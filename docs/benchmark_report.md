# Storage Benchmark Report

Generated at: `2026-10-10T14:45:06.351309+00:00`

## Dataset
- Rows: 15036
- Columns: 222
- Feature columns: 215

## Sizes (bytes, lower is better)
| format | bytes | bytes/row |
|---|---:|---:|
| csv | 9078651 | 603.79 |
| jsonl | 83517394 | 5554.50 |
| parquet | 1111784 | 73.94 |

## Write timings (seconds)
| format | write |
|---|---:|
| csv | 0.9762 |
| jsonl | 1.8041 |
| parquet | 0.4592 |
| postgres | 11.1963 |

## Read timings (median of 5, seconds, lower is better)
| format | read |
|---|---:|
| csv | 0.2022 |
| jsonl | 1.7105 |
| parquet | 0.0325 |

## PostgreSQL query timings (median of 5, seconds)
| query | median seconds | row count |
|---|---:|---:|
| full table count | 0.013166 | 15036 |
| selective (is_malware=1) | 0.011938 | 5560 |

**Index note.** The planner correctly ignores `idx_curated_apps_is_malware` at 15,036 rows (full scan 13 ms vs selective filter 12 ms — indistinguishable). When forced with `SET enable_seqscan = off`, the planner uses an `Index Only Scan` with `Heap Fetches: 0` and executes in 0.6 ms. The index is the right structure for the query; the table is simply small enough that the planner does not need it yet. See `docs/evidence/postgres_index_check.txt`.

## Logical-equivalence check
Sorted `source_row_key` SHA-256 of curated input: `b31d6fd396dcf0de23eb38bc5f63c3bb680b78f49d2eaa7bf8d0164eb73c436e`

## Partition experiment

No natural date/time key exists in the DREBIN subset. Partitions here are pedagogical: is_malware and flag_conflicting_label.

| partition | rows | bytes |
|---|---:|---:|
| is_malware=0 | 9476 | 841884 |
| is_malware=1 | 5560 | 428946 |
| flag_conflicting_label=false | 14634 | 1102491 |
| flag_conflicting_label=true | 402 | 152694 |

Selected partition: `is_malware=0` — read 9476 rows (matches written: True).

## Findings per use case

- **Source exchange (one-time handoff to another engineer or system)**: CSV.
  Universally readable, human-inspectable, 9.08 MB for 15,036 rows is
  unproblematic. The source CSV is also the immutable input tracked under
  CC BY 4.0; the curated CSV is a convenience export, not the authoritative
  artifact.

- **Pipeline intermediate storage (raw → staging → curated handoff)**: Parquet.
  1.11 MB, 0.46 s write, 0.033 s read. The smallest and fastest representation
  and it preserves dtypes, so `TelephonyManager.getSimCountryIso`'s
  normalization to `{0,1}` survives without a re-parse. This is what the
  pipeline actually uses.

- **Model input**: Parquet, loaded into pandas with the same 215 int64 feature
  columns the baseline saw. JSONL would require re-typing each feature on load,
  and CSV would re-parse 3.3M cells as text on every read. Parquet avoids both.

- **Analytical querying**: PostgreSQL. The 15,036-row table fits in shared_buffers
  after the first query, so full scan (13 ms) and selective filter (12 ms) are
  indistinguishable. The `is_malware` index exists for the case when the table
  grows; on 15k rows the planner correctly ignores it. This is the correct
  storage for joins, aggregations, and downstream BI, not for ML training.

- **Partitioning**: pedagogical. The DREBIN subset has no reliable event
  timestamp; partitioning by `is_malware` is not a natural business partition,
  it is a demonstration that one partition can be read independently
  (9,476 rows read from `is_malware=0.parquet`, matching the written row count).
  A real production partition would need an ingest_date or a device_id space.
  Small partitions carry disproportionate Parquet footer overhead
  (152 KB for 402 rows), so partitioning should only be applied when the
  partition count and the workload justify it.

- **Not universal**: none of the above generalizes. CSV is best here because
  the dataset is small and text-legible; on a 500 GB event stream Parquet
  would be mandatory. JSONL is the worst of both worlds for this shape of
  data but is the right choice for append-only event logs with heterogeneous
  schemas. PostgreSQL is the right analytical store at 15k rows; a real
  warehouse would move to columnar storage (Parquet on object storage or a
  columnar warehouse) as the data grows past a few hundred million rows.
