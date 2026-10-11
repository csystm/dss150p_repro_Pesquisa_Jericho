"""DSS150P reproducible predictive analytics pipeline.

All business logic lives in src/*.py. This DAG orchestrates via BashOperator.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


def _failure_log(context):
    ti = context["task_instance"]
    print(
        f"TASK FAILED dag={ti.dag_id} task={ti.task_id} "
        f"run_id={ti.run_id} try={ti.try_number}"
    )


DEFAULT_ARGS = {
    "owner": "dss150p",
    "retries": 2,
    "retry_delay": timedelta(seconds=30),
    "execution_timeout": timedelta(minutes=90),
    "on_failure_callback": _failure_log,
}

with DAG(
    dag_id="predictive_repro_pipeline",
    description="DSS150P reproducible predictive analytics pipeline (DREBIN subset)",
    start_date=datetime(2025, 1, 1),
    schedule=None,       # manual trigger only; catchup disabled
    catchup=False,
    default_args=DEFAULT_ARGS,
    params={
        "full_refresh": False,
        "seed": 246112165,
        "primary_metric": "f1",
        "tolerance": 0.01,
        "train_models": "all",   # or "linear" for the fast subset
    },
    tags=["dss150p", "reproducibility"],
) as dag:

    def _common(cmd: str) -> str:
        # Every task: cd to repo, export seed + run id, then run cmd.
        return (
            "cd /app && "
            "export PYTHONHASHSEED={{ params.seed }} && "
            "export PIPELINE_RUN_ID=$(echo '{{ run_id }}' | tr ':+.' '___') && "
            + cmd
        )

    ingest_source = BashOperator(
        task_id="ingest_source",
        bash_command=_common(
            "python -m src.ingest {{ '--force' if params.full_refresh else '' }}"
        ),
    )

    validate_raw = BashOperator(
        task_id="validate_raw",
        bash_command=_common("python -m src.validate --layer raw"),
    )

    transform_staging = BashOperator(
        task_id="transform_staging",
        bash_command=_common("python -m src.transform --stage staging"),
    )

    validate_staging = BashOperator(
        task_id="validate_staging",
        bash_command=_common("python -m src.validate --layer staging"),
    )

    build_curated = BashOperator(
        task_id="build_curated",
        bash_command=_common("python -m src.transform --stage curated"),
    )

    load_postgres = BashOperator(
        task_id="load_postgres",
        bash_command=_common("python -m src.load_to_postgres"),
        retries=3,
        retry_delay=timedelta(seconds=15),
    )

    validate_curated = BashOperator(
        task_id="validate_curated",
        bash_command=_common("python -m src.validate --layer curated"),
    )

    train_model = BashOperator(
        task_id="train_model",
        bash_command=_common(
            "{% if params.train_models == 'linear' %}"
            "python -m src.train --models 'LR baseline' 'LR L2' 'LR L1'"
            "{% else %}"
            "python -m src.train"
            "{% endif %}"
        ),
        execution_timeout=timedelta(minutes=120),
    )

    evaluate_model = BashOperator(
        task_id="evaluate_model",
        bash_command=_common(
            "python -m src.evaluate "
            "--primary-metric {{ params.primary_metric }} "
            "--tolerance {{ params.tolerance }}"
        ),
    )

    reproducibility_check = BashOperator(
        task_id="reproducibility_check",
        bash_command=_common("python -m src.reproducibility_check"),
    )

    publish_outputs = BashOperator(
        task_id="publish_outputs",
        bash_command=_common(
            "python -m src.publish "
            "--run-id $(echo '{{ run_id }}' | tr ':+.' '___')"
        ),
    )

    (
        ingest_source
        >> validate_raw
        >> transform_staging
        >> validate_staging
        >> build_curated
        >> load_postgres
        >> validate_curated
        >> train_model
        >> evaluate_model
        >> reproducibility_check
        >> publish_outputs
    )