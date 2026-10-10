"""Storage I/O helpers for the DSS150P pipeline.

Kept deliberately narrow for now: Parquet read/write with a temp-file pattern
so a crash mid-write cannot leave a partially written artifact at the target
path. CSV/JSON/PostgreSQL helpers will be added in the storage benchmark phase.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(Path(path))


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def write_jsonl(df: pd.DataFrame, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_json(tmp, orient="records", lines=True)
    tmp.replace(path)