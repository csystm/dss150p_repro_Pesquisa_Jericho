"""Unit tests for src.transform."""
import pandas as pd
import pytest

from src.transform import (
    MIXED_TYPE_COL, build_curated, build_staging, feature_columns,
)


def test_normalizes_mixed_type_column(toy_raw_df):
    """The mixed-type column is normalized to {0,1} and stored as int."""
    st = build_staging(toy_raw_df, transform_run_id="test_run")
    assert sorted(st[MIXED_TYPE_COL].unique().tolist()) == [0, 1]
    assert st[MIXED_TYPE_COL].dtype == "int64"


def test_feature_columns_excludes_audit_and_target(toy_raw_df):
    """feature_columns never returns audit columns, class, or is_malware."""
    st = build_staging(toy_raw_df, transform_run_id="test_run")
    feats = feature_columns(st)
    assert "source_row_key" not in feats
    assert "pipeline_run_id" not in feats
    assert "class" not in feats
    assert "is_malware" not in feats
    assert "transact" in feats


def test_curated_maps_target_and_drops_class(toy_raw_df):
    """Curated encodes class -> is_malware and drops the raw target column."""
    st = build_staging(toy_raw_df, transform_run_id="test_run")
    cu = build_curated(st)
    assert "class" not in cu.columns
    assert "is_malware" in cu.columns
    assert set(cu["is_malware"].unique().tolist()) <= {0, 1}
    # Row 0 = S, Row 1 = B, Row 2 = S
    assert cu.sort_values("source_row_number")["is_malware"].tolist() == [1, 0, 1]