"""Storage benchmark for the DSS150P reproducible pipeline.

Materializes the same logical curated dataset in CSV, JSONL, Parquet, and
PostgreSQL, then measures:

  - Serialized size for each format.
  - Write time.
  - Read time (median of N=5).
  - PostgreSQL full-table and selective/filter query time.
  - Row counts and a checksum of the sorted source_row_key list to prove
    all four representations carry the same logical records.

Writes:
  outputs/benchmark/benchmark.json     (raw measurements)
  outputs/benchmark/sizes.csv
  docs/benchmark_report.md             (findings and per-use-case conclusions)

Partition experiment:
  The dataset has no natural date/time key. We create a pedagogical partition
  on is_malware (2 partitions) and on flag_conflicting_label (2 partitions).
  We demonstrate reading a single partition and verifying its row count.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from src import db
from src.storage import read_parquet, write_csv, write_json, write_jsonl, write_parquet

N_READS = 5
TARGET = "is_malware"


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------
def _time_it(fn, *args, **kwargs) -> tuple[float, object]:
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    dt = time.perf_counter() - t0
    return dt, result


def _median_seconds(fn, n: int = N_READS, *args, **kwargs) -> float:
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn(*args, **kwargs)
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


# ---------------------------------------------------------------------------
# Logical-equivalence check
# ---------------------------------------------------------------------------
def keys_checksum(df: pd.DataFrame, key: str = "source_row_key") -> str:
    h = hashlib.sha256()
    for v in sorted(df[key].astype(str).tolist()):
        h.update(v.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Writers / readers for each format
# ---------------------------------------------------------------------------
def write_all_formats(df: pd.DataFrame, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv":     out_dir / "curated.csv",
        "jsonl":   out_dir / "curated.jsonl",
        "parquet": out_dir / "curated.parquet",
    }

    timings = {}
    t, _ = _time_it(write_csv, df, paths["csv"]);     timings["csv_write_s"]     = t
    t, _ = _time_it(write_jsonl, df, paths["jsonl"]); timings["jsonl_write_s"]   = t
    t, _ = _time_it(write_parquet, df, paths["parquet"]); timings["parquet_write_s"] = t

    return {"paths": {k: str(v) for k, v in paths.items()}, "timings": timings}


def read_all_formats(paths: dict) -> dict:
    timings = {}

    timings["csv_read_s"] = _median_seconds(lambda p: pd.read_csv(p), N_READS, paths["csv"])
    # JSONL lines=True is the intended layout for record streaming.
    timings["jsonl_read_s"] = _median_seconds(
        lambda p: pd.read_json(p, orient="records", lines=True), N_READS, paths["jsonl"]
    )
    timings["parquet_read_s"] = _median_seconds(lambda p: pd.read_parquet(p), N_READS, paths["parquet"])

    return timings


def file_sizes(paths: dict) -> dict:
    return {k: Path(v).stat().st_size for k, v in paths.items()}


# ---------------------------------------------------------------------------
# Postgres load + queries
# ---------------------------------------------------------------------------
def load_to_postgres(df: pd.DataFrame) -> dict:
    db.wait_for_postgres()

    # Clear previous benchmark rows so timing is like-for-like
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE curated_apps")

    t_insert, inserted = _time_it(db.upsert_curated_apps, df)
    return {
        "postgres_insert_s": t_insert,
        "postgres_rows_inserted": int(inserted),
        "postgres_count": db.count_curated_rows(),
    }


def postgres_query_timings() -> dict:
    full_sql = "SELECT count(*) FROM curated_apps"
    selective_sql = "SELECT count(*) FROM curated_apps WHERE is_malware = 1"

    def _full():
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute(full_sql)
            return cur.fetchone()[0]

    def _selective():
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute(selective_sql)
            return cur.fetchone()[0]

    return {
        "postgres_full_table_scan_s": _median_seconds(_full, N_READS),
        "postgres_selective_query_s": _median_seconds(_selective, N_READS),
        "postgres_full_count":        _full(),
        "postgres_selective_count":   _selective(),
    }


# ---------------------------------------------------------------------------
# Partition experiment
# ---------------------------------------------------------------------------
def partition_experiment(df: pd.DataFrame, out_dir: Path) -> dict:
    """Split curated data into pedagogical partitions and prove we can read one
    partition independently."""
    part_dir = out_dir / "partitioned"
    part_dir.mkdir(parents=True, exist_ok=True)

    results: dict = {
        "note": ("No natural date/time key exists in the DREBIN subset. "
                 "Partitions here are pedagogical: is_malware and "
                 "flag_conflicting_label."),
        "partitions": {},
    }

    # Partition by is_malware
    for label, sub in df.groupby(TARGET):
        p = part_dir / f"is_malware={int(label)}.parquet"
        sub.to_parquet(p, index=False)
        results["partitions"][f"is_malware={int(label)}"] = {
            "rows": int(len(sub)),
            "path": str(p),
            "size_bytes": p.stat().st_size,
        }

    # Partition by flag_conflicting_label
    for label, sub in df.groupby("flag_conflicting_label"):
        slug = "true" if label else "false"
        p = part_dir / f"flag_conflicting_label={slug}.parquet"
        sub.to_parquet(p, index=False)
        results["partitions"][f"flag_conflicting_label={slug}"] = {
            "rows": int(len(sub)),
            "path": str(p),
            "size_bytes": p.stat().st_size,
        }

    # Demonstrate reading only one partition
    one = next(iter(results["partitions"].items()))
    name, meta = one
    partition_df = pd.read_parquet(meta["path"])
    results["selected_partition"] = {
        "name": name,
        "rows_read": int(len(partition_df)),
        "matches_written": int(len(partition_df)) == int(meta["rows"]),
    }
    return results


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------
def write_report(payload: dict, path: Path) -> None:
    lines = []
    lines.append("# Storage Benchmark Report")
    lines.append("")
    lines.append(f"Generated at: `{payload['generated_at_utc']}`")
    lines.append("")
    lines.append("## Dataset")
    lines.append(f"- Rows: {payload['rows']}")
    lines.append(f"- Columns: {payload['columns']}")
    lines.append(f"- Feature columns: {payload['feature_columns']}")
    lines.append("")
    lines.append("## Sizes (bytes, lower is better)")
    lines.append("| format | bytes | bytes/row |")
    lines.append("|---|---:|---:|")
    for fmt, size in payload["sizes"].items():
        lines.append(f"| {fmt} | {size} | {size / payload['rows']:.2f} |")
    lines.append("")
    lines.append("## Write timings (seconds)")
    lines.append("| format | write |")
    lines.append("|---|---:|")
    for k, v in payload["timings"].items():
        if k.endswith("_write_s"):
            lines.append(f"| {k[:-8]} | {v:.4f} |")
    if "postgres_insert_s" in payload["timings"]:
        lines.append(f"| postgres | {payload['timings']['postgres_insert_s']:.4f} |")
    lines.append("")
    lines.append(f"## Read timings (median of {N_READS}, seconds, lower is better)")
    lines.append("| format | read |")
    lines.append("|---|---:|")
    for k, v in payload["timings"].items():
        if k.endswith("_read_s"):
            lines.append(f"| {k[:-7]} | {v:.4f} |")
    lines.append("")
    lines.append("## PostgreSQL query timings (median of "
                 f"{N_READS}, seconds)")
    lines.append("| query | median seconds | row count |")
    lines.append("|---|---:|---:|")
    lines.append(f"| full table count | {payload['timings']['postgres_full_table_scan_s']:.6f} "
                 f"| {payload['timings']['postgres_full_count']} |")
    lines.append(f"| selective (is_malware=1) | {payload['timings']['postgres_selective_query_s']:.6f} "
                 f"| {payload['timings']['postgres_selective_count']} |")
    lines.append("")
    lines.append("## Logical-equivalence check")
    lines.append(f"Sorted `source_row_key` SHA-256 of curated input: `{payload['keys_checksum']}`")
    lines.append("")
    lines.append("## Partition experiment")
    lines.append("")
    lines.append(payload["partitions"]["note"])
    lines.append("")
    lines.append("| partition | rows | bytes |")
    lines.append("|---|---:|---:|")
    for name, meta in payload["partitions"]["partitions"].items():
        lines.append(f"| {name} | {meta['rows']} | {meta['size_bytes']} |")
    sel = payload["partitions"]["selected_partition"]
    lines.append("")
    lines.append(f"Selected partition: `{sel['name']}` — read {sel['rows_read']} rows "
                 f"(matches written: {sel['matches_written']}).")
    lines.append("")
    lines.append("## Findings per use case")
    lines.append("")
    lines.append("*Fill in after inspecting the numbers above. Format recommendations are workload-specific and not universal.*")
    lines.append("")
    lines.append("- **Source exchange**: ")
    lines.append("- **Pipeline intermediate storage**: ")
    lines.append("- **Model input**: ")
    lines.append("- **Analytical querying (PostgreSQL)**: ")
    lines.append("- **Partitioning**: ")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_benchmark(curated_path: Path, out_dir: Path, report_path: Path,
                  skip_postgres: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = read_parquet(curated_path)
    # Ensure deterministic order before hashing and writing.
    df = df.sort_values("source_row_number", kind="mergesort").reset_index(drop=True)

    feature_cols = [c for c in df.columns if c not in {
        "ingest_run_id", "transform_run_id", "source_row_number",
        "source_row_key", "record_hash", "flag_conflicting_label", "is_malware",
    }]

    print(f"curated rows={len(df)} cols={df.shape[1]} features={len(feature_cols)}")
    keys_hash = keys_checksum(df)

    writes = write_all_formats(df, out_dir)
    sizes = file_sizes(writes["paths"])
    reads = read_all_formats(writes["paths"])

    timings = {**writes["timings"], **reads}

    if not skip_postgres:
        pg_load = load_to_postgres(df)
        pg_query = postgres_query_timings()
        timings.update(pg_load)
        timings.update(pg_query)

    partitions = partition_experiment(df, out_dir)

    payload = {
        "generated_at_utc": db.utc_now_iso(),
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "feature_columns": int(len(feature_cols)),
        "keys_checksum": keys_hash,
        "paths": writes["paths"],
        "sizes": sizes,
        "timings": timings,
        "partitions": partitions,
    }

    write_json(payload, out_dir / "benchmark.json")
    write_report(payload, report_path)

    # sizes.csv for convenience
    pd.DataFrame(
        [{"format": k, "bytes": v} for k, v in sizes.items()]
    ).to_csv(out_dir / "sizes.csv", index=False)

    print(f"wrote {out_dir / 'benchmark.json'}")
    print(f"wrote {report_path}")
    return payload


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Storage benchmark: CSV/JSONL/Parquet/PostgreSQL.")
    p.add_argument("--curated-path", default="data/curated/curated.parquet")
    p.add_argument("--out-dir", default="outputs/benchmark")
    p.add_argument("--report-path", default="docs/benchmark_report.md")
    p.add_argument("--skip-postgres", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        run_benchmark(
            curated_path=Path(args.curated_path),
            out_dir=Path(args.out_dir),
            report_path=Path(args.report_path),
            skip_postgres=args.skip_postgres,
        )
    except Exception as exc:
        import traceback; traceback.print_exc()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())