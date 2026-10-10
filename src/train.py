"""Deterministic training for the DSS150P reproducible pipeline.

Reads:  data/curated/curated.parquet
Writes: metadata/split_manifest.json
        outputs/model/<slug>.joblib
        outputs/train_summary.json

Model families, hyperparameters, and CV strategy mirror the DSS141P baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import loguniform, randint, uniform
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.model_selection import (
    RandomizedSearchCV, RepeatedStratifiedKFold, train_test_split,
)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

from src.storage import read_parquet, write_json

SEED = 246112165
TEST_SIZE = 0.2
TARGET_COL = "is_malware"

NON_FEATURE_COLS = {
    "ingest_run_id", "transform_run_id", "source_row_number",
    "source_row_key", "record_hash", "flag_conflicting_label",
    TARGET_COL,
}


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
def set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    # PYTHONHASHSEED must be set before interpreter start.
    # README documents: PYTHONHASHSEED=246112165 python -m src.train


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


# ---------------------------------------------------------------------------
# Split + manifest
# ---------------------------------------------------------------------------
def _key_checksum(keys) -> str:
    h = hashlib.sha256()
    for k in sorted(keys):
        h.update(str(k).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def make_split(df: pd.DataFrame):
    feats = feature_columns(df)
    X = df[feats].copy()
    y = df[TARGET_COL].copy()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=SEED, stratify=y
    )
    return X_train, X_test, y_train, y_test


def save_split_manifest(df, X_train, X_test, y_train, y_test, path: Path) -> dict:
    train_keys = df.loc[X_train.index, "source_row_key"].tolist()
    test_keys = df.loc[X_test.index, "source_row_key"].tolist()
    train_nums = sorted(df.loc[X_train.index, "source_row_number"].astype(int).tolist())
    test_nums = sorted(df.loc[X_test.index, "source_row_number"].astype(int).tolist())

    manifest = {
        "method": "stratified_random",
        "seed": SEED,
        "test_size": TEST_SIZE,
        "row_counts": {
            "total": int(len(df)),
            "train": int(len(X_train)),
            "test": int(len(X_test)),
        },
        "class_distribution": {
            "train": {str(k): int(v) for k, v in y_train.value_counts().to_dict().items()},
            "test":  {str(k): int(v) for k, v in y_test.value_counts().to_dict().items()},
        },
        "source_row_key_checksums": {
            "train_sha256": _key_checksum(train_keys),
            "test_sha256":  _key_checksum(test_keys),
        },
        "train_source_row_numbers": train_nums,
        "test_source_row_numbers":  test_nums,
    }
    write_json(manifest, path)
    return manifest


# ---------------------------------------------------------------------------
# Model builders
# ---------------------------------------------------------------------------
def build_lr_baseline():
    return LogisticRegression(
        penalty="l2", solver="liblinear", C=1.0,
        max_iter=1000, random_state=SEED,
    )


def build_lr_l2():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("logistic", LogisticRegressionCV(
            penalty="l2", solver="lbfgs",
            Cs=20, cv=5, scoring="roc_auc",
            max_iter=1000, random_state=SEED, n_jobs=-1,
        )),
    ])


def build_lr_l1():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("logistic", LogisticRegressionCV(
            penalty="l1", solver="liblinear",
            Cs=20, cv=5, scoring="roc_auc",
            max_iter=1000, random_state=SEED, n_jobs=-1,
        )),
    ])


def build_rf_search(cv):
    rf = RandomForestClassifier(random_state=SEED, n_jobs=-1)
    param = {
        "n_estimators": randint(100, 300),
        "max_depth": [10, 20, 30],
        "min_samples_split": [2, 5, 10, 20],
        "max_features": ["sqrt", "log2"],
    }
    return RandomizedSearchCV(
        rf, param, n_iter=50, cv=cv, scoring="roc_auc",
        n_jobs=-1, random_state=SEED,
    )


def build_xgb_search(cv, y_train):
    scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
    xgb_model = xgb.XGBClassifier(
        objective="binary:logistic", eval_metric="auc",
        random_state=SEED, n_jobs=-1,
    )
    param = {
        "n_estimators": randint(100, 500),
        "max_depth": randint(3, 10),
        "learning_rate": loguniform(0.01, 0.3),
        "subsample": uniform(0.6, 0.4),
        "colsample_bytree": uniform(0.6, 0.4),
        "scale_pos_weight": [scale_pos_weight, 1.0],
    }
    return RandomizedSearchCV(
        xgb_model, param, n_iter=50, cv=cv, scoring="roc_auc",
        n_jobs=-1, random_state=SEED,
    )


def build_mlp_search(cv):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPClassifier(random_state=SEED, early_stopping=True, max_iter=500)),
    ])
    param = {
        "mlp__hidden_layer_sizes": [(64,), (128,), (64, 32), (128, 64)],
        "mlp__activation": ["relu", "tanh"],
        "mlp__alpha": loguniform(1e-5, 1e-1),
        "mlp__learning_rate_init": loguniform(1e-4, 1e-2),
        "mlp__batch_size": [32, 64, 128],
    }
    return RandomizedSearchCV(
        pipe, param, n_iter=40, cv=cv, scoring="roc_auc",
        n_jobs=-1, random_state=SEED,
    )


# ---------------------------------------------------------------------------
# Training dispatch
# ---------------------------------------------------------------------------
MODEL_NAMES = ["LR baseline", "LR L2", "LR L1", "Random Forest", "XGBoost", "MLP"]


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def train_models(X_train, y_train, models_to_run: list[str] | None = None) -> dict:
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=1, random_state=SEED)
    results: dict = {}
    selected = models_to_run or MODEL_NAMES

    if "LR baseline" in selected:
        print("[fit] LR baseline")
        m = build_lr_baseline(); m.fit(X_train, y_train)
        results["LR baseline"] = m

    if "LR L2" in selected:
        print("[fit] LR L2 (LogisticRegressionCV)")
        m = build_lr_l2(); m.fit(X_train, y_train)
        print(f"  best C = {m.named_steps['logistic'].C_[0]:.4f}")
        results["LR L2"] = m

    if "LR L1" in selected:
        print("[fit] LR L1 (LogisticRegressionCV)")
        m = build_lr_l1(); m.fit(X_train, y_train)
        print(f"  best C = {m.named_steps['logistic'].C_[0]:.4f}")
        results["LR L1"] = m

    if "Random Forest" in selected:
        print("[fit] Random Forest (n_iter=50)")
        s = build_rf_search(cv); s.fit(X_train, y_train)
        print(f"  best: {s.best_params_}  cv AUC={s.best_score_:.4f}")
        results["Random Forest"] = s.best_estimator_

    if "XGBoost" in selected:
        print("[fit] XGBoost (n_iter=50)")
        s = build_xgb_search(cv, y_train); s.fit(X_train, y_train)
        print(f"  best: {s.best_params_}  cv AUC={s.best_score_:.4f}")
        results["XGBoost"] = s.best_estimator_

    if "MLP" in selected:
        print("[fit] MLP (n_iter=40)")
        s = build_mlp_search(cv); s.fit(X_train, y_train)
        print(f"  best: {s.best_params_}  cv AUC={s.best_score_:.4f}")
        results["MLP"] = s.best_estimator_

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_train(curated_path: Path, model_dir: Path, manifest_path: Path,
              summary_path: Path, models_to_run: list[str] | None = None) -> dict:
    set_seeds(SEED)
    train_run_id = "train_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") \
                   + "_" + uuid.uuid4().hex[:8]

    df = read_parquet(curated_path)
    X_train, X_test, y_train, y_test = make_split(df)
    print(f"split: train={len(X_train)} test={len(X_test)}")

    manifest = save_split_manifest(df, X_train, X_test, y_train, y_test, manifest_path)

    models = train_models(X_train, y_train, models_to_run)

    model_dir.mkdir(parents=True, exist_ok=True)
    model_paths = {}
    for name, m in models.items():
        p = model_dir / f"{_slug(name)}.joblib"
        joblib.dump(m, p)
        model_paths[name] = str(p)
        print(f"  saved {p}")

    summary = {
        "train_run_id": train_run_id,
        "seed": SEED,
        "test_size": TEST_SIZE,
        "models_trained": list(models.keys()),
        "model_paths": model_paths,
        "split_manifest": str(manifest_path),
        "class_distribution": manifest["class_distribution"],
    }
    write_json(summary, summary_path)
    return summary


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Deterministic model training.")
    p.add_argument("--curated-path", default="data/curated/curated.parquet")
    p.add_argument("--model-dir", default="outputs/model")
    p.add_argument("--manifest-path", default="metadata/split_manifest.json")
    p.add_argument("--summary-path", default="outputs/train_summary.json")
    p.add_argument("--models", nargs="+", default=None, choices=MODEL_NAMES,
                   help="Train only these models (default: all).")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        summary = run_train(
            curated_path=Path(args.curated_path),
            model_dir=Path(args.model_dir),
            manifest_path=Path(args.manifest_path),
            summary_path=Path(args.summary_path),
            models_to_run=args.models,
        )
    except Exception as exc:
        import traceback; traceback.print_exc()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"trained {len(summary['models_trained'])} models, run_id={summary['train_run_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())