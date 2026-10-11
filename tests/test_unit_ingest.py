"""Unit tests for src.ingest — batch boundaries, audit columns, checkpoint."""
import json
from pathlib import Path

import pandas as pd
import pytest

from src.ingest import (
    add_audit_columns,
    compute_batch_boundaries,
    read_checkpoint,
    row_hash,
    validate_batch,
    write_checkpoint,
)


def test_compute_batch_boundaries_even_split():
    assert compute_batch_boundaries(15036, 3) == [(0, 5012), (5012, 10024), (10024, 15036)]


def test_compute_batch_boundaries_uneven():
    # 10 into 3 gives 4,3,3
    assert compute_batch_boundaries(10, 3) == [(0, 4), (4, 7), (7, 10)]


def test_row_hash_deterministic():
    assert row_hash([1, 0, "x"]) == row_hash([1, 0, "x"])
    assert row_hash([1, 0, "x"]) != row_hash([1, 0, "y"])
    assert len(row_hash([1, 0, "x"])) == 64


def test_add_audit_columns_uses_global_row_offset():
    chunk = pd.DataFrame({"feature_a": [0, 1, 0], "class": ["S", "B", "S"]})
    out = add_audit_columns(
        chunk,
        pipeline_run_id="r1",
        ingested_at="2026-01-01T00:00:00+00:00",
        source_file="x.csv",
        source_checksum="abc",
        row_offset=5012,
    )
    assert out["source_row_number"].tolist() == [5012, 5013, 5014]
    assert out["source_row_key"].tolist() == [
        "drebin_subset_15036:row:5012",
        "drebin_subset_15036:row:5013",
        "drebin_subset_15036:row:5014",
    ]
    assert out["pipeline_run_id"].unique().tolist() == ["r1"]


def test_validate_batch_accepts_correct_batch():
    chunk = pd.DataFrame({"feature_a": [0, 1], "class": ["S", "B"]})
    out = add_audit_columns(
        chunk, pipeline_run_id="r", ingested_at="t",
        source_file="x.csv", source_checksum="c", row_offset=0,
    )
    validate_batch(out, expected_start=0, expected_end=2, source_checksum="c")


def test_validate_batch_rejects_wrong_start():
    chunk = pd.DataFrame({"feature_a": [0, 1], "class": ["S", "B"]})
    out = add_audit_columns(
        chunk, pipeline_run_id="r", ingested_at="t",
        source_file="x.csv", source_checksum="c", row_offset=5,
    )
    with pytest.raises(ValueError, match="source_row_number"):
        validate_batch(out, expected_start=0, expected_end=2, source_checksum="c")


def test_validate_batch_rejects_checksum_mismatch():
    chunk = pd.DataFrame({"feature_a": [0, 1], "class": ["S", "B"]})
    out = add_audit_columns(
        chunk, pipeline_run_id="r", ingested_at="t",
        source_file="x.csv", source_checksum="wrong", row_offset=0,
    )
    with pytest.raises(ValueError, match="checksum"):
        validate_batch(out, expected_start=0, expected_end=2, source_checksum="c")


def test_checkpoint_roundtrip_and_atomic_write(tmp_path: Path):
    p = tmp_path / "checkpoint.json"
    assert read_checkpoint(p)["last_committed_batch"] == -1

    write_checkpoint(p, {"last_committed_batch": 1, "updated_at_utc": "x"})
    assert read_checkpoint(p)["last_committed_batch"] == 1
    assert not p.with_suffix(".tmp").exists()
    assert json.loads(p.read_text())["last_committed_batch"] == 1