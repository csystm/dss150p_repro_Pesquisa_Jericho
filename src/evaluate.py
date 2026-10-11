"""Deterministic evaluation for the DSS150P reproducible pipeline.

Reads:  data/curated/curated.parquet, metadata/split_manifest.json,
        outputs/model/*.joblib, metadata/expected_metrics.json
Writes: outputs/metrics.json, outputs/predictions.csv
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import (
    accuracy_score, average_precision_score, f1_score, log_loss,
    precision_score, recall_score, roc_auc_score,
)

from src.storage import read_parquet, write_csv, write_json

TARGET_COL = "is_malware"
TOLERANCE_DEFAULT = 0.01
PRIMARY_METRIC_DEFAULT = "f1"

NON_FEATURE_COLS = {
    "ingest_run_id", "transform_run_id", "source_row_number",
    "source_row_key", "record_hash", "flag_conflicting_label",
    TARGET_COL,
}


def feature_columns(df): return [c for c in df.columns if c not in NON_FEATURE_COLS]


def reconstruct_test(df: pd.DataFrame, manifest: dict) -> pd.DataFrame:
    test_nums = set(manifest["test_source_row_numbers"])
    mask = df["source_row_number"].astype(int).isin(test_nums)
    test = df.loc[mask].sort_values("source_row_number").reset_index(drop=True)
    expected = manifest["row_counts"]["test"]
    if len(test) != expected:
        raise ValueError(f"test reconstruction: got {len(test)}, expected {expected}")
    return test


def evaluate_model(model, X_test, y_test):
    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)
    return {
        "accuracy":  float(accuracy_score(y_test, pred)),
        "precision": float(precision_score(y_test, pred)),
        "recall":    float(recall_score(y_test, pred)),
        "f1":        float(f1_score(y_test, pred)),
        "roc_auc":   float(roc_auc_score(y_test, proba)),
        "pr_auc":    float(average_precision_score(y_test, proba)),
        "log_loss":  float(log_loss(y_test, proba)),
    }, proba


def compare_to_expected(actual, expected, tolerance, primary):
    row = {}
    for metric, exp_val in expected.items():
        if metric not in actual:
            continue
        delta = actual[metric] - exp_val
        row[metric] = {
            "expected": float(exp_val),
            "actual": float(actual[metric]),
            "delta": float(delta),
            "within_tolerance": abs(delta) <= tolerance,
        }
    primary_row = row.get(primary)
    overall = bool(primary_row and primary_row["within_tolerance"])
    return row, overall


def run_evaluate(curated_path: Path, manifest_path: Path, model_dir: Path,
                 expected_metrics_path: Path, metrics_out: Path,
                 predictions_out: Path, tolerance: float, primary_metric: str) -> dict:
    eval_run_id = "evaluate_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") \
                  + "_" + uuid.uuid4().hex[:8]

    df = read_parquet(curated_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    expected = json.loads(Path(expected_metrics_path).read_text(encoding="utf-8"))
    expected_models = expected.get("models", {})

    test = reconstruct_test(df, manifest)
    feats = feature_columns(df)
    X_test = test[feats]
    y_test = test[TARGET_COL]
    print(f"evaluation set: rows={len(test)} positives={int(y_test.sum())}")

    model_files = sorted(model_dir.glob("*.joblib"))
    if not model_files:
        raise FileNotFoundError(f"no model files under {model_dir}")

    metrics_by_model = {}
    prediction_frames = []

    for p in model_files:
        # Map slug back to display name via expected_models keys
        candidates = [k for k in expected_models
                      if k.lower().replace(" ", "_") == p.stem]
        display_name = candidates[0] if candidates else p.stem
        model = joblib.load(p)
        metrics, proba = evaluate_model(model, X_test, y_test)
        metrics_by_model[display_name] = metrics
        prediction_frames.append(pd.DataFrame({
            "model":          display_name,
            "source_row_key": test["source_row_key"].values,
            "y_true":         y_test.values,
            "y_prob":         proba,
            "y_pred":         (proba >= 0.5).astype(int),
        }))

    comparison, reproducibility_passed, failures = {}, True, []
    for name, m in metrics_by_model.items():
        if name not in expected_models:
            continue
        row, ok = compare_to_expected(m, expected_models[name], tolerance, primary_metric)
        comparison[name] = row
        if not ok:
            reproducibility_passed = False
            failures.append({
                "model": name, "metric": primary_metric,
                "expected": row[primary_metric]["expected"],
                "actual":   row[primary_metric]["actual"],
                "delta":    row[primary_metric]["delta"],
            })

    payload = {
        "evaluate_run_id": eval_run_id,
        "primary_metric": primary_metric,
        "tolerance": tolerance,
        "model_metrics": metrics_by_model,
        "vs_expected": comparison,
        "reproducibility": {"passed": reproducibility_passed, "failures": failures},
    }
    write_json(payload, metrics_out)
    write_csv(pd.concat(prediction_frames, ignore_index=True), predictions_out)
    return payload


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Evaluate trained models against baseline.")
    p.add_argument("--curated-path", default="data/curated/curated.parquet")
    p.add_argument("--manifest-path", default="metadata/split_manifest.json")
    p.add_argument("--model-dir", default="outputs/model")
    p.add_argument("--expected-metrics", default="metadata/expected_metrics.json")
    p.add_argument("--metrics-out", default="outputs/metrics.json")
    p.add_argument("--predictions-out", default="outputs/predictions.csv")
    p.add_argument("--tolerance", type=float, default=TOLERANCE_DEFAULT)
    p.add_argument("--primary-metric", default=PRIMARY_METRIC_DEFAULT)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        payload = run_evaluate(
            curated_path=Path(args.curated_path),
            manifest_path=Path(args.manifest_path),
            model_dir=Path(args.model_dir),
            expected_metrics_path=Path(args.expected_metrics),
            metrics_out=Path(args.metrics_out),
            predictions_out=Path(args.predictions_out),
            tolerance=args.tolerance,
            primary_metric=args.primary_metric,
        )
    except Exception as exc:
        import traceback; traceback.print_exc()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for name, m in payload["model_metrics"].items():
        print(f"{name}:")
        print(f"  accuracy={m['accuracy']:.4f} precision={m['precision']:.4f} "
              f"recall={m['recall']:.4f} f1={m['f1']:.4f}")
        print(f"  roc_auc={m['roc_auc']:.4f} pr_auc={m['pr_auc']:.4f} log_loss={m['log_loss']:.4f}")
        vs = payload["vs_expected"].get(name, {})
        pm = payload["primary_metric"]
        if pm in vs:
            v = vs[pm]
            print(f"  {pm} vs expected: {v['actual']:.4f} vs {v['expected']:.4f} "
                  f"(delta={v['delta']:+.4f}, within_tolerance={v['within_tolerance']})")
    print(f"reproducibility_passed={payload['reproducibility']['passed']}")
    # evaluate is a measurement, not a gate. The gate is reproducibility_check.
    return 0


if __name__ == "__main__":
    sys.exit(main())