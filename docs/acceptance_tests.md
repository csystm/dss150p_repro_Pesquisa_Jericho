# Acceptance Test Results

Snapshot: 2026-10-11. Image `dss150p-repro:pipeline`. Host: Windows 11 + Docker
Desktop on WSL2, 16 GB RAM.

Reference: Section 11 of the DSS150P laboratory brief.

| ID | Test | Result | Evidence |
|---|---|---|---|
| A1 | Repository clones; README setup sufficient | PASS | `README.md` §7; git history |
| A2 | Source identity verifiable by checksum | PASS | `metadata/source_manifest.yml` sha256 = `710f2c11...3ad5`; `tests/test_data_contract.py::test_manifest_checksum_matches_source_on_disk` |
| A3 | No machine-specific absolute paths | PASS | `grep -rn "C:\\\\\|/Users/" src/ dags/ sql/` returns nothing |
| A4 | No secrets committed | PASS | `.env` in `.gitignore`; `git log --all --full-history -- .env` returns nothing |
| A5 | Environment from declared dependencies | PASS | `docker compose build pipeline` succeeds; `requirements.txt` pinned |
| A6 | Full ingestion produces expected count | PASS | 3 batch files, 15036 rows total; `ingest.py` first-run log |
| A7 | Incremental run avoids duplicates | PASS | `docs/evidence/ingest_recovery_part1.txt`, `part2.txt`; `source_row_key` unique = 15036 |
| A8 | Staging/curated produced deterministically | PASS | `metadata/split_manifest.json`; `tests/test_unit_transform.py` |
| A9 | Postgres load rerun-safe | PASS | `tests/test_integration_postgres.py::test_upsert_is_idempotent`; second load inserts 0 |
| A10 | All four formats carry same logical records | PASS | `docs/benchmark_report.md` `keys_checksum`; `docs/evidence/benchmark.json` |
| A11 | Selected partition read independently | PASS | `outputs/benchmark/partitioned/is_malware=0.parquet` reads 9476 rows |
| A12 | Airflow DAG valid and completes | PASS | `docs/evidence/airflow_run_completed.txt`; `airflow_run_all_models.png` |
| A13 | At least one recoverable failure demonstrated | PASS | `docs/evidence/airflow_failure_recovery.txt` |
| A14 | Quality checks detect invalid conditions | PASS | `docs/evidence/validation_failure_injection.txt` |
| A15 | Second run no duplicate business keys | PASS | `test_upsert_is_idempotent`; `count(distinct source_row_key)` = 15036 |
| A16 | Metrics regenerated from curated, not copied | PASS | `outputs/metrics.json` written by `evaluate_model`; `tests/test_unit_train.py::test_make_split_deterministic` |
| A17 | Reproduced metric passes tolerance | PASS | `outputs/metrics.json` `reproducibility.passed=true`; `docs/evidence/metrics_all_models.json` |
| A18 | Diagrams, runbook, report present and consistent | PASS | `docs/architecture.md`, `docs/lineage.md`, `docs/runbook.md`, `docs/reproducibility_report.md` |

## Notes

- A2: SHA-256 pin matches the raw file on disk. The file is committed unchanged
  under CC BY 4.0; attribution in `ATTRIBUTION.md`.
- A3: The only absolute paths in the repository are inside `.venv/` and
  `outputs/`, both of which are gitignored. No executable source file contains a
  machine-specific path.
- A3: Verified with
  `grep -rn "C:\\\\\|/Users/" src/ dags/ sql/ tests/ config/ metadata/ --exclude-dir=__pycache__`.
  Returns no matches, meaning no committed source file contains a
  machine-specific absolute path. `__pycache__/` and `.venv/` are gitignored
  and contain compiled artifacts with embedded interpreter paths, which are
  regenerable and not part of the source.
- A4: Verified with `git log --all --full-history -- .env`. The command returns
  no output, meaning `.env` was never committed at any point in history.
- A11: The partition experiment is pedagogical. The DREBIN subset has no
  natural date/time key, so partitions are defined on `is_malware` and
  `flag_conflicting_label`. The limitation is documented in
  `docs/benchmark_report.md`.
- A15: The Postgres schema declares `source_row_key` as `PRIMARY KEY`. The load
  path uses `INSERT ... ON CONFLICT (source_row_key) DO NOTHING`, which
  guarantees idempotency at the database level.
- A17: Reproduced F1 for all six models is within ±0.01 of the DSS141P
  baseline. Five of six match to four decimal places. XGBoost varies by up to
  ±0.0014 due to non-associative parallel reductions in its histogram-based
  tree construction; documented in `docs/reproducibility_report.md` §5.1.