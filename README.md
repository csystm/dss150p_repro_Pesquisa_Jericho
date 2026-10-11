# DSS150P Reproducible Predictive Analytics — DREBIN Android Malware

Individual reproduction of a predictive analytics project as a reproducible,
rerun-safe data engineering product. The prior DSS141P baseline is treated as
an artifact to be regenerated from the same source dataset, not improved.

**Student:** Pesquisa, J. B.
**Student number:** 2024111404
**Section:** CM17
**Prior project:** DSS141P "Comparing classification models for Android malware
detection using binary feature flags"

---

## 1. What this repository does

The pipeline ingests the DREBIN subset, validates it against a declarative data
contract, transforms it into staging and curated layers, materializes it in
PostgreSQL, trains six classifiers deterministically, evaluates them against a
machine-readable baseline, and publishes the results — all orchestrated by
Apache Airflow and containerized with Docker Compose.

The success criterion is reproducibility, not accuracy. Given the same source
file and the same pinned environment, the pipeline regenerates the same
curated dataset and metrics within the declared ±0.01 tolerance on F1.

## 2. Prior project summary

The DSS141P baseline trained six classifiers on the DREBIN subset to predict
`is_malware` from 215 binary manifest/permission/API flags. Baseline metrics:

| Model         | Accuracy | Precision | Recall | F1     | ROC-AUC |
|---------------|----------|-----------|--------|--------|---------|
| LR baseline   | 0.9764   | 0.9618    | 0.9748 | 0.9683 | 0.9961  |
| LR L2         | 0.9771   | 0.9636    | 0.9748 | 0.9692 | 0.9961  |
| LR L1         | 0.9764   | 0.9635    | 0.9730 | 0.9682 | 0.9962  |
| Random Forest | 0.9890   | 0.9909    | 0.9793 | 0.9851 | 0.9989  |
| XGBoost       | 0.9900   | 0.9874    | 0.9856 | 0.9865 | 0.9991  |
| MLP           | 0.9880   | 0.9829    | 0.9847 | 0.9838 | 0.9978  |

Split: `train_test_split(test_size=0.2, random_state=246112165, stratify=y)`.

Full engineering comparison is in
[`docs/reproducibility_report.md`](docs/reproducibility_report.md).

## 3. Dataset and license

**Source:** DREBIN subset (15,036 Android applications, 9,476 benign / 5,560
malware, 215 binary features). Mendeley Data, DOI
[10.17632/bpkksc9v5s.7](https://doi.org/10.17632/bpkksc9v5s.7).

**License:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The raw file is committed unchanged at `data/source/drebin_dataset.csv`. Its
identity is pinned by SHA-256 in `metadata/source_manifest.yml`:

```
710f2c11b0cad04c36f56dd16398127feb697fd99e8efa7f75890b792fba3ad5
```

See [`ATTRIBUTION.md`](ATTRIBUTION.md) for full attribution and modification
notes.

**Duplicate audit.** The source contains 7,775 extra exact-duplicate rows and
three feature-vector groups with conflicting labels (398 rows pre-normalization,
402 post-normalization). The primary reproduction preserves all 15,036 rows.
See [`metadata/data_contract.yml`](metadata/data_contract.yml) for the
declared policy and
[`metadata/source_profile.md`](metadata/source_profile.md) for the audit
evidence.

## 4. Architecture

Components: PostgreSQL (pipeline data + Airflow metadata), a pipeline
container (all `src/*.py` entry points), an Airflow container set (webserver +
scheduler), and bind-mounted artifact directories on the host.

Full component diagram: [`docs/architecture.md`](docs/architecture.md).
Dataset-level lineage: [`docs/lineage.md`](docs/lineage.md).

High-level flow:

```
source CSV
  → raw (batched Parquet)
  → staging (typed, validated)
  → curated (model-ready)
  → PostgreSQL curated_apps
  → models (six classifiers)
  → metrics.json + predictions.csv
  → reproducibility_check (gate)
  → published outputs
```

## 5. Repository structure

```
dss150p_repro_Pesquisa_Jericho/
├── README.md
├── ATTRIBUTION.md
├── .gitattributes
├── .gitignore
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── requirements-airflow.txt
├── Dockerfile
├── Dockerfile.airflow
├── docker-compose.yml
├── pytest.ini
├── config/
│   └── settings.yml
├── data/
│   ├── source/            # immutable source CSV (committed)
│   ├── raw/               # ingested batches
│   ├── staging/           # typed, validated
│   ├── curated/           # model-ready
│   └── partitioned/       # benchmark partitions
├── metadata/
│   ├── source_manifest.yml
│   ├── source_profile.md
│   ├── data_contract.yml
│   ├── expected_metrics.json
│   └── split_manifest.json      # generated
├── src/
│   ├── profile_source.py
│   ├── ingest.py
│   ├── transform.py
│   ├── storage.py
│   ├── validate.py
│   ├── db.py
│   ├── load_to_postgres.py
│   ├── train.py
│   ├── evaluate.py
│   ├── reproducibility_check.py
│   ├── publish.py
│   └── benchmark.py
├── sql/
│   ├── schema.sql
│   └── init_airflow_db.sql
├── dags/
│   └── predictive_repro_pipeline.py
├── tests/
│   ├── conftest.py
│   ├── test_unit_*.py
│   ├── test_integration_*.py
│   └── test_data_contract.py
├── outputs/                # regenerable (gitignored except .gitkeep)
└── docs/
    ├── architecture.md
    ├── lineage.md
    ├── runbook.md
    ├── benchmark_report.md
    ├── reproducibility_report.md
    ├── acceptance_tests.md
    └── evidence/
```

**Deviations from the required structure.** Diagrams are provided as Mermaid
inside Markdown (`docs/architecture.md`, `docs/lineage.md`) rather than as
`.png` files, because Mermaid renders inline on GitHub and stays in sync with
the repo. An `ATTRIBUTION.md` and `pytest.ini` were added. The `sql/` and
`tests/` directories carry additional files. All are annotated in this README
and in `docs/reproducibility_report.md`.

## 6. Prerequisites

- Docker Desktop 24+ with Compose v2 (Linux, macOS, or Windows with WSL2)
- 8 GB RAM minimum (16 GB recommended for the all-models training run)
- ~2 GB free disk for images, volumes, and outputs
- Python 3.12 on the host is only needed to run the pure-unit test subset

## 7. Clean-machine setup

```bash
git clone https://github.com/csystm/dss150p_repro_Pesquisa_Jericho.git
cd dss150p_repro_Pesquisa_Jericho
cp .env.example .env
# Optional: edit .env for a non-default Postgres password and Airflow admin creds.
```

```python
# Generate a Fernet key for Airflow and paste it into .env as AIRFLOW_FERNET_KEY
from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())
```


```bash
mkdir -p logs

# Build sequentially to avoid the compose parallel-build race
docker compose build pipeline
docker compose build airflow-init
docker compose up -d
docker compose ps
```

Expected state: `postgres` healthy, `pipeline` up, `airflow-webserver` healthy
on `localhost:${AIRFLOW_WEBSERVER_PORT:-8080}`, `airflow-scheduler` up.

The Postgres schema is created automatically on first volume initialization by
`sql/schema.sql`. Create the Airflow metadata database once:

```bash
docker compose exec postgres psql -U dss150p_user -d dss150p \
  -c "CREATE DATABASE airflow OWNER dss150p_user;"
```

If the `pgdata` volume already exists, both steps are skipped and the schema
persists.

## 8. Data placement

The source CSV is committed. If you obtained the repository without it, place
the DREBIN subset at:

```
data/source/drebin_dataset.csv
```

Verify the identity:

```bash
shasum -a 256 data/source/drebin_dataset.csv      # macOS / Linux
Get-FileHash data\source\drebin_dataset.csv -Algorithm SHA256   # Windows
```

The output must match `sha256` in `metadata/source_manifest.yml`. If it does
not, the file is not the version the baseline was computed against and the
metrics will not reproduce.

## 9. Execution — CLI

All stages are runnable from inside the pipeline container:

```bash
docker compose exec pipeline bash

python src/profile_source.py
python -m src.ingest --expected-checksum 710f2c11b0cad04c36f56dd16398127feb697fd99e8efa7f75890b792fba3ad5
python -m src.transform --stage both
python -m src.validate --layer raw
python -m src.validate --layer staging
python -m src.validate --layer curated
python -m src.load_to_postgres
PYTHONHASHSEED=246112165 python -m src.train
python -m src.evaluate
python -m src.reproducibility_check
```

`src/reproducibility_check.py` exits non-zero if any primary metric falls
outside the declared tolerance.

A storage benchmark comparing CSV, JSONL, Parquet, and PostgreSQL is available:

```bash
python -m src.benchmark
```

## 10. Execution — Airflow

```bash
# Unpause once per DAG lifetime
docker compose exec airflow-scheduler \
  airflow dags unpause predictive_repro_pipeline

# Full run (all six models, ~9 minutes)
docker compose exec airflow-scheduler \
  airflow dags trigger predictive_repro_pipeline

# Fast subset (three logistic models, ~90 seconds)
docker compose exec airflow-scheduler \
  airflow dags trigger predictive_repro_pipeline \
  --conf '{"full_refresh": false, "seed": 246112165,
           "primary_metric": "f1", "tolerance": 0.01,
           "train_models": "linear"}'
```

Runtime parameters: `full_refresh`, `seed`, `primary_metric`, `tolerance`,
`train_models`. Every parameter overrides the DAG default via `dag_run.conf`.

The DAG contains 11 tasks in a strict chain:

```
ingest_source → validate_raw → transform_staging → validate_staging
→ build_curated → load_postgres → validate_curated
→ train_model → evaluate_model → reproducibility_check → publish_outputs
```

Business logic lives exclusively in `src/*.py`; the DAG only sequences
`BashOperator` calls. See [`docs/runbook.md`](docs/runbook.md) for operational
procedures and failure recovery.

## 11. Validation

Three layers are validated against the declarative contract in
`metadata/data_contract.yml`:

```bash
python -m src.validate --layer raw
python -m src.validate --layer staging
python -m src.validate --layer curated
```

Each run writes a JSON report under `outputs/validation/` and exits non-zero
on any `fail`-severity check. `quarantine` and `warn` severities are logged
without blocking. See
[`docs/evidence/validation_failure_injection.txt`](docs/evidence/validation_failure_injection.txt)
for a demonstration that intentionally invalid data is caught.

## 12. Tests

```bash
# Host (no Postgres)
pip install -r requirements-dev.txt
pytest tests/ -v
# Expected: 50 passed, 2 skipped

# Inside the pipeline container (full suite, incl. Postgres)
docker compose exec pipeline pip install pytest==9.1.1
docker compose exec pipeline python -m pytest tests/ -v
# Expected: 52 passed
```

Test categories:

- `tests/test_unit_*.py` — pure unit tests for `ingest`, `transform`,
  `validate`, `storage`, `train`.
- `tests/test_integration_pipeline.py` — file-boundary integration
  (Parquet round-trip).
- `tests/test_integration_postgres.py` — Postgres-boundary integration
  (upsert idempotency, pipeline-run audit).
- `tests/test_data_contract.py` — data-quality assertions against produced
  artifacts; skipped if `data/curated/curated.parquet` is absent.

Evidence: [`docs/evidence/pytest_full.txt`](docs/evidence/pytest_full.txt)
and [`docs/evidence/pytest_host.txt`](docs/evidence/pytest_host.txt).

## 13. Expected outputs

After a successful full run:

- `data/raw/batches/batch_0000..0002.parquet` — 15,036 rows total.
- `data/staging/staging.parquet` — 15,036 rows × 226 columns.
- `data/curated/curated.parquet` — 15,036 rows × 222 columns.
- `outputs/validation/{raw,staging,curated}_*.json` — all `passed: true`.
- `metadata/split_manifest.json` — seed, boundary, per-split SHA-256 checksums.
- `outputs/model/*.joblib` — six fitted model pipelines.
- `outputs/metrics.json` — `reproducibility.passed: true`.
- `outputs/predictions.csv` — per-row probabilities per model.
- `outputs/published/<run_id>/` — run-scoped copies of the above.

PostgreSQL:

```bash
docker compose exec postgres psql -U dss150p_user -d dss150p -c "
  SELECT
    (SELECT count(*) FROM curated_apps)   AS curated_rows,
    (SELECT count(*) FROM pipeline_runs)  AS pipeline_runs,
    (SELECT count(*) FROM model_metrics)  AS metric_rows;
"
```

Expected: `curated_rows = 15036`.

## 14. Reproducibility notes

**Deterministic controls.**

- Source identity pinned by SHA-256, verified at ingestion.
- Stratified split, seed `246112165`, `test_size=0.2`; recorded in
  `metadata/split_manifest.json` with per-split `source_row_key` checksums.
- Preprocessing (`StandardScaler`) fit inside the pipeline on training folds
  only.
- `PYTHONHASHSEED=246112165` set for every task.
- Every estimator with a `random_state` parameter receives `246112165`.
- Curated data ordered deterministically by `source_row_number`.

**Tolerance.** Default is ±0.01 absolute on the primary metric (`f1`). Five of
six models reproduce to four decimal places. XGBoost varies at the fourth
decimal (`±0.001`) due to non-associative parallel reductions in its
histogram-based tree construction. This is documented in
[`docs/reproducibility_report.md`](docs/reproducibility_report.md) §5.1.

**Pinned environment.** `requirements.txt` pins all top-level runtime packages.
scikit-learn 1.9.1 emits `FutureWarning` for the deprecated `penalty=` argument;
this is expected and does not affect results. When scikit-learn 1.10 removes
`penalty=`, `src/train.py` will need to migrate to `l1_ratio=` and the pin will
need to be updated.

## 15. Troubleshooting

Quick reference; full procedures are in [`docs/runbook.md`](docs/runbook.md).

| Symptom | Fix |
|---|---|
| `port is already allocated` on 8080 | Set `AIRFLOW_WEBSERVER_PORT=8081` in `.env`, then `docker compose up -d` |
| `port is already allocated` on 5432 | Set `POSTGRES_HOST_PORT=5433` in `.env` |
| Airflow login rejected | `docker compose exec airflow-scheduler airflow users reset-password --username admin --password admin` |
| `ImportError: DLL load failed while importing murmurhash` (Windows) | Windows Smart App Control is blocking unsigned scikit-learn binaries; disable it or add the project `.venv` to Windows Security exclusions |
| `reproducibility_check` fails | Inspect the task log for which model and metric exceeded tolerance; do not raise tolerance without documentation |
| Ingest checkpoint stuck | `python -m src.ingest --force` resets the checkpoint and rebuilds all batches |
| `curated_apps` count drifts | Load path is `ON CONFLICT DO NOTHING`; if count is low, rerun `python -m src.load_to_postgres` |
| DAG not visible in the UI | `docker compose exec airflow-scheduler airflow dags list-import-errors` |

## 16. Attribution

DREBIN dataset attribution and license are in
[`ATTRIBUTION.md`](ATTRIBUTION.md). All code, tests, documentation, and
derived data in this repository are the individual work of the student named
above.

## 17. Further reading

- Reproducibility report: [`docs/reproducibility_report.md`](docs/reproducibility_report.md)
- Benchmark report: [`docs/benchmark_report.md`](docs/benchmark_report.md)
- Runbook: [`docs/runbook.md`](docs/runbook.md)
- Acceptance tests: [`docs/acceptance_tests.md`](docs/acceptance_tests.md)
- Evidence: [`docs/evidence/`](docs/evidence/)