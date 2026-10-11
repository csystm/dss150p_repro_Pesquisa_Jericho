"""Unit tests for deterministic behavior in src.train."""
import numpy as np
import pandas as pd
import pytest

from src.train import SEED, _key_checksum, feature_columns, make_split, set_seeds


@pytest.fixture
def cur_df():
    n = 100
    return pd.DataFrame({
        "source_row_key": [f"k:{i}" for i in range(n)],
        "source_row_number": list(range(n)),
        "record_hash": [f"h{i}" for i in range(n)],
        "ingest_run_id": ["r"] * n,
        "transform_run_id": ["t"] * n,
        "flag_conflicting_label": [False] * n,
        "is_malware": [i % 2 for i in range(n)],
        "transact": [i % 2 for i in range(n)],
        "INTERNET": [(i + 1) % 2 for i in range(n)],
    })


def test_feature_columns_excludes_audit_and_target(cur_df):
    feats = feature_columns(cur_df)
    for c in ["is_malware", "source_row_key", "source_row_number",
              "record_hash", "ingest_run_id", "transform_run_id",
              "flag_conflicting_label"]:
        assert c not in feats
    assert "transact" in feats
    assert "INTERNET" in feats


def test_make_split_deterministic(cur_df):
    a = make_split(cur_df)
    b = make_split(cur_df)
    pd.testing.assert_frame_equal(a[0], b[0])
    pd.testing.assert_frame_equal(a[1], b[1])
    pd.testing.assert_series_equal(a[2], b[2])
    pd.testing.assert_series_equal(a[3], b[3])


def test_make_split_sizes(cur_df):
    X_train, X_test, _, _ = make_split(cur_df)
    assert len(X_train) + len(X_test) == len(cur_df)
    assert len(X_test) == 20  # 0.2 of 100


def test_make_split_stratified(cur_df):
    _, _, y_train, y_test = make_split(cur_df)
    assert abs(y_train.mean() - 0.5) < 0.05
    assert abs(y_test.mean() - 0.5) < 0.05


def test_key_checksum_deterministic():
    keys = ["a", "b", "c"]
    assert _key_checksum(keys) == _key_checksum(keys)


def test_key_checksum_order_independent():
    assert _key_checksum(["a", "b", "c"]) == _key_checksum(["c", "b", "a"])


def test_set_seeds_reproducible():
    set_seeds(SEED)
    a = np.random.random(5)
    set_seeds(SEED)
    b = np.random.random(5)
    np.testing.assert_array_equal(a, b)