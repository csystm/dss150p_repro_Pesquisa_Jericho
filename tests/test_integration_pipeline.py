"""Integration tests spanning raw -> staging -> curated and file boundaries."""
from pathlib import Path

import pandas as pd
import pytest

from src.storage import read_parquet, write_parquet
from src.transform import build_curated, build_staging


def test_raw_to_curated_roundtrip(tmp_path: Path, toy_raw_df):
    """Persist staging to disk, reload, build curated. Prove the file boundary
    does not change dtypes or row counts."""
    staging_path = tmp_path / "staging.parquet"
    curated_path = tmp_path / "curated.parquet"

    st1 = build_staging(toy_raw_df, transform_run_id="test_run")
    write_parquet(st1, staging_path)
    st2 = read_parquet(staging_path)

    assert st1.shape == st2.shape
    assert st1["source_row_key"].tolist() == st2["source_row_key"].tolist()
    assert st1["TelephonyManager.getSimCountryIso"].dtype == st2["TelephonyManager.getSimCountryIso"].dtype

    cu = build_curated(st2)
    write_parquet(cu, curated_path)
    cu2 = read_parquet(curated_path)

    assert cu.shape == cu2.shape
    assert cu["is_malware"].tolist() == cu2["is_malware"].tolist()
    assert "class" not in cu2.columns


def test_conflicting_label_flag_survives_roundtrip(tmp_path: Path):
    """Two identical feature vectors with different labels get flagged, and the
    flag survives parquet write/read."""
    rows = [
        {
            "pipeline_run_id": "r", "ingested_at_utc": "t", "source_file": "f",
            "source_checksum": "c", "source_row_number": 0,
            "source_row_key": "k:0", "record_hash": "h0",
            "transact": 1, "INTERNET": 1,
            "TelephonyManager.getSimCountryIso": "0", "class": "S",
        },
        {
            "pipeline_run_id": "r", "ingested_at_utc": "t", "source_file": "f",
            "source_checksum": "c", "source_row_number": 1,
            "source_row_key": "k:1", "record_hash": "h1",
            "transact": 1, "INTERNET": 1,
            "TelephonyManager.getSimCountryIso": "0", "class": "B",
        },
    ]
    raw = pd.DataFrame(rows)
    st = build_staging(raw, transform_run_id="test_run")

    # Both rows should be flagged: same feature vector, different class.
    assert st["flag_conflicting_label"].sum() == 2

    p = tmp_path / "staging.parquet"
    write_parquet(st, p)
    st2 = read_parquet(p)
    assert st2["flag_conflicting_label"].sum() == 2
    assert st2["flag_conflicting_label"].dtype == bool