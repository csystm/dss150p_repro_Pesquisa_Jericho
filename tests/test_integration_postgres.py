"""Integration tests against the running Postgres instance.

Skipped automatically if Postgres is not reachable. Run inside the pipeline
container (docker compose exec pipeline python -m pytest) for these to execute.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from src import db

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "metadata" / "source_profile.json"

AUDIT_COLS = {
    "ingest_run_id", "transform_run_id", "source_row_number",
    "source_row_key", "record_hash", "flag_conflicting_label",
    "is_malware", "class",
}


def _postgres_available() -> bool:
    try:
        db.wait_for_postgres(max_attempts=1, delay=0.0)
        return True
    except Exception:
        return False


def _feature_names() -> list[str]:
    """Read the 215 feature column names from the source profile."""
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    return [c for c in profile["column_names"] if c not in AUDIT_COLS]


def _full_row(i: int, source_row_key: str, feature_names: list[str]) -> dict:
    """Build one row with all 222 columns required by curated_apps."""
    row = {
        "source_row_key": source_row_key,
        "source_row_number": -1 - i,          # negative to avoid colliding with real data
        "record_hash": f"ih{i}",
        "ingest_run_id": "itest",
        "transform_run_id": "itest",
        "flag_conflicting_label": False,
        "is_malware": i % 2,
    }
    for f in feature_names:
        row[f] = 0
    return row


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _postgres_available(), reason="Postgres not reachable"),
]


@pytest.fixture
def small_df():
    feats = _feature_names()
    rows = [_full_row(i, f"itest:{i}", feats) for i in range(3)]
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def cleanup():
    _cleanup()
    yield
    _cleanup()


def _cleanup():
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM curated_apps WHERE source_row_key LIKE 'itest:%'")
        cur.execute("DELETE FROM pipeline_runs WHERE run_id LIKE 'itest:%'")


def test_upsert_is_idempotent(small_df):
    first = db.upsert_curated_apps(small_df)
    assert first == 3

    second = db.upsert_curated_apps(small_df)
    assert second == 0  # ON CONFLICT DO NOTHING

    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM curated_apps WHERE source_row_key LIKE 'itest:%'")
        assert cur.fetchone()[0] == 3


def test_record_pipeline_run_upserts():
    db.record_pipeline_run("itest:run1", "unit_test", "running", rows_in=10)
    db.record_pipeline_run("itest:run1", "unit_test", "success", rows_in=10, rows_out=10)

    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, rows_out FROM pipeline_runs WHERE run_id = 'itest:run1'")
        status, rows_out = cur.fetchone()
        assert status == "success"
        assert rows_out == 10