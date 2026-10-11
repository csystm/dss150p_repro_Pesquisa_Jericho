"""Shared pytest fixtures for the DSS150P test suite."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Make `src` importable when pytest is invoked from the repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def toy_raw_df():
    """Minimal raw-shaped DataFrame with audit columns and one mixed-type column."""
    rows = [
        # audit cols first (matching ingest output order)
        {
            "pipeline_run_id": "run_test",
            "ingested_at_utc": "2026-01-01T00:00:00+00:00",
            "source_file": "toy.csv",
            "source_checksum": "deadbeef",
            "source_row_number": 0,
            "source_row_key": "toy:row:0",
            "record_hash": "h0",
            "transact": 1, "INTERNET": 1, "SEND_SMS": 0,
            "TelephonyManager.getSimCountryIso": "1",
            "class": "S",
        },
        {
            "pipeline_run_id": "run_test",
            "ingested_at_utc": "2026-01-01T00:00:00+00:00",
            "source_file": "toy.csv",
            "source_checksum": "deadbeef",
            "source_row_number": 1,
            "source_row_key": "toy:row:1",
            "record_hash": "h1",
            "transact": 0, "INTERNET": 0, "SEND_SMS": 0,
            "TelephonyManager.getSimCountryIso": "?",
            "class": "B",
        },
        {
            "pipeline_run_id": "run_test",
            "ingested_at_utc": "2026-01-01T00:00:00+00:00",
            "source_file": "toy.csv",
            "source_checksum": "deadbeef",
            "source_row_number": 2,
            "source_row_key": "toy:row:2",
            "record_hash": "h2",
            "transact": 0, "INTERNET": 0, "SEND_SMS": 0,
            "TelephonyManager.getSimCountryIso": "0",
            "class": "S",
        },
    ]
    return pd.DataFrame(rows)