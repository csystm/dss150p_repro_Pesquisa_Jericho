"""PostgreSQL I/O for the DSS150P reproducible pipeline.

Responsibilities
----------------
- Load connection settings from environment (via .env).
- Retry connection until Postgres is ready (compose healthcheck races are real).
- Upsert curated rows with INSERT ... ON CONFLICT (source_row_key) DO NOTHING,
  so reruns never duplicate logical records.
- Record pipeline-run audit rows.
- Persist evaluation metrics snapshots.

The upsert uses psycopg2.extras.execute_values for batched inserts.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Iterator

import numpy as np
import pandas as pd
import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import execute_values

AUDIT_COLS = {
    "source_row_key", "source_row_number", "record_hash",
    "ingest_run_id", "transform_run_id", "flag_conflicting_label",
    "is_malware",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn_kwargs() -> dict:
    return {
        "host":     os.environ.get("POSTGRES_HOST", "localhost"),
        "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname":   os.environ.get("POSTGRES_DB", "dss150p"),
        "user":     os.environ.get("POSTGRES_USER", "dss150p_user"),
        "password": os.environ.get("POSTGRES_PASSWORD", "change_me"),
    }


def wait_for_postgres(max_attempts: int = 30, delay: float = 1.0) -> None:
    """Block until Postgres accepts connections or raise."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with psycopg2.connect(**_conn_kwargs()) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(delay)
    raise RuntimeError(f"Postgres not reachable after {max_attempts} attempts: {last_error}")


@contextmanager
def connection() -> Iterator[psycopg2.extensions.connection]:
    conn = psycopg2.connect(**_conn_kwargs())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Curated upsert
# ---------------------------------------------------------------------------
def _quote(col: str) -> str:
    return '"' + col.replace('"', '""') + '"'


def _to_native_records(df: pd.DataFrame) -> list[tuple]:
    """Convert a DataFrame into a list of tuples whose values are Python-native
    scalars. psycopg2 can adapt Python int/float/bool/str/None; it cannot adapt
    numpy scalars or pandas NA sentinels.
    """
    out = df.copy()

    for col in out.columns:
        s = out[col]

        # Strings: pandas 3 "string" dtype -> Python str objects
        if pd.api.types.is_string_dtype(s) or s.dtype == "object":
            out[col] = s.astype(object).where(pd.notna(s), None)
            continue

        if pd.api.types.is_bool_dtype(s):
            out[col] = s.astype(bool).astype(object)
            continue

        if pd.api.types.is_integer_dtype(s):
            # Nullable Int64 -> float has NaN; regular int64 has no NA.
            if s.isna().any():
                out[col] = s.astype("float64").astype(object)
            else:
                out[col] = s.astype("int64").astype(object)
            continue

        if pd.api.types.is_float_dtype(s):
            out[col] = s.astype("float64").astype(object)
            continue

        # Fallback: cast to object and replace NA with None
        out[col] = s.astype(object).where(pd.notna(s), None)

    # Drop to plain tuples of Python objects
    return [tuple(r) for r in out.itertuples(index=False, name=None)]


def upsert_curated_apps(df: pd.DataFrame, batch_size: int = 5000) -> int:
    """Insert curated rows; skip rows whose source_row_key already exists.

    Returns the number of rows actually inserted (not counting skips).
    """
    if df.empty:
        return 0

    cols = list(df.columns)
    col_sql = ", ".join(_quote(c) for c in cols)
    sql = (
        f"INSERT INTO curated_apps ({col_sql}) VALUES %s "
        f"ON CONFLICT (source_row_key) DO NOTHING"
    )

    records = _to_native_records(df)

    inserted = 0
    with connection() as conn:
        with conn.cursor() as cur:
            for start in range(0, len(records), batch_size):
                chunk = records[start : start + batch_size]
                execute_values(cur, sql, chunk, page_size=len(chunk))
                inserted += cur.rowcount
    return inserted


# ---------------------------------------------------------------------------
# Audit + metrics
# ---------------------------------------------------------------------------
def record_pipeline_run(
    run_id: str,
    stage: str,
    status: str,
    rows_in: int | None = None,
    rows_out: int | None = None,
    started_at_utc: str | None = None,
    notes: str | None = None,
) -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline_runs
                    (run_id, stage, started_at_utc, finished_at_utc,
                     status, rows_in, rows_out, notes)
                VALUES (%s, %s, COALESCE(%s::timestamptz, now()), now(),
                        %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    stage          = EXCLUDED.stage,
                    finished_at_utc= EXCLUDED.finished_at_utc,
                    status         = EXCLUDED.status,
                    rows_in        = EXCLUDED.rows_in,
                    rows_out       = EXCLUDED.rows_out,
                    notes          = EXCLUDED.notes
                """,
                (run_id, stage, started_at_utc, status, rows_in, rows_out, notes),
            )


def load_model_metrics(evaluate_run_id: str, metrics_by_model: dict) -> int:
    """Persist per-model metric rows. metrics_by_model: {model: {metric: value}}."""
    rows = []
    for model, metrics in metrics_by_model.items():
        for metric, value in metrics.items():
            rows.append((evaluate_run_id, model, metric, float(value)))
    if not rows:
        return 0
    with connection() as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO model_metrics
                    (evaluate_run_id, model, metric, value)
                VALUES %s
                ON CONFLICT (evaluate_run_id, model, metric) DO UPDATE SET
                    value = EXCLUDED.value,
                    loaded_at_utc = now()
                """,
                rows,
            )
    return len(rows)


# ---------------------------------------------------------------------------
# Read helpers used by the benchmark
# ---------------------------------------------------------------------------
def count_curated_rows() -> int:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM curated_apps")
            return int(cur.fetchone()[0])


def read_curated_to_df() -> pd.DataFrame:
    import pandas as pd
    with connection() as conn:
        return pd.read_sql_query("SELECT * FROM curated_apps ORDER BY source_row_number", conn)