"""Load curated dataset into PostgreSQL with rerun-safe upsert."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src import db
from src.storage import read_parquet


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Load curated data into Postgres.")
    p.add_argument("--curated-path", default="data/curated/curated.parquet")
    args = p.parse_args(argv)

    df = read_parquet(Path(args.curated_path))
    df = df.sort_values("source_row_number", kind="mergesort").reset_index(drop=True)

    db.wait_for_postgres()
    inserted = db.upsert_curated_apps(df)
    total = db.count_curated_rows()
    print(f"postgres: rows_in_df={len(df)} rows_inserted={inserted} total_in_table={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())