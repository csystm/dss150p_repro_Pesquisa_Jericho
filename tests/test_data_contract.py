"""Data-quality assertions over the produced artifacts.

Skipped if the pipeline has not been run (curated parquet missing). These are
the "data tests" layer: they prove the outputs honor the declared contract.
"""
import hashlib
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CURATED = ROOT / "data" / "curated" / "curated.parquet"
CONTRACT = ROOT / "metadata" / "data_contract.yml"
MANIFEST = ROOT / "metadata" / "source_manifest.yml"

AUDIT_COLS = {
    "ingest_run_id", "transform_run_id", "source_row_number",
    "source_row_key", "record_hash", "flag_conflicting_label",
    "is_malware",
}

pytestmark = [
    pytest.mark.data,
    pytest.mark.skipif(not CURATED.exists(), reason=f"{CURATED} not present"),
]


@pytest.fixture(scope="module")
def curated():
    return pd.read_parquet(CURATED)


@pytest.fixture(scope="module")
def contract():
    return yaml.safe_load(CONTRACT.read_text())


def _features(df):
    return [c for c in df.columns if c not in AUDIT_COLS]


def test_row_count_matches_contract(curated, contract):
    assert len(curated) == contract["schema"]["row_count_expected"]


def test_feature_count(curated, contract):
    assert len(_features(curated)) == contract["schema"]["feature_columns"]["expected_count"]


def test_all_features_binary(curated):
    for col in _features(curated):
        vals = set(curated[col].unique().tolist())
        assert vals <= {0, 1}, f"{col} has values {vals}"


def test_target_is_binary(curated):
    assert set(curated["is_malware"].unique().tolist()) <= {0, 1}


def test_target_distribution(curated):
    assert curated["is_malware"].value_counts().to_dict() == {0: 9476, 1: 5560}


def test_source_row_key_unique(curated):
    assert curated["source_row_key"].duplicated().sum() == 0


def test_source_row_number_contiguous(curated):
    nums = sorted(curated["source_row_number"].tolist())
    assert nums == list(range(len(nums)))


def test_no_class_column(curated):
    assert "class" not in curated.columns


def test_no_target_in_features(curated):
    feats = _features(curated)
    assert "is_malware" not in feats
    assert "class" not in feats


def test_conflicting_label_flag_count(curated):
    """Post-normalization figure. Change only if normalization changes."""
    assert int(curated["flag_conflicting_label"].sum()) == 402


def test_no_nulls_in_critical_columns(curated):
    for col in ["source_row_key", "record_hash", "is_malware"]:
        assert curated[col].isna().sum() == 0


def test_manifest_checksum_matches_source_on_disk():
    if not MANIFEST.exists():
        pytest.skip("no manifest")
    manifest = yaml.safe_load(MANIFEST.read_text())
    src = ROOT / "data" / "source" / manifest["source_file"]
    if not src.exists():
        pytest.skip(f"source not present: {src}")
    h = hashlib.sha256()
    with open(src, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    assert h.hexdigest() == manifest["sha256"]