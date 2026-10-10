"""Build a deliberately broken staging fixture for failure-injection evidence.

Two reversible faults are injected into a copy of the real staging data:
  1. A non-binary feature value (transact = 7).
  2. A null in a critical audit column (source_row_key = None).

Row count and feature count are unchanged so only the intended checks fail.
"""
from pathlib import Path
import sys

import pandas as pd


def main() -> int:
    src = Path("data/staging/staging.parquet")
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        return 1

    df = pd.read_parquet(src)

    # Fault 1: non-binary feature value
    df.loc[0, "transact"] = 7

    # Fault 2: null in a required audit column
    df.loc[1, "source_row_key"] = None

    out_dir = Path("outputs/validation/_fixtures")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "staging_bad.parquet"
    df.to_parquet(out_path, index=False)

    print(f"wrote {out_path}")
    print(f"  row 0: transact = {df.loc[0, 'transact']}  (expected 0 or 1)")
    print(f"  row 1: source_row_key = {df.loc[1, 'source_row_key']!r}  (expected string)")
    return 0


if __name__ == "__main__":
    sys.exit(main())