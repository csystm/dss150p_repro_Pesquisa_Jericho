"""Data-quality validation for the DSS150P reproducible pipeline.

Layers: raw, staging, curated.

Each check returns a CheckResult with a severity drawn from the data
contract's violation_behavior map:
    schema: fail         nullability: fail
    invalid_row: quarantine  duplicate_row: warn

Only 'fail' severity checks cause a non-zero exit. 'quarantine' and 'warn'
are logged and carried forward in the report.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from src.storage import read_parquet, write_json
from src.config import get as cfg

EXPECTED_FEATURE_COUNT = int(cfg("data.feature_count", 215))
EXPECTED_ROWS = int(cfg("data.source_expected_rows", 15036))
EXPECTED_TARGET = cfg("data.target_distribution", {"B": 9476, "S": 5560})
EXPECTED_IS_MALWARE = {
    int(k): int(v) for k, v in cfg("data.derived_distribution", {0: 9476, 1: 5560}).items()
}

NON_FEATURE_COLS = {
    "pipeline_run_id", "ingested_at_utc", "source_file", "source_checksum",
    "source_row_number", "source_row_key", "record_hash",
    "ingest_run_id", "transform_run_id", "processed_at_utc",
    "flag_conflicting_label", "class", "is_malware",
}

RAW_REQUIRED = [
    "pipeline_run_id", "ingested_at_utc", "source_file", "source_checksum",
    "source_row_number", "source_row_key", "record_hash", "class",
]
STAGING_REQUIRED = [
    "ingest_run_id", "transform_run_id", "ingested_at_utc", "processed_at_utc",
    "source_file", "source_checksum", "source_row_number", "source_row_key",
    "record_hash", "flag_conflicting_label", "class",
]
CURATED_REQUIRED = [
    "ingest_run_id", "transform_run_id", "source_row_number", "source_row_key",
    "record_hash", "flag_conflicting_label", "is_malware",
]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass
class CheckResult:
    name: str
    category: str
    passed: bool
    severity: str
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class ValidationReport:
    layer: str
    run_id: str
    started_at_utc: str
    finished_at_utc: str
    source_checksum_expected: str | None
    source_checksum_observed: str | None
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "fail")

    @property
    def n_failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "run_id": self.run_id,
            "started_at_utc": self.started_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "source_checksum_expected": self.source_checksum_expected,
            "source_checksum_observed": self.source_checksum_observed,
            "passed": self.passed,
            "n_checks": len(self.checks),
            "n_failed": self.n_failed,
            "checks": [asdict(c) for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_run_id(layer: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"validate_{layer}_{ts}_{uuid.uuid4().hex[:8]}"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


def _read_all_batches(raw_dir: Path) -> pd.DataFrame:
    batch_files = sorted((raw_dir / "batches").glob("batch_*.parquet"))
    if not batch_files:
        raise FileNotFoundError(f"no batch files in {raw_dir / 'batches'}")
    return pd.concat([pd.read_parquet(p) for p in batch_files], ignore_index=True)


# ---------------------------------------------------------------------------
# Generic checks
# ---------------------------------------------------------------------------
def check_schema(df: pd.DataFrame, required: list[str], severity: str) -> CheckResult:
    missing = [c for c in required if c not in df.columns]
    return CheckResult(
        name="schema.required_columns",
        category="schema",
        passed=not missing,
        severity=severity,
        message="all required columns present" if not missing else f"missing {len(missing)} required columns",
        details={"missing": missing, "expected_count": len(required)},
    )


def check_no_nulls(df: pd.DataFrame, critical: list[str], severity: str) -> CheckResult:
    offenders = {c: int(df[c].isna().sum()) for c in critical if c in df.columns}
    offenders = {c: n for c, n in offenders.items() if n > 0}
    return CheckResult(
        name="completeness.no_nulls",
        category="completeness",
        passed=not offenders,
        severity=severity,
        message="no nulls in critical columns" if not offenders else f"nulls in {len(offenders)} column(s)",
        details={"offenders": offenders},
    )


def check_unique_key(df: pd.DataFrame, key: str, severity: str) -> CheckResult:
    if key not in df.columns:
        return CheckResult(
            name=f"uniqueness.{key}", category="uniqueness", passed=False,
            severity=severity, message=f"key '{key}' not present",
            details={"key": key},
        )
    dup = int(df[key].duplicated().sum())
    return CheckResult(
        name=f"uniqueness.{key}",
        category="uniqueness",
        passed=dup == 0,
        severity=severity,
        message="all keys unique" if dup == 0 else f"{dup} duplicate key(s)",
        details={"key": key, "duplicate_count": dup},
    )


def check_binary_features(df: pd.DataFrame, severity: str, name="validity.features_binary") -> CheckResult:
    feats = _feature_columns(df)
    bad: dict[str, list] = {}
    for c in feats:
        vals = set(df[c].dropna().unique().tolist())
        if not vals.issubset({0, 1}):
            bad[c] = sorted(map(str, vals))[:10]
    return CheckResult(
        name=name,
        category="validity",
        passed=not bad,
        severity=severity,
        message=f"all {len(feats)} features are binary" if not bad else f"{len(bad)} feature(s) outside {{0,1}}",
        details={"n_features": len(feats), "violations": bad},
    )


def check_target_values(
    df: pd.DataFrame, col: str, allowed: set, severity: str
) -> CheckResult:
    if col not in df.columns:
        return CheckResult(
            name=f"validity.{col}", category="validity", passed=False,
            severity=severity, message=f"target column '{col}' missing",
        )
    observed = set(df[col].dropna().unique().tolist())
    unexpected = sorted(str(v) for v in observed - allowed)
    return CheckResult(
        name=f"validity.{col}",
        category="validity",
        passed=not unexpected,
        severity=severity,
        message="target values within allowed set" if not unexpected else f"unexpected values: {unexpected}",
        details={"allowed": sorted(map(str, allowed)), "observed": sorted(map(str, observed))},
    )


def check_target_distribution(
    df: pd.DataFrame, col: str, expected: dict, severity: str, tolerance: int = 0
) -> CheckResult:
    if col not in df.columns:
        return CheckResult(
            name=f"consistency.{col}_distribution", category="consistency",
            passed=False, severity=severity,
            message=f"target column '{col}' missing",
        )
    observed = {str(k): int(v) for k, v in df[col].value_counts(dropna=False).to_dict().items()}
    expected_str = {str(k): int(v) for k, v in expected.items()}
    mismatched = {
        k: {"expected": expected_str.get(k, 0), "observed": observed.get(k, 0)}
        for k in set(expected_str) | set(observed)
        if abs(expected_str.get(k, 0) - observed.get(k, 0)) > tolerance
    }
    return CheckResult(
        name=f"consistency.{col}_distribution",
        category="consistency",
        passed=not mismatched,
        severity=severity,
        message="distribution matches contract" if not mismatched else "distribution drift",
        details={"expected": expected_str, "observed": observed, "mismatched": mismatched},
    )


def check_row_count(df: pd.DataFrame, expected: int, severity: str) -> CheckResult:
    ok = len(df) == expected
    return CheckResult(
        name="consistency.row_count",
        category="consistency",
        passed=ok,
        severity=severity,
        message=f"row count {'matches' if ok else 'differs from'} contract",
        details={"expected": expected, "observed": int(len(df))},
    )


def check_feature_count(df: pd.DataFrame, expected: int, severity: str) -> CheckResult:
    feats = _feature_columns(df)
    ok = len(feats) == expected
    return CheckResult(
        name="schema.feature_count",
        category="schema",
        passed=ok,
        severity=severity,
        message=f"{len(feats)} feature columns (expected {expected})",
        details={"expected": expected, "observed": len(feats)},
    )


def check_source_row_number_contiguous(df: pd.DataFrame, severity: str) -> CheckResult:
    if "source_row_number" not in df.columns:
        return CheckResult(
            name="consistency.source_row_number_contiguous",
            category="consistency", passed=False, severity=severity,
            message="source_row_number missing",
        )
    n = len(df)
    observed_min = int(df["source_row_number"].min())
    observed_max = int(df["source_row_number"].max())
    unique_n = int(df["source_row_number"].nunique())
    ok = observed_min == 0 and observed_max == n - 1 and unique_n == n
    return CheckResult(
        name="consistency.source_row_number_contiguous",
        category="consistency",
        passed=ok,
        severity=severity,
        message="source_row_number is 0..n-1 unique" if ok else "source_row_number not contiguous",
        details={
            "n": n, "min": observed_min, "max": observed_max, "unique": unique_n,
        },
    )


def check_source_checksum(
    df: pd.DataFrame, expected: str, severity: str
) -> CheckResult:
    if "source_checksum" not in df.columns:
        return CheckResult(
            name="freshness.source_checksum", category="freshness",
            passed=False, severity=severity, message="source_checksum column missing",
        )
    observed = set(df["source_checksum"].dropna().unique().tolist())
    ok = observed == {expected}
    return CheckResult(
        name="freshness.source_checksum",
        category="freshness",
        passed=ok,
        severity=severity,
        message="all rows carry expected checksum" if ok else "checksum mismatch",
        details={"expected": expected, "observed": sorted(observed)},
    )


def check_no_target_leakage(
    df: pd.DataFrame, severity: str, derived_col: str
) -> CheckResult:
    feats = _feature_columns(df)
    leaked = [c for c in feats if c in {derived_col, "class"}]
    return CheckResult(
        name="predictive_integrity.no_target_leakage",
        category="predictive_integrity",
        passed=not leaked,
        severity=severity,
        message="target excluded from feature set" if not leaked else f"target leaked into features: {leaked}",
        details={"derived_col": derived_col, "leaked": leaked},
    )


# ---------------------------------------------------------------------------
# Layer orchestrators
# ---------------------------------------------------------------------------
def validate_raw(
    raw_dir: Path, contract: dict, expected_checksum: str
) -> ValidationReport:
    sev = contract.get("violation_behavior", {})
    schema_sev = sev.get("schema", "fail")
    null_sev = sev.get("nullability", "fail")
    dup_sev = sev.get("duplicate_row", "warn")
    invalid_sev = sev.get("invalid_row", "quarantine")

    df = _read_all_batches(raw_dir)

    report = ValidationReport(
        layer="raw",
        run_id=_new_run_id("raw"),
        started_at_utc=_utc_now(),
        finished_at_utc="",
        source_checksum_expected=expected_checksum,
        source_checksum_observed=None,
    )
    report.checks.append(check_schema(df, RAW_REQUIRED, schema_sev))
    report.checks.append(check_no_nulls(df, RAW_REQUIRED, null_sev))
    report.checks.append(check_unique_key(df, "source_row_key", dup_sev))
    report.checks.append(check_row_count(df, EXPECTED_ROWS, schema_sev))
    report.checks.append(check_source_checksum(df, expected_checksum, schema_sev))
    report.checks.append(check_target_values(df, "class", set(EXPECTED_TARGET), invalid_sev))
    report.checks.append(check_target_distribution(df, "class", EXPECTED_TARGET, schema_sev))
    report.checks.append(check_source_row_number_contiguous(df, schema_sev))
    report.checks.append(check_feature_count(df, EXPECTED_FEATURE_COUNT, schema_sev))

    observed = df["source_checksum"].dropna().unique().tolist()
    report.source_checksum_observed = observed[0] if len(observed) == 1 else None
    report.finished_at_utc = _utc_now()
    return report


def validate_staging(staging_path: Path, contract: dict, expected_checksum: str) -> ValidationReport:
    sev = contract.get("violation_behavior", {})
    schema_sev = sev.get("schema", "fail")
    null_sev = sev.get("nullability", "fail")
    dup_sev = sev.get("duplicate_row", "warn")
    invalid_sev = sev.get("invalid_row", "quarantine")

    df = read_parquet(staging_path)
    report = ValidationReport(
        layer="staging",
        run_id=_new_run_id("staging"),
        started_at_utc=_utc_now(),
        finished_at_utc="",
        source_checksum_expected=expected_checksum,
        source_checksum_observed=None,
    )
    report.checks.append(check_schema(df, STAGING_REQUIRED, schema_sev))
    report.checks.append(check_no_nulls(df, STAGING_REQUIRED + _feature_columns(df), null_sev))
    report.checks.append(check_unique_key(df, "source_row_key", dup_sev))
    report.checks.append(check_row_count(df, EXPECTED_ROWS, schema_sev))
    report.checks.append(check_feature_count(df, EXPECTED_FEATURE_COUNT, schema_sev))
    report.checks.append(check_binary_features(df, invalid_sev))
    report.checks.append(check_target_values(df, "class", set(EXPECTED_TARGET), invalid_sev))
    report.checks.append(check_target_distribution(df, "class", EXPECTED_TARGET, schema_sev))
    report.checks.append(check_source_row_number_contiguous(df, schema_sev))
    report.checks.append(check_source_checksum(df, expected_checksum, schema_sev))
    report.checks.append(
        CheckResult(
            name="consistency.flag_conflicting_label_is_bool",
            category="consistency",
            passed=df["flag_conflicting_label"].dtype == bool,
            severity=schema_sev,
            message=f"flag dtype = {df['flag_conflicting_label'].dtype}",
        )
    )
    report.finished_at_utc = _utc_now()
    return report


def validate_curated(curated_path: Path, contract: dict) -> ValidationReport:
    sev = contract.get("violation_behavior", {})
    schema_sev = sev.get("schema", "fail")
    null_sev = sev.get("nullability", "fail")
    dup_sev = sev.get("duplicate_row", "warn")
    invalid_sev = sev.get("invalid_row", "quarantine")

    df = read_parquet(curated_path)
    report = ValidationReport(
        layer="curated",
        run_id=_new_run_id("curated"),
        started_at_utc=_utc_now(),
        finished_at_utc="",
        source_checksum_expected=None,
        source_checksum_observed=None,
    )
    report.checks.append(check_schema(df, CURATED_REQUIRED, schema_sev))
    report.checks.append(check_no_nulls(df, _feature_columns(df) + ["is_malware"], null_sev))
    report.checks.append(check_unique_key(df, "source_row_key", dup_sev))
    report.checks.append(check_row_count(df, EXPECTED_ROWS, schema_sev))
    report.checks.append(check_feature_count(df, EXPECTED_FEATURE_COUNT, schema_sev))
    report.checks.append(check_binary_features(df, invalid_sev))
    report.checks.append(check_target_values(df, "is_malware", {0, 1}, invalid_sev))
    report.checks.append(check_target_distribution(df, "is_malware", EXPECTED_IS_MALWARE, schema_sev))
    report.checks.append(check_source_row_number_contiguous(df, schema_sev))
    report.checks.append(check_no_target_leakage(df, schema_sev, derived_col="is_malware"))
    report.checks.append(
        CheckResult(
            name="schema.no_class_column",
            category="schema",
            passed="class" not in df.columns,
            severity=schema_sev,
            message="raw target column absent from curated",
            details={"present": "class" in df.columns},
        )
    )
    report.finished_at_utc = _utc_now()
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_report(report: ValidationReport) -> None:
    print(f"--- {report.layer} validation ({report.run_id}) ---")
    for c in report.checks:
        mark = "PASS" if c.passed else "FAIL"
        print(f"  [{mark}] [{c.severity:10s}] {c.name}: {c.message}")
        if not c.passed and c.details:
            print(f"      details: {c.details}")
    verdict = "PASSED" if report.passed else "FAILED"
    print(f"  VERDICT={verdict} n_checks={len(report.checks)} n_failed={report.n_failed}")


def _write_report(report: ValidationReport, out_dir: Path) -> Path:
    path = out_dir / f"{report.layer}_{report.run_id}.json"
    write_json(report.to_dict(), path)
    return path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Validate pipeline layers against the data contract.")
    p.add_argument("--layer", choices=["raw", "staging", "curated"], required=True)
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--staging-path", default="data/staging/staging.parquet")
    p.add_argument("--curated-path", default="data/curated/curated.parquet")
    p.add_argument("--manifest", default="metadata/source_manifest.yml")
    p.add_argument("--contract", default="metadata/data_contract.yml")
    p.add_argument("--out-dir", default="outputs/validation")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    contract = _load_yaml(Path(args.contract))
    manifest = _load_yaml(Path(args.manifest))
    expected_checksum = manifest["sha256"]

    if args.layer == "raw":
        report = validate_raw(Path(args.raw_dir), contract, expected_checksum)
    elif args.layer == "staging":
        report = validate_staging(Path(args.staging_path), contract, expected_checksum)
    else:
        report = validate_curated(Path(args.curated_path), contract)

    _print_report(report)
    out_path = _write_report(report, Path(args.out_dir))
    print(f"report written: {out_path}")

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())