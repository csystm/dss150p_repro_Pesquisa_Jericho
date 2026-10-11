# Analysis and Reflection

Responses to Section 14 of the laboratory brief.

## 1. What prevented immediate reproduction

The prior project was delivered as two Jupyter notebooks. Four things stood
in the way of someone else reproducing it. First, there was no pinned
environment, so the notebooks depended on whatever version of scikit-learn
happened to be installed; the `penalty` argument used throughout is already
deprecated in the version we have now and will be removed in the next major
release, so the code will not run unchanged in the future. Second, while the
train/test split had a seed, the seed lived inside a notebook cell and there
was no record of which rows ended up in training and which in test. Third,
the notebook read the dataset from an implicit working directory, so opening
it from anywhere else produced a `FileNotFoundError` with no guidance.
Fourth, the metrics existed only as printed output from a notebook cell;
there was no machine-readable artifact a reviewer could compare against. The
engineering gap table in the reproducibility report lists these and how each
was addressed.

## 2. Which artifact is the authoritative source

The original file is the authoritative source. Its checksum is recorded in
the source manifest and verified at every ingestion, and nothing downstream
is allowed to change it. Everything else in the pipeline is regenerable from
it, which is what makes the checksum meaningful.

Each layer has a distinct role. The raw ingested copy is the original bytes
plus audit columns that record which pipeline run produced it and which row
in the source it corresponds to. The curated dataset is the model-ready view:
types are normalized, the target is encoded, and the rows are in a
deterministic order. The model-ready dataset is not a separate artifact at
all; it is a slice of the curated data selected by the split manifest and can
be regenerated at any time from the same seed. The chain of custody runs
bottom-up, and each layer is verified against the one above it.

## 3. What prevents duplicates

Two identifiers do different jobs. The row key, which encodes the row's
position in the source file, is the business key used for the database
upsert and for any operation that needs to distinguish rows. It assumes that
within a single immutable source file, positional order is stable, which
holds because the file is committed unchanged and its checksum is verified
before ingestion. The record hash is a fingerprint over the feature values
and the target, used for content-based duplicate detection and for checking
whether identical rows end up on both sides of the train/test split.

The upsert uses `INSERT ... ON CONFLICT DO NOTHING` against a primary key,
so the database enforces uniqueness regardless of what the application code
does. This is the strongest form of the rule because it does not rely on the
pipeline being correct.

## 4. Simulating incremental ingestion without a false watermark

The dataset has no event timestamp, no ingestion date, and no monotonic
identifier. There is no legitimate watermark to derive from the data itself.
Rather than invent one and pretend it means something, the pipeline splits
the immutable source into three deterministic batches by row order and
records the last committed batch in a checkpoint file. The checkpoint
advances only after a batch is durably written and validated. On a rerun,
already-committed batches are skipped.

The data contract states explicitly that this is a laboratory simulation, not
a business watermark. A real production pipeline would use the source's
natural event time if one existed, or an ingestion date partition if the
source arrived incrementally. Neither applies here, and the pipeline does not
pretend otherwise.

## 5. What belongs in staging versus curated

Staging is where the data becomes technically correct. This is where the
mixed-type column is normalized to zero and one, where every feature is cast
to an integer and checked to be binary, and where rows whose feature vectors
disagree on the label are flagged. The question staging answers is whether
this is a well-formed table.

Curated is where the data becomes semantically ready for modeling. The raw
target column is replaced by a binary integer target, audit columns are
pruned to the minimum needed for lineage, and the feature and target columns
are separated explicitly. The question curated answers is whether this has
the shape the model expects.

The split matters because normalization is reusable across any downstream
task, while target encoding is specific to this particular model. If a second
model with a different target were added, staging would be unchanged and only
curated would need a variant.

## 6. Which storage format performed best

For the pipeline's intermediate storage, Parquet performed best. It was
eight times smaller than CSV and six times faster to read, and it preserves
data types so the normalization step does not need to be reapplied. For
analytical querying, PostgreSQL performed best; at fifteen thousand rows the
planner correctly ignores the index on the target because the table fits
comfortably in memory, and when the index is forced it produces a very fast
index-only scan.

These results should not be generalized. They are a function of three things
specific to this dataset: it is small, it is wide, and its features are
binary and low-cardinality. Parquet's compression likes low cardinality, and
a large event stream with high-cardinality text columns would not compress
nearly as well. A three-column table would not benefit from a columnar layout
at all, and a streaming source would not tolerate Parquet's
write-once-read-many model. The right answer depends on access patterns,
cardinality, and data lifecycle, which is why the benchmark report records
the numbers for this specific workload rather than declaring a universal
winner.

## 7. What happens if the load task is retried after a committed write

The task would rerun the load module, which issues an upsert against the
curated table. Because the row key is a primary key and the statement uses
`ON CONFLICT DO NOTHING`, the retry inserts zero rows for anything already
committed and inserts only rows that were not committed on the first attempt.
The logical state of the table is identical whether the first attempt
succeeded outright, succeeded partially and then timed out, or succeeded but
lost its acknowledgment.

The task's retries are therefore safe by construction. No distributed
transaction, lock, or compensating action is needed.

## 8. How the retry is made safe

Three properties, in order of importance. The database enforces uniqueness
through the primary key, so no application-level correctness is required.
The insert statement is idempotent by design, so running it any number of
times produces the same result. And the input to the statement is
deterministic, ordered by row number with a fixed column order, so a retry
sees byte-identical data. The idempotency is verified by an integration test
that inserts the same three rows twice and checks that the second call
reports zero new rows.

## 9. Which quality check matters most for silent accuracy damage

The binary feature check catches the most dangerous class of silent error. If
a feature column acquires a value outside zero and one, whether from a
missing sentinel, an encoding bug, or a bad join, the model will quietly
learn from a distorted distribution. Training will not error, evaluation will
produce a plausible-looking metric, and nothing will look wrong until the
model is deployed. Only a range check catches it in time.

The target leakage check is a close second. It guards against the case where
the target itself accidentally ends up in the feature set, which produces
suspiciously perfect metrics that are easy to miss visually. Both checks run
in the validation module, and the failure-injection transcript shows them
catching intentionally broken data.

## 10. How I know the split matches the baseline

Three controls. The seed is the same. The split call is the same, including
the same test size and the same stratification. And the resulting split is
persisted to a manifest that records the row numbers assigned to each side
along with checksums of the row key lists.

The split is therefore not merely seeded but auditable. A reviewer can
recompute either side from the manifest and compare hashes. If the population
had changed, the checksum would change, and the reproducibility check would
fail at the metric comparison step rather than silently producing different
numbers.

## 11. Sources of nondeterminism that remain

Four sources remain, all within tolerance. XGBoost uses parallel reductions
that are not associative, so its split boundaries can shift slightly between
runs; across three full runs its F1 varied between 0.9851 and 0.9861 against
a baseline of 0.9865. The MLP's early stopping depends on a validation-loss
trajectory that can vary slightly with weight initialization and thread
scheduling, though its observed F1 has been stable. Random forest
bootstrapping is seeded but tree construction across threads can shuffle
slightly. And the logistic regression solver uses a numerical tolerance that
could in principle flip the chosen regularization strength on a different
BLAS, though this was not observed.

Python-level sources are covered by setting the hash seed, the random state,
and the NumPy seed before any imports run.

## 12. How to diagnose a metric that differs

Layer by layer. First verify the source checksum, because if that fails
nothing downstream can be trusted. Second verify the split by recomputing the
train and test key checksums against the manifest; a mismatch points to a
data or ordering change. Third validate the curated dataset, which isolates
any problem to the transform stage. Fourth compare the installed packages
against the pinned list, because a library version change can shift feature
importances and even the chosen regularization strength. Fifth load the saved
model artifact and score it against a fixed slice; if the score differs from
what was saved, the problem is in evaluation, and if it matches, the problem
was in training. Finally, rerun with single-threaded execution; if the metric
stabilizes, the cause is thread scheduling rather than a change in the data
or code.

The pipeline makes this cheap because each step produces a machine-readable
artifact with a checksum.

## 13. What to monitor in production

Four families of signal. Data quality, meaning schema drift, feature
distribution changes, null rates, and source freshness; any of these moving
outside its declared band is an early warning. Model performance, meaning the
primary metric on a labeled holdout slice updated periodically, plus drift
metrics on the input distribution that can warn before performance actually
degrades. Pipeline health, meaning task durations relative to a rolling
baseline, retry counts, and checkpoint lag; a rising trend often precedes a
failure. And business metrics, meaning the false positive and false negative
rates weighted by the cost of each error, because those are what actually
matter and the machine learning metrics are only proxies.

## 14. First bottleneck at a hundred times the data

At roughly one and a half million rows, the load step becomes the first
bottleneck. At fifteen thousand rows it already takes eleven seconds because
the table is wide, and scaling that linearly puts it near twenty minutes; the
right fix is bulk loading via `COPY` rather than row-by-row upsert. The
second bottleneck is orchestration, because the current scheduler runs all
tasks in one container and would need to be distributed. The third is memory,
because the transform module loads the entire dataset into memory and would
need to become chunked or out-of-core at that scale.

The order matters. Bulk loading solves the first wall, distributed
orchestration solves the second, and streaming or partitioned processing
solves the third.

## 15. What changes if the data becomes sensitive

Six things change. The source can no longer be committed to the repository;
only a manifest, a checksum, and acquisition instructions go in, and the
attribution file becomes a data access policy with a classification label.
Credentials move out of the environment file and into a secrets manager, and
no plaintext secret appears anywhere, including logs. Encryption is required
at rest for the database volume and in transit between the pipeline and the
database. Every read of the source data is logged with who, when, and why,
which is a stronger audit trail than the current run metadata alone. Deletion
rights mean a source row must be traceable to a data subject and removable
from raw, staging, curated, the database, and any model artifact that
memorized it. And the model itself inherits the data's classification, so
shipping the artifact becomes a controlled operation and even the
explanation plots may leak information.

The current design is not compliant with any of these. The layered
architecture makes them easier to add, because a secrets manager only touches
the database module and the compose file, and a deletion API only touches the
ingest and load modules. But the work is real, not cosmetic.