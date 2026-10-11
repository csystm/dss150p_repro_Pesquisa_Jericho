"""Publish run outputs into a run-scoped directory and record the run in Postgres."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from src import db

PUBLISH_ARTIFACTS = ["metrics.json", "predictions.csv", "train_summary.json"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Publish outputs to a run-scoped directory.")
    p.add_argument("--run-id", required=True)
    p.add_argument("--outputs-dir", default="outputs")
    p.add_argument("--published-dir", default="outputs/published")
    args = p.parse_args(argv)

    src_dir = Path(args.outputs_dir)
    dest = Path(args.published_dir) / args.run_id
    dest.mkdir(parents=True, exist_ok=True)

    published = []
    for name in PUBLISH_ARTIFACTS:
        s = src_dir / name
        if s.exists():
            shutil.copy2(s, dest / name)
            published.append(name)
            print(f"published {s} -> {dest / name}")

    try:
        db.record_pipeline_run(
            run_id=args.run_id,
            stage="publish_outputs",
            status="success",
            notes=f"published={published}",
        )
    except Exception as exc:
        print(f"warning: could not record pipeline run in postgres: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())