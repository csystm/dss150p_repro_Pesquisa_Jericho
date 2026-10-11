# Runbook

Operational procedures for the DSS150P reproducible predictive analytics pipeline.

## Prerequisites

- Docker Desktop 24+ with Compose v2
- 8 GB RAM minimum, 16 GB recommended
- ~2 GB free disk for images and volumes
- The source dataset committed at `data/source/drebin_dataset.csv`
  (CC BY 4.0; see `ATTRIBUTION.md`)

## Cold start

From a clean clone:

    git clone <repo-url>
    cd DSS150P_REPRO_LASTNAME_FIRSTNAME
    cp .env.example .env
    # optional: edit .env for a non-default Postgres password

    mkdir -p logs
    docker compose build pipeline
    docker compose build airflow-init
    docker compose up -d
    docker compose ps

Expected state: `postgres` healthy, `pipeline` up, `airflow-webserver` healthy
and bound to `localhost:${AIRFLOW_WEBSERVER_PORT:-8080}`, `airflow-scheduler` up.

First-time initialization creates the Postgres schema automatically (via
`sql/schema.sql` mounted into `/docker-entrypoint-initdb.d/`). If the `pgdata`
volume already exists from a previous run, schema is preserved and not
re-applied.

Create the Airflow metadata DB once (only if it does not exist):

    docker compose exec postgres psql -U dss150p_user -d dss150p \
      -c "CREATE DATABASE airflow OWNER dss150p_user;"

The `airflow-init` service creates the admin user; credentials come from
`AIRFLOW_ADMIN_USER` and `AIRFLOW_ADMIN_PASSWORD` in `.env`.

## CLI-only execution (no Airflow)

Every stage runs as a Python module from inside the pipeline container:

    docker compose exec pipeline bash

    python src/profile_source.py
    python -m src.ingest
    python -m src.transform --stage both
    python -m src.validate --layer raw
    python -m src.validate --layer staging
    python -m src.validate --layer curated
    python -m src.load_to_postgres
    PYTHONHASHSEED=246112165 python -m src.train
    python -m src.evaluate
    python -m src.reproducibility_check

The `reproducibility_check` step exits non-zero if any primary metric falls
outside the declared tolerance.

## Airflow execution

Unpause once per DAG lifetime:

    docker compose exec airflow-scheduler airflow dags unpause predictive_repro_pipeline

Trigger with default parameters (all models):

    docker compose exec airflow-scheduler \
      airflow dags trigger predictive_repro_pipeline

Trigger with a fast subset (three logistic models, ~90 seconds):

    docker compose exec airflow-scheduler \
      airflow dags trigger predictive_repro_pipeline \
      --conf '{"full_refresh": false, "seed": 246112165,
               "primary_metric": "f1", "tolerance": 0.01,
               "train_models": "linear"}'

Runtime parameters:

| param | default | meaning |
|---|---|---|
| `full_refresh` | `false` | pass `--force` to ingest so raw batches are rebuilt from scratch |
| `seed` | `246112165` | `PYTHONHASHSEED` for every task |
| `primary_metric` | `f1` | metric used by `reproducibility_check` |
| `tolerance` | `0.01` | absolute delta permitted against `metadata/expected_metrics.json` |
| `train_models` | `"all"` | `"all"` or `"linear"` (three fastest models) |

## Common failures and recovery

### `service postgres is unhealthy`

Postgres has not accepted its first connection within 20 seconds.

    docker compose logs postgres | tail -n 40
    docker compose restart postgres

The healthcheck (`pg_isready`) runs every 5 seconds with 20 retries. If it is
still failing, check available disk: `docker system df`.

### `port is already allocated` on 8080

Another process owns the Airflow webserver port. Change the host mapping in
`.env`:

    AIRFLOW_WEBSERVER_PORT=8081

Then `docker compose up -d`. Internally the webserver still listens on 8080.

### `port is already allocated` on 5432

Same pattern:

    POSTGRES_HOST_PORT=5433

Inside the compose network the pipeline still reaches `postgres:5432`.

### Airflow login rejected

Reset the admin password directly:

    docker compose exec airflow-scheduler airflow users reset-password \
      --username admin --password admin

If no user exists:

    docker compose exec airflow-scheduler airflow users create \
      --username admin --firstname Admin --lastname User \
      --role Admin --email admin@example.com --password admin

### DAG not listed in the UI

    docker compose exec airflow-scheduler airflow dags list
    docker compose exec airflow-scheduler airflow dags list-import-errors

An import error is usually caused by a Python syntax error in the DAG file or a
missing dependency. Check `airflow-scheduler` logs.

### Task fails: `Bash command failed`

Read the task log. Airflow 2.10 stores logs under
`logs/dag_id=<id>/run_id=<id>/task_id=<id>/attempt=N.log`. The exact failure
reason is the last few lines before the Python traceback.

For `reproducibility_check` specifically, the log contains a
`REPRODUCIBILITY FAILED` line and the per-model deltas.

### `reproducibility_check` fails

Cause: a metric delta exceeds the configured tolerance.

Diagnosis:

    python -m src.reproducibility_check

Fix: either the pipeline genuinely diverged (inspect the task log for which
model and metric), or the tolerance is too strict for the algorithm's
nondeterminism (XGBoost varies at the 4th decimal). Do not raise the tolerance
without documenting the reason.

### Ingest checkpoint stuck

The checkpoint file is `data/raw/_checkpoints/ingest_checkpoint.json`.
`{"last_committed_batch": N}` means batches 0..N are committed. To rebuild from
scratch:

    python -m src.ingest --force

This deletes existing batch parquet files and resets the checkpoint.

### Postgres `curated_apps` counts drift

The load path uses `INSERT ... ON CONFLICT (source_row_key) DO NOTHING`, so
reruns never duplicate rows. Verify:

    docker compose exec postgres psql -U dss150p_user -d dss150p \
      -c "SELECT count(*) FROM curated_apps;"

Expected: 15036. If lower, some batches were not loaded — rerun
`python -m src.load_to_postgres`.

### Wipe everything and start clean

    docker compose down
    docker volume rm dss150p-pgdata
    rm -rf data/raw/batches data/raw/_checkpoints
    rm -rf data/staging data/curated data/partitioned
    rm -rf outputs/*
    docker compose up -d --build

This removes the Postgres volume (all pipeline data and Airflow history).
The source CSV is untouched.

## Verification checklist after a run

1. `data/raw/batches/` contains three batch files totaling 15036 rows.
2. `data/staging/staging.parquet` has 15036 rows and 226 columns.
3. `data/curated/curated.parquet` has 15036 rows and 222 columns.
4. `outputs/validation/` contains three JSON reports, all `passed: true`.
5. `outputs/metrics.json` has `reproducibility.passed: true`.
6. `docker compose exec postgres psql -U dss150p_user -d dss150p -c
   "SELECT count(*) FROM curated_apps;"` returns 15036.
7. `pytest tests/ -v` returns 5 passed.

## Rollback

The pipeline has no destructive side effects on the source dataset. To roll back
to a previous state:

- Git: `git checkout <commit>` and rerun the pipeline.
- Postgres: the `curated_apps` table is idempotent on `source_row_key`; to
  reset, `TRUNCATE curated_apps;` then `python -m src.load_to_postgres`.
- Airflow: delete individual runs from the UI; the DAG definition lives in git.