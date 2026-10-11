# Reproducibility Report — DSS150P Integrated Individual Laboratory Activity #4

**Student:** Pesquisa, J. B.
**Student number:** 2024111404  
**Section:** CM17 
**Prior group project:** DSS141P "Comparing classification models for Android malware detection using binary feature flags"  
**Dataset:** DREBIN subset, 15,036 Android apps, 215 binary features, Mendeley Data DOI 10.17632/bpkksc9v5s.7, CC BY 4.0

---

## 1. Prior project summary

The DSS141P baseline trained six classifiers on the DREBIN subset to predict
`is_malware` from 215 binary manifest/permission/API flags:

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| LR baseline | 0.9764 | 0.9618 | 0.9748 | 0.9683 | 0.9961 |
| LR L2 | 0.9771 | 0.9636 | 0.9748 | 0.9692 | 0.9961 |
| LR L1 | 0.9764 | 0.9635 | 0.9730 | 0.9682 | 0.9962 |
| Random Forest | 0.9890 | 0.9909 | 0.9793 | 0.9851 | 0.9989 |
| XGBoost | 0.9900 | 0.9874 | 0.9856 | 0.9865 | 0.9991 |
| MLP | 0.9880 | 0.9829 | 0.9847 | 0.9838 | 0.9978 |

Split: `train_test_split(test_size=0.2, random_state=246112165, stratify=y)`.
The baseline was delivered as two Jupyter notebooks; there was no pipeline
module, no environment pin, no split manifest, and no machine-readable
metrics file.

## 2. Engineered reproduction

Each layer is built from the immutable source in `data/source/drebin_dataset.csv`
with SHA-256 `710f2c11b0cad04c36f56dd16398127feb697fd99e8efa7f75890b792fba3ad5`.

| Stage | Command | Output |
|---|---|---|
| Profile source | `python -m src.profile_source` | `metadata/source_manifest.yml`, `metadata/source_profile.md` |
| Ingest full + incremental | `python -m src.ingest` | `data/raw/batches/batch_*.parquet` |
| Transform | `python -m src.transform --stage both` | `data/staging/staging.parquet`, `data/curated/curated.parquet` |
| Validate | `python -m src.validate --layer raw` (also `staging`, `curated`) | `outputs/validation/*.json` |
| Train | `PYTHONHASHSEED=246112165 python -m src.train` | `outputs/model/*.joblib`, `metadata/split_manifest.json` |
| Evaluate | `python -m src.evaluate` | `outputs/metrics.json`, `outputs/predictions.csv` |
| Reproducibility gate | `python -m src.reproducibility_check` | exit code 0 if F1 is within ±0.01 of `metadata/expected_metrics.json` |

All commands are also available through the Airflow DAG
`predictive_repro_pipeline`, which sequences the same modules as
`BashOperator` tasks (see §5.3).

## 3. Reproduced metrics

All values are from `outputs/metrics.json` produced by the full DAG run
`manual__2026-10-11T05:51:04+00:00`, whose task states are recorded in
`docs/evidence/airflow_run_completed.txt`. The primary metric is F1, the
declared tolerance is ±0.01.

| Model | F1 baseline | F1 reproduced | Delta | Within tolerance ±0.01 |
|---|---:|---:|---:|:---:|
| LR baseline | 0.9683 | 0.9683 | 0.0000 | Yes |
| LR L2 | 0.9692 | 0.9692 | 0.0000 | Yes |
| LR L1 | 0.9682 | 0.9682 | 0.0000 | Yes |
| Random Forest | 0.9851 | 0.9851 | 0.0000 | Yes |
| XGBoost | 0.9865 | 0.9851 | −0.0014 | Yes |
| MLP | 0.9838 | 0.9838 | 0.0000 | Yes |

Reproducibility verdict: `reproducibility.passed = true`. Five of six models
match the baseline F1 to four decimal places. XGBoost varies at the fourth
decimal due to non-associative parallel reductions in its histogram-based
tree construction (see §5.1). The observed spread across three full
reproduction runs was 0.9861, 0.9851, 0.9851 — all within tolerance, none
indicating a pipeline defect.

## 4. Deterministic controls

- **Source identity**: SHA-256 pinned in `metadata/source_manifest.yml`; verified at ingestion.
- **Split**: stratified, seed `246112165`, `test_size=0.2`. `metadata/split_manifest.json` records seed, boundary, per-split row counts, class distributions, and per-split SHA-256 checksums of `source_row_key` lists.
- **Preprocessing fit on train only**: `StandardScaler` lives inside each pipeline, fit inside the CV loop and on the training fold only.
- **Python/NumPy/ML seeds**: `random.seed(246112165)`, `np.random.seed(246112165)`, and every estimator that accepts `random_state` receives `246112165`. `PYTHONHASHSEED=246112165` is documented in the README.
- **Pinned dependencies**: `requirements.txt` pins all top-level packages to the versions used for the reproduction above.
- **Deterministic ordering**: curated data is ordered by `source_row_number` before any operation whose result depends on row order.

## 5. Known limitations

### 5.1 XGBoost F1 delta up to −0.0014

XGBoost uses histogram-based tree construction with parallel reductions that
are not associative. Across three full-reproduction runs on the same machine
with the same seed and identical inputs, the XGBoost F1 varied slightly: 
0.9861, 0.9851, 0.9851. All values are well inside the ±0.01
tolerance and none indicates a pipeline defect. The pipeline keeps `n_jobs=-1`
for speed. Setting `n_jobs=1` would eliminate the variance at a significant
runtime cost.

### 5.2 Duplicate rows, conflicting labels, and identity leakage

The source file contains substantial duplication at the raw byte level:

- 7,775 extra exact-duplicate rows (would be dropped by `drop_duplicates()`)
- 7,778 extra duplicate-feature-vector rows
- 3 feature-vector groups with conflicting labels, covering 398 raw rows
  and 402 rows after `SimCountryIso` normalization to `{0, 1}`

The largest group is the **all-zeros feature vector** (385 rows: 377 B, 8 S).
It is inherent label noise: no feature-based model can separate those rows
beyond the majority label.

The raw audit reports 398 conflicting rows. After normalizing
`TelephonyManager.getSimCountryIso` from `{'0', '1', '?', 0, 1}` to `{0, 1}`
(the `'?'` collapses to `0`), some previously distinct feature vectors become
identical, joining existing conflicting groups. The post-normalization count
is 402. The pipeline flags on the normalized vector because that is what the
model sees.

**Policy.** The pipeline treats every source row as one legitimate app
observation (see `metadata/data_contract.yml > duplicates`). No row is dropped
or reassigned in the primary reproduction; dropping would change the
population, the class balance, and the split, making baseline metrics
incomparable. Every conflicting-label row carries
`flag_conflicting_label = True` for downstream analysis.

**Identity leakage.** Under the primary `policy=keep`, identical feature
vectors can appear in both train and test. This is *identity leakage*: the
model can match a test row to a train row by content. The pipeline logs this
overlap via `record_hash` in the evaluation report. Baseline metrics are as
reported above because the baseline itself used the random split; a grouped
split would not reproduce it.

### 5.3 Airflow orchestration

The DAG `predictive_repro_pipeline` orchestrates 11 tasks in a strict chain:

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

Every task body is a `BashOperator` that invokes `python -m src.X` inside the
pipeline container; business logic lives exclusively in `src/*.py`. The DAG
defines dependencies, retries (2 with 30 s delay), a per-task timeout (90
minutes default, 120 for `train_model`), and a failure callback that logs
`dag_id`, `task_id`, `run_id`, and `try_number`.

Runtime parameters: `full_refresh`, `seed`, `primary_metric`, `tolerance`,
`train_models`. These override the DAG defaults through `dag_run.conf`, so the
same pipeline runs the fast subset (`train_models=linear`, ~90 seconds) and the
full reproduction (`train_models=all`, ~9 minutes) without code changes.

Execution evidence:

- `docs/evidence/airflow_dag_graph.png` — DAG dependency graph.
- `docs/evidence/airflow_run_all_models.png` — grid view of three runs:
  fast linear success, deliberate failure, full-model success.
- `docs/evidence/airflow_run_completed.txt` — task states for the full run
  plus per-model F1 deltas.
- `docs/evidence/airflow_failure_recovery.txt` — the failure injection run
  (`tolerance=-1`, `reproducibility_check` fails, `publish_outputs` blocked)
  and the subsequent recovery run (all green).

### 5.4 Storage benchmark

The same logical curated data (15036 rows × 222 columns) was materialized in
four representations. Numbers are on the development machine (Windows 11 +
Docker Desktop on WSL2, 16 GB RAM):

| Format | Size | Write (s) | Read median (s) |
|---|---:|---:|---:|
| CSV | 9.08 MB | 0.98 | 0.202 |
| JSONL | 83.5 MB | 1.80 | 1.711 |
| Parquet | 1.11 MB | 0.46 | 0.033 |
| PostgreSQL | — | 11.20 (insert) | 0.013 (count) |

Conclusions:

- **Parquet** is the pipeline's intermediate storage: 8× smaller than CSV and
  6× faster to read. It preserves dtypes so the `SimCountryIso` normalization
  does not need to be re-applied.
- **CSV** remains the source-exchange format for its universality and for the
  immutable identity check (the source dataset itself is CSV).
- **JSONL** is 9× larger than CSV for this shape of data because every row
  repeats 222 key strings. It is a poor fit for a wide low-cardinality table
  but the right format for heterogeneous event streams.
- **PostgreSQL** is the analytical store. At 15k rows the planner chooses a
  sequential scan (13 ms full scan vs 12 ms selective filter — indistinguishable)
  and ignores `idx_curated_apps_is_malware`. When forced with
  `SET enable_seqscan = off`, an Index Only Scan with `Heap Fetches: 0`
  executes in 0.6 ms. The index is correct; the table is simply small enough
  that the planner does not need it yet.

Full details: `docs/benchmark_report.md` and `docs/evidence/benchmark.json`.

## 6. Reproducibility contract verification

Reference: §5 of the laboratory brief.

1. Repository clones from GitHub.
2. Source CSV is committed (CC BY 4.0, attribution in `ATTRIBUTION.md`).
3. `.env` is documented in `.env.example`; no secrets committed.
4. Docker/Docker Compose starts PostgreSQL and the pipeline app.
5. Full pipeline runs via CLI or Airflow DAG.
6. Curated data and predictive outputs are produced.
7. Validation and reproducibility checks run.
8. Second run does not introduce duplicate logical records; metrics stay within tolerance.

## 7. Deviations from the prior project

| Aspect | Prior project | This reproduction | Reason |
|---|---|---|---|
| Environment | Global Python, unpinned | `.venv` + `requirements.txt` pinned | Reproducibility |
| Data access | Local notebook path | `SOURCE_DATA_PATH` env var + manifest | No absolute paths |
| Preprocessing | Inline in notebook | `src/transform.py` module | Reusable, testable |
| Split | `train_test_split` in notebook, seed noted | Same seed, persisted manifest | Reproducible, auditable |
| Metrics | Printed in notebook | `outputs/metrics.json` compared to `metadata/expected_metrics.json` | Machine-checkable |
| Model artifacts | `deployment_objects.pkl` | Per-model `.joblib` + `outputs/model/` | Cleaner separation |
| Duplicate handling | Not documented | Contract-declared `policy=keep` | Explicit engineering decision |
| Orchestration | None | Airflow DAG (Phase III) | Runnable as a product |

## 8. What a reviewer can do

From a clean clone on any machine with Docker:

    git clone https://github.com/csystm/dss150p_repro_Pesquisa_Jericho.git
    cd dss150p_repro_Pesquisa_Jericho
    cp .env.example .env
    mkdir -p logs
    docker compose build pipeline
    docker compose build airflow-init
    docker compose up -d

    # CLI-only path (no Airflow)
    docker compose exec pipeline bash
    python -m src.profile_source
    python -m src.ingest
    python -m src.transform --stage both
    python -m src.validate --layer raw
    python -m src.validate --layer staging
    python -m src.validate --layer curated
    docker compose exec -e PYTHONHASHSEED=246112165 pipeline python -m src.train
    docker compose exec pipeline python -m src.evaluate

    # Airflow path (equivalent)
    docker compose exec airflow-scheduler \
      airflow dags trigger predictive_repro_pipeline

Expected: `reproducibility_passed = true` in `outputs/metrics.json`, with all
six models' F1 within ±0.01 of the values in §3. Full setup and troubleshooting
are in `README.md` and `docs/runbook.md`.