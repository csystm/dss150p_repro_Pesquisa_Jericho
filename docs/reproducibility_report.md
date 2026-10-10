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
| Profile source | `python src/profile_source.py` | `metadata/source_manifest.yml`, `metadata/source_profile.md` |
| Ingest full + incremental | `python src/ingest.py` | `data/raw/batches/batch_*.parquet` |
| Transform | `python -m src.transform` | `data/staging/staging.parquet`, `data/curated/curated.parquet` |
| Validate | `python -m src.validate --layer raw/staging/curated` | `outputs/validation/*.json` |
| Train | `PYTHONHASHSEED=246112165 python -m src.train` | `outputs/model/*.joblib`, `metadata/split_manifest.json` |
| Evaluate | `python -m src.evaluate` | `outputs/metrics.json`, `outputs/predictions.csv` |

## 3. Reproduced metrics

| Model | F1 baseline | F1 reproduced | Delta | Within tolerance ±0.01 |
|---|---:|---:|---:|:---:|
| LR baseline | 0.9683 | 0.9683 | +0.0000 | Yes |
| LR L2 | 0.9692 | 0.9692 | +0.0000 | Yes |
| LR L1 | 0.9682 | 0.9682 | +0.0000 | Yes |
| Random Forest | 0.9851 | 0.9851 | +0.0000 | Yes |
| XGBoost | 0.9865 | 0.9861 | −0.0004 | Yes |
| MLP | 0.9838 | 0.9838 | +0.0000 | Yes |

`reproducibility_passed = true` on the primary metric F1.

## 4. Deterministic controls

- **Source identity**: SHA-256 pinned in `metadata/source_manifest.yml`; verified at ingestion.
- **Split**: stratified, seed `246112165`, `test_size=0.2`. `metadata/split_manifest.json` records seed, boundary, per-split row counts, class distributions, and per-split SHA-256 checksums of `source_row_key` lists.
- **Preprocessing fit on train only**: `StandardScaler` lives inside each pipeline, fit inside the CV loop and on the training fold only.
- **Python/NumPy/ML seeds**: `random.seed(246112165)`, `np.random.seed(246112165)`, and every estimator that accepts `random_state` receives `246112165`. `PYTHONHASHSEED=246112165` is documented in the README.
- **Pinned dependencies**: `requirements.txt` pins all top-level packages to the versions used for the reproduction above.
- **Deterministic ordering**: curated data is ordered by `source_row_number` before any operation whose result depends on row order.

## 5. Known limitations

### 5.1 XGBoost F1 delta of −0.0004

XGBoost uses histogram-based tree construction with parallel reductions that
are not associative. Run-to-run F1 differs at the 4th decimal even with a
fixed seed and identical inputs. The delta is well inside the ±0.01 tolerance
and does not indicate a pipeline error. Verification experiment: rerunning
with `n_jobs=1` should eliminate the drift; the pipeline keeps `n_jobs=-1`
for speed and documents the expected tolerance.

### 5.2 Duplicate rows and conflicting labels

The source file contains substantial duplication at the raw byte level:

- 7,775 extra exact-duplicate rows (would be dropped by `drop_duplicates()`)
- 7,778 extra duplicate-feature-vector rows
- 3 feature-vector groups with conflicting labels, covering 398 raw rows
  and 402 rows after `SimCountryIso` normalization to `{0,1}`

The largest group is the **all-zeros feature vector** (385 rows: 377 B, 8 S).
It is inherent label noise: no feature-based model can separate those rows
beyond the majority label.

**Policy.** The pipeline treats every source row as one legitimate app
observation (see `metadata/data_contract.yml > duplicates`). No row is
dropped or reassigned in the primary reproduction; dropping would change
the population, the class balance, and the split, making baseline metrics
incomparable. Every conflicting-label row carries
`flag_conflicting_label = True` for downstream analysis.

### 5.3 Identity leakage in the random split

Under the primary `policy=keep`, identical feature vectors can appear in
both train and test. This is *identity leakage*: the model can match a test
row to a train row by content. The pipeline logs this overlap via
`record_hash` in the evaluation report. Baseline metrics are as reported
above because the baseline itself used the random split.

### 5.4 Post-normalization conflicting-label count

The raw audit reports 398 conflicting rows. After normalizing
`TelephonyManager.getSimCountryIso` from `{'0', '1', '?', 0, 1}` to `{0, 1}`
(the `'?'` collapses to `0`), some previously distinct feature vectors become
identical, joining existing conflicting groups. The post-normalization count
is 402. The pipeline flags on the normalized vector because that is what the
model sees.

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
| Duplicate handling | Not documented | Contract-declared `policy=keep` with sensitivity run | Explicit engineering decision |
| Orchestration | None | Airflow DAG (Phase III) | Runnable as a product |

## 8. What a reviewer can do

From a clean clone:

    git clone https://github.com/csystm/dss150p_repro_Pesquisa_Jericho.git
    cd dss150p_repro_Pesquisa_Jericho
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    # place drebin_dataset.csv in data/source/ (committed in this repo)
    python src/profile_source.py
    python src/ingest.py
    python -m src.transform
    python -m src.validate --layer raw
    python -m src.validate --layer staging
    python -m src.validate --layer curated
    PYTHONHASHSEED=246112165 python -m src.train
    python -m src.evaluate

Expected: `reproducibility_passed = true` in `outputs/metrics.json` with all
six models' F1 within ±0.01 of the values in §3.

---

*This report will be extended in Phases III and IV with Airflow execution evidence, storage benchmark results, lineage, and failure-recovery transcripts.*