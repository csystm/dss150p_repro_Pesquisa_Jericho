"""Unit tests for the config loader."""
from src.config import get, reload


def test_get_returns_expected_types():
    assert isinstance(get("run.seed"), int)
    assert isinstance(get("split.test_size"), float)
    assert isinstance(get("data.feature_count"), int)
    assert isinstance(get("data.target_values"), list)
    assert isinstance(get("models.all"), list)


def test_get_known_values():
    assert get("run.seed") == 246112165
    assert get("split.test_size") == 0.2
    assert get("reproduction.primary_metric") == "f1"
    assert get("reproduction.tolerance") == 0.01
    assert get("data.feature_count") == 215
    assert len(get("models.all")) == 6
    assert len(get("models.linear_subset")) == 3


def test_get_missing_key_returns_default():
    assert get("does.not.exist", "fallback") == "fallback"
    assert get("run.missing_key", 42) == 42


def test_reload_clears_cache():
    reload()
    assert get("run.seed") == 246112165