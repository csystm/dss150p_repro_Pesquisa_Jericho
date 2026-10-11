"""Unit tests for src.storage I/O helpers."""
import json
from pathlib import Path

import pandas as pd

from src.storage import (
    read_parquet,
    write_csv,
    write_json,
    write_jsonl,
    write_parquet,
)


def _df():
    return pd.DataFrame({
        "a": [1, 2, 3],
        "b": ["x", "y", "z"],
        "c": [0.1, 0.2, 0.3],
    })


def test_parquet_roundtrip(tmp_path: Path):
    p = tmp_path / "t.parquet"
    write_parquet(_df(), p)
    pd.testing.assert_frame_equal(read_parquet(p), _df())


def test_parquet_atomic_no_tmp_left(tmp_path: Path):
    p = tmp_path / "t.parquet"
    write_parquet(_df(), p)
    assert p.exists()
    assert not p.with_suffix(".parquet.tmp").exists()


def test_csv_roundtrip(tmp_path: Path):
    p = tmp_path / "t.csv"
    write_csv(_df(), p)
    pd.testing.assert_frame_equal(pd.read_csv(p), _df())


def test_jsonl_roundtrip(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    write_jsonl(_df(), p)
    out = pd.read_json(p, orient="records", lines=True)
    pd.testing.assert_frame_equal(out, _df())


def test_json_roundtrip(tmp_path: Path):
    p = tmp_path / "meta.json"
    payload = {"a": 1, "b": [1, 2], "c": {"d": "e"}}
    write_json(payload, p)
    assert json.loads(p.read_text()) == payload


def test_write_creates_parent_dirs(tmp_path: Path):
    p = tmp_path / "a" / "b" / "c" / "t.parquet"
    write_parquet(_df(), p)
    assert p.exists()