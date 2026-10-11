"""Fail if regenerated metrics are outside the declared tolerance of the baseline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Reproducibility tolerance check.")
    p.add_argument("--metrics", default="outputs/metrics.json")
    args = p.parse_args(argv)

    payload = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    rep = payload.get("reproducibility", {})
    primary = payload.get("primary_metric")
    tolerance = payload.get("tolerance")

    print(f"primary={primary} tolerance={tolerance}")
    for model, row in payload.get("vs_expected", {}).items():
        if primary not in row:
            continue
        v = row[primary]
        print(
            f"  {model:16s} {primary}={v['actual']:.4f} "
            f"expected={v['expected']:.4f} delta={v['delta']:+.4f} "
            f"within_tolerance={v['within_tolerance']}"
        )

    if rep.get("passed"):
        print("REPRODUCIBILITY PASSED")
        return 0
    print("REPRODUCIBILITY FAILED")
    for f in rep.get("failures", []):
        print(f"  FAIL {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())