"""Staging and curated transformations for the DSS150P reproducible pipeline.

Reads:  data/raw/batches/batch_*.parquet
Writes: data/staging/staging.parquet
        data/curated/curated.parquet
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.storage import read_parquet, write_parquet

TARGET_COL = "class"
TARGET_MAP = {"S": 1, "B": 0}
TARGET_DERIVED_COL = "is_malware"
MIXED_TYPE_COL = "TelephonyManager.getSimCountryIso"

RAW_AUDIT_COLS = [
    "pipeline_run_id",
    "ingested_at_utc",
    "source_file",
    "source_checksum",
    "source_row_number",
    "source_row_key",
    "record_hash",
]

STAGING_AUDIT_COLS = [
    "ingest_run_id",
    "transform_run_id",
    "ingested_at_utc",
    "processed_at_utc",
    "source_file",
    "source_checksum",
    "source_row_number",
    "source_row_key",
    "record_hash",
    "flag_conflicting_label",
]

NON_FEATURE_COLS = set(RAW_AUDIT_COLS) | set(STAGING_AUDIT_COLS) | {
    TARGET_COL,
    TARGET_DERIVED_COL,
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id(prefix: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{ts}_{uuid.uuid4().hex[:8]}"


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Feature columns = every column except audit, target, and target-derived."""
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


# ---------------------------------------------------------------------------
# Conflicting-label detection (post-normalization)
# ---------------------------------------------------------------------------
def conflicting_label_keys(
    df: pd.DataFrame, feature_cols: list[str], target_col: str = TARGET_COL
) -> set:
    nunique = df.groupby(feature_cols, dropna=False)[target_col].nunique()
    conflict_keys = nunique[nunique > 1].index
    return set(conflict_keys)


def flag_conflicting_labels(
    df: pd.DataFrame, feature_cols: list[str], target_col: str = TARGET_COL
) -> pd.Series:
    conflict_set = conflicting_label_keys(df, feature_cols, target_col)
    if not conflict_set:
        return pd.Series(False, index=df.index, name="flag_conflicting_label")
    # Fast membership via MultiIndex.isin
    mi = pd.MultiIndex.from_frame(df[feature_cols])
    conflict_index = pd.MultiIndex.from_tuples(list(conflict_set), names=feature_cols)
    return pd.Series(mi.isin(conflict_index), index=df.index, name="flag_conflicting_label")


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------
def build_staging(raw_df: pd.DataFrame, transform_run_id: str) -> pd.DataFrame:
    df = raw_df.copy()

    # Rename raw's pipeline_run_id -> ingest_run_id.
    df = df.rename(columns={"pipeline_run_id": "ingest_run_id"})

    # Normalize the mixed-type column to {0,1}.
    if MIXED_TYPE_COL in df.columns:
        df[MIXED_TYPE_COL] = (
            df[MIXED_TYPE_COL].astype("string").replace({"?": "0"}).astype("int64")
        )

    # Enforce int {0,1} on every feature column.
    feats = feature_columns(df)
    for c in feats:
        df[c] = df[c].astype("int64")
        bad = ~df[c].isin([0, 1])
        if bad.any():
            raise ValueError(
                f"staging: feature '{c}' has non-binary values in {int(bad.sum())} rows"
            )

    # Flag conflicting labels on the normalized vector.
    conflict_flag = flag_conflicting_labels(df, feats)

    # Build the audit block once and concat, instead of repeated insert() calls.
    audit_block = pd.DataFrame({
        "ingest_run_id": df["ingest_run_id"].astype("string"),
        "transform_run_id": transform_run_id,
        "ingested_at_utc": df["ingested_at_utc"].astype("string"),
        "processed_at_utc": utc_now_iso(),
        "source_file": df["source_file"].astype("string"),
        "source_checksum": df["source_checksum"].astype("string"),
        "source_row_number": df["source_row_number"].astype("int64"),
        "source_row_key": df["source_row_key"].astype("string"),
        "record_hash": df["record_hash"].astype("string"),
        "flag_conflicting_label": conflict_flag.astype(bool),
    })

    staging = pd.concat([audit_block, df[feats], df[[TARGET_COL]]], axis=1)
    staging = staging.sort_values("source_row_number", kind="mergesort").reset_index(drop=True)
    return staging


# ---------------------------------------------------------------------------
# Curated
# ---------------------------------------------------------------------------
def build_curated(staging_df: pd.DataFrame) -> pd.DataFrame:
    df = staging_df.copy()

    if TARGET_COL not in df.columns:
        raise ValueError("curated: target column missing from staging")
    unknown = set(df[TARGET_COL].unique()) - set(TARGET_MAP)
    if unknown:
        raise ValueError(f"curated: unexpected target values {unknown}")

    feats = feature_columns(df)

    # Build curated block explicitly so is_malware is never accidentally a feature.
    curated = pd.concat(
        [
            df[
                [
                    "ingest_run_id",
                    "transform_run_id",
                    "source_row_number",
                    "source_row_key",
                    "record_hash",
                    "flag_conflicting_label",
                ]
            ],
            df[feats],
            df[TARGET_COL].map(TARGET_MAP).astype("int64").rename(TARGET_DERIVED_COL),
        ],
        axis=1,
    )

    curated = curated.sort_values("source_row_number", kind="mergesort").reset_index(drop=True)
    return curated


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------
def run_transform(raw_dir: Path, staging_path: Path, curated_path: Path) -> dict:
    transform_run_id = new_run_id("transform")

    batch_files = sorted((raw_dir / "batches").glob("batch_*.parquet"))
    if not batch_files:
        raise FileNotFoundError(f"no raw batches found in {raw_dir / 'batches'}")

    raw_df = pd.concat([read_parquet(p) for p in batch_files], ignore_index=True)
    raw_df = raw_df.sort_values("source_row_number", kind="mergesort").reset_index(drop=True)

    staging_df = build_staging(raw_df, transform_run_id=transform_run_id)
    curated_df = build_curated(staging_df)

    write_parquet(staging_df, staging_path)
    write_parquet(curated_df, curated_path)

    n_conflict = int(staging_df["flag_conflicting_label"].sum())
    return {
        "transform_run_id": transform_run_id,
        "raw_rows": int(len(raw_df)),
        "staging_rows": int(len(staging_df)),
        "curated_rows": int(len(curated_df)),
        "flag_conflicting_label_rows": n_conflict,
        "staging_path": str(staging_path),
        "curated_path": str(curated_path),
    }


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Build staging and curated layers.")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--staging-path", default="data/staging/staging.parquet")
    p.add_argument("--curated-path", default="data/curated/curated.parquet")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        summary = run_transform(
            raw_dir=Path(args.raw_dir),
            staging_path=Path(args.staging_path),
            curated_path=Path(args.curated_path),
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for k, v in summary.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())