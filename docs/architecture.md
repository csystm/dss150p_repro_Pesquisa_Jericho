# Architecture

Software components and how they are wired together.

```mermaid
flowchart TB
    subgraph Host["Host machine"]
        Dev["Developer / Reviewer"]
    end

    subgraph Compose["docker compose network: dss150p-repro"]
        subgraph PG["postgres (postgres:16-alpine)"]
            PGCUR["curated_apps"]
            PGAUDIT["pipeline_runs"]
            PGMET["model_metrics"]
            PGAIR["airflow metadata DB"]
        end

        subgraph PIPE["pipeline (dss150p-repro:pipeline)"]
            CLI["src/*.py CLI entry points"]
            ART[["data/ curated/staging/raw/<br/>outputs/ model/metrics/predictions"]]
        end

        subgraph AF["airflow (dss150p-repro:airflow)"]
            WEB["webserver :8080 (host :8081)"]
            SCHED["scheduler (LocalExecutor)"]
            DAG["dags/predictive_repro_pipeline.py"]
        end

        subgraph VOLS["Bind mounts and volumes"]
            REPO["./ -> /app"]
            LOGS["./logs -> /opt/airflow/logs"]
            PGDATA["pgdata -> /var/lib/postgresql/data"]
        end
    end

    SRC[("data/source/drebin_dataset.csv<br/>CC BY 4.0")]

    Dev --> SRC
    Dev -->|docker compose exec| CLI
    Dev -->|browser| WEB

    SRC --> CLI
    CLI --> ART
    CLI -->|psycopg2| PGCUR
    CLI -->|psycopg2| PGAUDIT
    CLI -->|psycopg2| PGMET

    WEB --> PGAIR
    SCHED --> PGAIR
    SCHED --> DAG
    DAG -->|BashOperator: python -m src.X| CLI

    REPO --- PIPE
    REPO --- AF
    LOGS --- AF
    PGDATA --- PG
```

Notes:

- Every task in the DAG invokes a `python -m src.X` command inside the **pipeline** container, so orchestration and execution use the same image.
- PostgreSQL serves two roles: the pipeline data store (`curated_apps`, `pipeline_runs`, `model_metrics`) and the Airflow metadata store (separate `airflow` database in the same instance).
- All pipeline artifacts land under bind mounts, so they appear on the host filesystem immediately.