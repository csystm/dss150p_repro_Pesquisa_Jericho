"""Unit tests for the check_* functions in src.validate."""
import pandas as pd
import pytest

from src.validate import (
    check_binary_features,
    check_feature_count,
    check_no_nulls,
    check_no_target_leakage,
    check_row_count,
    check_schema,
    check_source_row_number_contiguous,
    check_target_distribution,
    check_target_values,
    check_unique_key,
)


@pytest.fixture
def good_df():
    return pd.DataFrame({
        "source_row_key": ["a", "b", "c"],
        "source_row_number": [0, 1, 2],
        "record_hash": ["h1", "h2", "h3"],
        "is_malware": [0, 1, 0],
        "transact": [0, 1, 0],
        "INTERNET": [1, 0, 1],
    })


def test_check_schema_pass(good_df):
    assert check_schema(good_df, ["source_row_key", "is_malware"], "fail").passed


def test_check_schema_fail_reports_missing(good_df):
    r = check_schema(good_df, ["source_row_key", "missing"], "fail")
    assert not r.passed
    assert "missing" in r.details["missing"]


def test_check_no_nulls_pass(good_df):
    assert check_no_nulls(good_df, ["source_row_key", "is_malware"], "fail").passed


def test_check_no_nulls_fail_reports_offender(good_df):
    df = good_df.copy()
    df.loc[0, "source_row_key"] = None
    r = check_no_nulls(df, ["source_row_key"], "fail")
    assert not r.passed
    assert r.details["offenders"]["source_row_key"] == 1


def test_check_unique_key(good_df):
    assert check_unique_key(good_df, "source_row_key", "warn").passed
    df = pd.concat([good_df, good_df.iloc[[0]]], ignore_index=True)
    assert not check_unique_key(df, "source_row_key", "warn").passed


def test_check_binary_features_catches_non_binary(good_df):
    assert check_binary_features(good_df, "fail").passed
    df = good_df.copy()
    df.loc[0, "transact"] = 7
    r = check_binary_features(df, "fail")
    assert not r.passed
    assert "transact" in r.details["violations"]


def test_check_target_values(good_df):
    assert check_target_values(good_df, "is_malware", {0, 1}, "fail").passed
    df = good_df.copy()
    df.loc[0, "is_malware"] = 2
    assert not check_target_values(df, "is_malware", {0, 1}, "fail").passed


def test_check_target_distribution(good_df):
    assert check_target_distribution(good_df, "is_malware", {0: 2, 1: 1}, "fail").passed
    assert not check_target_distribution(good_df, "is_malware", {0: 5, 1: 5}, "fail").passed


def test_check_row_count(good_df):
    assert check_row_count(good_df, 3, "fail").passed
    assert not check_row_count(good_df, 4, "fail").passed


def test_check_feature_count(good_df):
    # features = transact, INTERNET
    assert check_feature_count(good_df, 2, "fail").passed
    assert not check_feature_count(good_df, 3, "fail").passed


def test_check_source_row_number_contiguous_detects_gap(good_df):
    assert check_source_row_number_contiguous(good_df, "fail").passed
    df = good_df.copy()
    df.loc[1, "source_row_number"] = 5
    assert not check_source_row_number_contiguous(df, "fail").passed


def test_check_no_target_leakage_regression_guard(good_df):
    """The feature selector excludes is_malware and class by construction."""
    assert check_no_target_leakage(good_df, "fail", "is_malware").passed