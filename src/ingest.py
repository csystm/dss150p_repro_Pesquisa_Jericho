"""Full and incremental ingestion for the DSS150P reproducible pipeline.

Simulates incremental arrival from an immutable source by splitting the source
into N deterministic row-order batches (DREBIN has no reliable event timestamp).
A checkpoint file outside the Python source records the last committed batch.
Reruns resume from the checkpoint and never re-append committed batches unless
--force is passed.

Audit columns added to every raw row:
    pipeline_run_id, ingested_at_utc, source_file, source_checksum,
    source_row_number, source_row_key, record_hash
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

MIXED_TYPE_COL = "TelephonyManager.getSimCountryIso"
TARGET_COL = "class"
DEFAULT_N_BATCHES = 3


# --------------------------------------------------------------------------
# Utility functions
# --------------------------------------------------------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{ts}_{uuid.uuid4().hex[:8]}"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def row_hash(values) -> str:
    h = hashlib.sha256()
    for v in values:
        h.update(str(v).encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()


def load_source(source_path: Path) -> pd.DataFrame:
    return pd.read_csv(
        source_path,
        dtype={MIXED_TYPE_COL: "string"},
        low_memory=False,
    )


def compute_batch_boundaries(n_rows: int, n_batches: int) -> list[tuple[int, int]]:
    base = n_rows // n_batches
    rem = n_rows % n_batches
    bounds, start = [], 0
    for i in range(n_batches):
        size = base + (1 if i < rem else 0)
        bounds.append((start, start + size))
        start += size
    return bounds


def add_audit_columns(
    df: pd.DataFrame,
    pipeline_run_id: str,
    ingested_at: str,
    source_file: str,
    source_checksum: str,
    row_offset: int,
) -> pd.DataFrame:
    out = df.copy()
    n = len(out)
    original_cols = df.columns.tolist()

    out.insert(0, "pipeline_run_id", pipeline_run_id)
    out.insert(1, "ingested_at_utc", ingested_at)
    out.insert(2, "source_file", source_file)
    out.insert(3, "source_checksum", source_checksum)
    out.insert(4, "source_row_number", [row_offset + i for i in range(n)])
    out.insert(5, "source_row_key",
               [f"drebin_subset_15036:row:{row_offset + i}" for i in range(n)])
    out["record_hash"] = [
        row_hash(out.iloc[i][original_cols].tolist()) for i in range(n)
    ]
    return out


# --------------------------------------------------------------------------
# Checkpoint and audit log
# --------------------------------------------------------------------------
def read_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {"last_committed_batch": -1, "updated_at_utc": None}
    return json.loads(path.read_text(encoding="utf-8"))


def write_checkpoint(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_audit_log(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


# --------------------------------------------------------------------------
# Validation of a single batch before committing
# --------------------------------------------------------------------------
def validate_batch(
    batch: pd.DataFrame,
    expected_start: int,
    expected_end: int,
    source_checksum: str,
) -> None:
    expected_rows = expected_end - expected_start
    if len(batch) != expected_rows:
        raise ValueError(f"batch row count {len(batch)} != expected {expected_rows}")

    expected_numbers = list(range(expected_start, expected_end))
    if batch["source_row_number"].tolist() != expected_numbers:
        raise ValueError(
            f"source_row_number not contiguous from {expected_start} to {expected_end - 1}"
        )

    if batch["source_row_key"].duplicated().any():
        raise ValueError("duplicate source_row_key within batch")
    if not (batch["source_checksum"] == source_checksum).all():
        raise ValueError("source_checksum mismatch inside batch")
    if batch["record_hash"].isna().any():
        raise ValueError("null record_hash inside batch")

# --------------------------------------------------------------------------
# Batch writer
# --------------------------------------------------------------------------
def write_batch(
    batch_df: pd.DataFrame,
    batch_id: int,
    raw_batches_dir: Path,
) -> Path:
    raw_batches_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_batches_dir / f"batch_{batch_id:04d}.parquet"
    tmp_path = out_path.with_suffix(".parquet.tmp")
    batch_df.to_parquet(tmp_path, index=False)
    tmp_path.replace(out_path)
    return out_path


# --------------------------------------------------------------------------
# Main ingestion flow
# --------------------------------------------------------------------------
def run_ingest(
    source_path: Path,
    raw_dir: Path,
    n_batches: int,
    force: bool,
    fail_after: int | None,
    expected_checksum: str | None,
) -> int:
    raw_dir.mkdir(parents=True, exist_ok=True)
    batches_dir = raw_dir / "batches"
    checkpoint_path = raw_dir / "_checkpoints" / "ingest_checkpoint.json"
    audit_log_path = raw_dir / "_ingest_audit.jsonl"

    actual_checksum = sha256_file(source_path)
    if expected_checksum and expected_checksum != actual_checksum:
        print(
            f"ERROR: source checksum mismatch.\n"
            f"  expected: {expected_checksum}\n"
            f"  actual:   {actual_checksum}",
            file=sys.stderr,
        )
        return 2

    df = load_source(source_path)
    n_rows = len(df)

    boundaries = compute_batch_boundaries(n_rows, n_batches)

    if force:
        print("[force] resetting checkpoint and removing existing batches")
        write_checkpoint(checkpoint_path, {"last_committed_batch": -1, "updated_at_utc": utc_now_iso()})
        for p in batches_dir.glob("batch_*.parquet"):
            p.unlink()

    ckpt = read_checkpoint(checkpoint_path)
    last_committed = int(ckpt.get("last_committed_batch", -1))
    print(f"[state] last committed batch: {last_committed}")

    pipeline_run_id = new_run_id()
    ingested_at = utc_now_iso()
    source_file = source_path.name

    committed_this_run = 0

    for batch_id, (start, end) in enumerate(boundaries):
        if batch_id <= last_committed:
            print(f"[skip] batch {batch_id:04d} rows [{start}:{end}] already committed")
            continue

        chunk = df.iloc[start:end].copy()
        batch_df = add_audit_columns(
            chunk,
            pipeline_run_id=pipeline_run_id,
            ingested_at=ingested_at,
            source_file=source_file,
            source_checksum=actual_checksum,
            row_offset=start,
        )

        validate_batch(
            batch_df,
            expected_start=start,
            expected_end=end,
            source_checksum=actual_checksum,
        )

        out_path = write_batch(batch_df, batch_id, batches_dir)

        append_audit_log(
            audit_log_path,
            [
                {
                    "pipeline_run_id": pipeline_run_id,
                    "batch_id": batch_id,
                    "start_row": start,
                    "end_row": end,
                    "rows": end - start,
                    "ingested_at_utc": ingested_at,
                    "source_file": source_file,
                    "source_checksum": actual_checksum,
                    "output_path": str(out_path.relative_to(raw_dir.parent.parent)),
                }
            ],
        )

        write_checkpoint(
            checkpoint_path,
            {
                "last_committed_batch": batch_id,
                "updated_at_utc": utc_now_iso(),
                "pipeline_run_id": pipeline_run_id,
            },
        )
        committed_this_run += 1
        print(f"[commit] batch {batch_id:04d} rows [{start}:{end}] -> {out_path.name}")

        if fail_after is not None and batch_id == fail_after:
            print(f"[inject] simulating failure after batch {batch_id:04d}", file=sys.stderr)
            raise RuntimeError(f"Simulated failure after batch {batch_id}")

    print(
        f"[done] run_id={pipeline_run_id} committed_this_run={committed_this_run} "
        f"last_committed={read_checkpoint(checkpoint_path)['last_committed_batch']}"
    )
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Ingest DREBIN source into raw batches.")
    parser.add_argument("--source", default="data/source/drebin_dataset.csv")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--n-batches", type=int, default=DEFAULT_N_BATCHES)
    parser.add_argument("--force", action="store_true", help="Reset checkpoint and re-ingest all batches.")
    parser.add_argument("--fail-after", type=int, default=None,
                        help="Simulate failure after committing this batch id (for recovery demo).")
    parser.add_argument("--expected-checksum", default=None,
                        help="If provided, verify source file hash before ingesting.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    source = Path(args.source)
    if not source.exists():
        print(f"ERROR: source not found: {source}", file=sys.stderr)
        return 1
    return run_ingest(
        source_path=source,
        raw_dir=Path(args.raw_dir),
        n_batches=args.n_batches,
        force=args.force,
        fail_after=args.fail_after,
        expected_checksum=args.expected_checksum,
    )


if __name__ == "__main__":
    sys.exit(main())