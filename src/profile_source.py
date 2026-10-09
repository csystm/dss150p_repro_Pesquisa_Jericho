import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def duplicate_audit(df: pd.DataFrame, target_col: str = "class") -> dict:
    """
    Audit duplicates without dropping anything.

    Produces three distinct signals:
      - exact_duplicate_rows: identical across ALL columns (including target)
      - duplicate_feature_rows: identical across FEATURE columns only (target ignored)
      - conflicting_label_groups: feature-vector groups whose target values disagree

    Also reports group-size distributions so we can see whether identical rows
    come in pairs, triples, or larger bundles.
    """
    feature_cols = [c for c in df.columns if c != target_col]

    # --- Exact duplicates (all columns) ---
    exact_dup_mask = df.duplicated(keep=False)
    exact_duplicate_rows = int(df.duplicated(keep=False).sum()) - int(
        df.duplicated(keep="first").sum() * 0
    )  # placeholder replaced below
    # Cleaner, unambiguous counts:
    exact_duplicate_rows_total = int(df.duplicated(keep=False).sum())  # all members of any dup group
    exact_duplicate_rows_extra = int(df.duplicated(keep="first").sum())  # extras beyond first in each group

    # --- Duplicate feature vectors (target ignored) ---
    feat_dup_mask = df.duplicated(subset=feature_cols, keep=False)
    feature_duplicate_rows_total = int(feat_dup_mask.sum())
    feature_duplicate_rows_extra = int(
        df.duplicated(subset=feature_cols, keep="first").sum()
    )

    # --- Group-size distributions ---
    def group_size_distribution(subset_cols):
        sizes = df.groupby(subset_cols, dropna=False).size()
        dist = sizes.value_counts().sort_index()
        return {int(k): int(v) for k, v in dist.items()}

    exact_group_sizes = group_size_distribution(list(df.columns))
    feature_group_sizes = group_size_distribution(feature_cols)

    # --- Conflicting-label groups ---
    work = df.copy()
    grouped = (
        work.groupby(feature_cols, dropna=False)[target_col]
        .agg(["nunique", "size"])
        .reset_index()
    )
    conflicting = grouped[grouped["nunique"] > 1]
    conflicting_groups = int(len(conflicting))
    conflicting_rows = int(conflicting["size"].sum()) if conflicting_groups else 0

    # Sample of conflicting groups for the markdown report (first 10)
    conflicting_samples = []
    if conflicting_groups:
        for _, row in conflicting.head(10).iterrows():
            group_key = {c: row[c] for c in feature_cols}
            labels = (
                df.loc[
                    (df[feature_cols] == pd.Series(group_key)).all(axis=1),
                    target_col,
                ]
                .value_counts()
                .to_dict()
            )
            conflicting_samples.append(
                {"size": int(row["size"]), "label_counts": {str(k): int(v) for k, v in labels.items()}}
            )

    return {
        "exact_duplicate_rows_total": exact_duplicate_rows_total,
        "exact_duplicate_rows_extra": exact_duplicate_rows_extra,
        "exact_duplicate_group_size_distribution": exact_group_sizes,
        "duplicate_feature_rows_total": feature_duplicate_rows_total,
        "duplicate_feature_rows_extra": feature_duplicate_rows_extra,
        "feature_duplicate_group_size_distribution": feature_group_sizes,
        "conflicting_label_groups": conflicting_groups,
        "conflicting_label_rows": conflicting_rows,
        "conflicting_label_samples": conflicting_samples,
    }


def profile_dataframe(df: pd.DataFrame, target_col: str = "class") -> dict:
    profile = {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "column_names": df.columns.tolist(),
        "null_counts": {c: int(df[c].isna().sum()) for c in df.columns},
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "unique_counts": {c: int(df[c].nunique(dropna=False)) for c in df.columns},
        "target": {},
        "columns_summary": [],
        "duplicates": duplicate_audit(df, target_col=target_col),
    }

    if target_col in df.columns:
        vc = df[target_col].value_counts(dropna=False)
        profile["target"] = {
            "column": target_col,
            "value_counts": {str(k): int(v) for k, v in vc.items()},
            "distribution": {str(k): float(v / len(df)) for k, v in vc.items()},
        }

    for c in df.columns:
        s = df[c]
        item = {
            "column": c,
            "dtype": str(s.dtype),
            "null_count": int(s.isna().sum()),
            "null_rate": float(s.isna().mean()),
            "unique_count": int(s.nunique(dropna=False)),
            "min": None,
            "max": None,
            "example_values": s.dropna().astype(str).unique()[:10].tolist(),
        }
        if pd.api.types.is_numeric_dtype(s):
            non_null = s.dropna()
            if not non_null.empty:
                item["min"] = float(non_null.min())
                item["max"] = float(non_null.max())
        profile["columns_summary"].append(item)

    return profile


def write_markdown(profile: dict, manifest: dict, path: Path) -> None:
    lines = []
    lines.append("# Source Profile\n")
    lines.append(f"Generated at: `{manifest['generated_at_utc']}`\n")

    lines.append("## Identity")
    lines.append(f"- Source file: `{manifest['source_file']}`")
    lines.append(f"- Relative path: `{manifest['source_path_relative']}`")
    lines.append(f"- SHA-256: `{manifest['sha256']}`")
    lines.append(f"- Size (bytes): {manifest['size_bytes']}")
    lines.append(f"- Rows: {profile['rows']}")
    lines.append(f"- Columns: {profile['columns']}")
    lines.append("")

    lines.append("## Target")
    if profile.get("target"):
        t = profile["target"]
        lines.append(f"- Target column: `{t['column']}`")
        lines.append("- Value counts:")
        for k, v in t["value_counts"].items():
            lines.append(f"  - `{k}`: {v} ({t['distribution'][k]:.6f})")
    lines.append("")

    d = profile["duplicates"]
    lines.append("## Duplicate audit")
    lines.append("")
    lines.append("**Interpretation.** One source row is treated as one app observation. "
                 "Two apps can legitimately share the same 215 binary flags, so identical "
                 "feature vectors are not automatically duplicates. The default policy is "
                 "to KEEP all rows to preserve the baseline population. Nothing is dropped "
                 "at profile time.")
    lines.append("")
    lines.append("### Exact duplicates (all columns, including target)")
    lines.append(f"- Rows that are members of any exact-duplicate group: `{d['exact_duplicate_rows_total']}`")
    lines.append(f"- Rows beyond the first in each group (i.e. would be dropped by `drop_duplicates()`): `{d['exact_duplicate_rows_extra']}`")
    lines.append(f"- Group-size distribution: `{d['exact_duplicate_group_size_distribution']}`")
    lines.append("")
    lines.append("### Duplicate feature vectors (target ignored)")
    lines.append(f"- Rows that are members of any duplicate-feature-vector group: `{d['duplicate_feature_rows_total']}`")
    lines.append(f"- Rows beyond the first in each group: `{d['duplicate_feature_rows_extra']}`")
    lines.append(f"- Group-size distribution: `{d['feature_duplicate_group_size_distribution']}`")
    lines.append("")
    lines.append("### Conflicting labels for identical feature vectors")
    lines.append(f"- Groups with disagreeing labels: `{d['conflicting_label_groups']}`")
    lines.append(f"- Rows involved in those groups: `{d['conflicting_label_rows']}`")
    if d["conflicting_label_samples"]:
        lines.append("")
        lines.append("Sample conflicting groups (first up to 10):")
        lines.append("")
        lines.append("| group_size | label_counts |")
        lines.append("|---:|---|")
        for s in d["conflicting_label_samples"]:
            lines.append(f"| {s['size']} | {s['label_counts']} |")
    lines.append("")
    lines.append("**Policy.** These rows are **not** dropped or reassigned at profile time. "
                 "The data contract declares how the pipeline behaves: keep, drop, or quarantine. "
                 "Default is `keep` to preserve baseline reproduction. Any deviation must be "
                 "declared in `metadata/data_contract.yml` and reflected in the reproducibility report.")
    lines.append("")

    lines.append("## Column summary")
    lines.append("| column | dtype | null_count | null_rate | unique_count | min | max | example_values |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for c in profile["columns_summary"]:
        ex = ", ".join(c["example_values"][:5])
        lines.append(
            f"| `{c['column']}` | {c['dtype']} | {c['null_count']} | "
            f"{c['null_rate']:.4f} | {c['unique_count']} | {c['min']} | {c['max']} | {ex} |"
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile the immutable source dataset.")
    parser.add_argument(
        "--source",
        default=os.environ.get("SOURCE_DATA_PATH", "data/source/drebin_dataset.csv"),
        help="Path to source CSV.",
    )
    parser.add_argument(
        "--metadata-dir",
        default="metadata",
        help="Directory for source_manifest.yml, source_profile.md, source_profile.json.",
    )
    parser.add_argument(
        "--target-col",
        default="class",
        help="Target column name.",
    )
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"ERROR: source dataset not found: {source}", file=sys.stderr)
        sys.exit(1)

    metadata_dir = Path(args.metadata_dir)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    checksum = sha256_file(source)
    size_bytes = source.stat().st_size

    df = pd.read_csv(
        source,
        dtype={"TelephonyManager.getSimCountryIso": "string"},
        low_memory=False,
    )
    profile = profile_dataframe(df, target_col=args.target_col)

    try:
        rel_source = source.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        rel_source = source.name

    manifest = {
        "source_file": source.name,
        "source_path_relative": rel_source,
        "sha256": checksum,
        "size_bytes": size_bytes,
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "target_column": args.target_col,
        "target_values": sorted(df[args.target_col].dropna().unique().tolist())
            if args.target_col in df.columns else [],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "duplicate_audit": profile["duplicates"],  # pinned at manifest time too
    }

    with open(metadata_dir / "source_manifest.yml", "w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, sort_keys=False)

    with open(metadata_dir / "source_profile.json", "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, default=str)

    write_markdown(profile, manifest, metadata_dir / "source_profile.md")

    print(f"Wrote {metadata_dir / 'source_manifest.yml'}")
    print(f"Wrote {metadata_dir / 'source_profile.md'}")
    print(f"Wrote {metadata_dir / 'source_profile.json'}")
    print("")
    print("Duplicate audit summary:")
    print(f"  exact duplicate rows (extra):     {profile['duplicates']['exact_duplicate_rows_extra']}")
    print(f"  duplicate feature rows (extra):   {profile['duplicates']['duplicate_feature_rows_extra']}")
    print(f"  conflicting-label groups:         {profile['duplicates']['conflicting_label_groups']}")
    print(f"  conflicting-label rows:           {profile['duplicates']['conflicting_label_rows']}")


if __name__ == "__main__":
    main()