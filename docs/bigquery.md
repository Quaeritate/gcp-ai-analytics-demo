# BigQuery: fixed analytics with a local reference

The BigQuery stage is implemented as an optional, bounded execution path. It
exports five normalized tables, joins service policies through a typed query
parameter, runs six fixed analyses, and compares the result with the independent
Python calculations. **The SQL and real cloud path have not been executed against
BigQuery.** Offline tests exercise export integrity, SDK request configuration,
hand-calculated response comparisons, failures and request budgets using a fake
client. They do not establish SQL syntax acceptance, IAM, regional compatibility,
actual costs or cloud cleanup.

## Local preparation

The CLI's `plan-cloud` command prepares exports and an approval plan without
constructing a Google Cloud client. Use a private ignored output directory such as
`artifacts/local/cloud-plan`. See the root README for the complete CLI workflow.

The Python interface is also available:

```python
from pathlib import Path
from gcp_ai_analytics.bigquery_pipeline import (
    BigQuerySettings, export_dataset, plan_bigquery,
)
from gcp_ai_analytics.generate_data import generate_dataset

source = generate_dataset(seed=42)
settings = BigQuerySettings("your-project-id", "operations_insights", "US")
bundle = export_dataset(source, Path("artifacts/local/cloud-plan/export"))
plan = plan_bigquery(source, settings, bundle)
```

This is ordinary local file work. It does not create resources, resolve ADC, load
data, dry-run SQL or submit a real query. `synthetic` is an explicit contract and
scope restriction, not an automatic privacy detector. Do not mark server data
synthetic to pass validation.

## Export and provenance

| Table | Source collection | Included data |
| --- | --- | --- |
| `checks` | `service_checks` | Check status, timestamp and nullable latency |
| `resources` | `resource_samples` | Nullable resource and storage-health measurements |
| `backups` | `backups` | Completion, outcome and checksum status |
| `restore_tests` | `restore_tests` | Restore test completion and outcome |
| `jobs` | `job_runs` | Run identity, lifecycle, attempts and generic failure category |

The exporter revalidates the complete source contract and BigQuery integer
ranges. Each table uses an explicit nullable/required schema, stable JSONL field
ordering and event-ID ordering. Empty tables are exported as zero-byte files.
`manifest.json` records schemas, row counts, byte counts, file SHA-256 values,
service policies, reporting boundaries and a SHA-256 of the validated source
serialized by `canonical_json`. Source list order is preserved in this source
hash; JSON object keys are sorted. Reordering events changes the source hash even
when the metric results remain equivalent.

The five JSONL files **plus the manifest** must fit within 5 MiB combined. Changed
existing outputs are rejected. Before planning and loading, the source, manifest
and exact exported bytes must agree. This detects modification after export;
there is no schema autodetection and no ignored malformed records.

Services are supplied to every query as an `ARRAY<STRUCT<...>>` parameter with
their identifier, check cadence, backup age target, restore age target and
pending-job age target. Every analysis starts or rejoins from that complete
service set. A service with no events therefore remains visible with zero
counts, null outcomes/ages and missing coverage. There is no sixth table or hidden
policy load, and there are no invented events used as policy placeholders.

## Six analyses

| Query | Semantics checked against Python |
| --- | --- |
| `checks.sql` | Latest check per cadence slot; expected partial slot; separate unknown/missing counts; success from known up/down slots; coverage from known slots |
| `freshness.sql` | Latest check/resource timestamps across available history; fresh through twice the configured cadence |
| `resources.sql` | Latest sample, measured/missing fields, nullable measurements and derived disk percentage |
| `backups.sql` | Latest attempt versus last successful backup; checksum evidence; strict overdue threshold |
| `restore_tests.sql` | Latest restore result versus last passed test; strict overdue threshold independent of backup success |
| `jobs.sql` | Completion-window cohort, pending carry-in, retries, final failures, failure categories, longest completed run and oldest pending work |

All cutoff comparisons are exclusive at `as_of`. `window_start` is inclusive.
Queries use microsecond differences for durations and threshold decisions;
display rounding is applied afterwards using the local report's conventions.
Equal-time ordering is deterministic by event ID, although the input contract
already rejects conflicting same-service observations at an identical timestamp.
History before `window_start` remains available to freshness/backup/restore
queries and pending-job calculations.

SQL comes only from the six packaged files. Timestamp values and service policies
are typed parameters. Project and dataset identifiers are validated before they
can enter a table reference. Gemini does not produce or execute this SQL.

`compare_query_results` checks service membership and every expected returned
metric against `build_report`, including null-valued columns. Incorrect metrics
or missing rows prevent a successful batch result. This comparison is meaningful
only after genuine SQL results exist; fake test rows are marked as test evidence.

`build_verified_report(source, result)` rechecks provenance and the comparison,
then builds the report from the returned SQL aggregate columns. Finding selection,
severity and summary text still use deterministic Python rules over the same
validated input. Each finding's evidence is replaced by explicitly selected SQL
columns. Event IDs, full stale-job lists and backup-attempt counts that were not
returned by these analyses are excluded. The combined Gemini path uses this
verified aggregate report; a local report on its own is not cloud evidence.

## Approved execution and limits

Before cloud use, the owner must approve the concrete generated plan, target
project/location, usage bounds and current cost basis. `execute=True` is the code
gate for that already-approved action; it is not a substitute for approval.
`BigQueryRunner` uses Application Default Credentials and never writes a key file.

The runner creates or verifies a dedicated dataset labeled
`application=server-ops-insights` and `data_classification=synthetic`. Existing
datasets with another location or without those labels are rejected. Tables are
named `ops_<first 24 source-hash characters>_<table>` in that exact dataset.
Existing tables are rejected; loads use `CREATE_NEVER` and `WRITE_EMPTY`.
Each new table receives a seven-day expiry. Dataset default expiry is requested
when creating a new dataset. The runner does not delete datasets or change an
existing dataset's metadata.

One batch permits:

- Five load submission attempts, including failed or uncertain attempts.
- Six dry-run submission attempts and six real-query submission attempts.
- A dry run before each real query. Unknown or over-limit byte estimates stop it.
- `maximum_bytes_billed=100000000` and `use_query_cache=False` on every query.
- Zero configured submission/job retries, 30-second request timeouts and
  120-second job-result timeouts.

The six real queries therefore have a combined configured ceiling of 600,000,000
billed bytes. At an illustrative US on-demand analysis rate of $6.25/TiB, this is
approximately **$0.00342 for analysis before any free allowance**. The generated
plan carries that calculation. It does not include storage, reservations or
different regional pricing, and does not promise a zero bill. Verify the current
[BigQuery pricing](https://cloud.google.com/bigquery/pricing) and the project's
billing mode before execution. Load/row validation, SQL execution, observed
processed/billed bytes and cleanup must be recorded from real job evidence.

## Failure recovery and private evidence

A deterministic batch ledger is reserved exclusively **before client
construction**. Every operation is written to it before submission. Deterministic
job IDs make an uncertain operation identifiable. Load output row counts must
match the manifest. Completed query records retain observed byte counts and cache
status when supplied by the SDK. Final rows and comparison results are saved in
the same private record directory. Project identifiers and job IDs belong in
`artifacts/local/`, not public fixtures or committed logs.

On an API error or timeout, the batch stops and records only the exception type;
raw error strings may contain private configuration. The outcome is conservatively
recorded as unknown. There is no automatic retry, cancellation, resubmission,
overwrite or cleanup. Reusing the same ledger or running the same runner twice
fails. Inspect the recorded job in the Cloud console and reconcile its actual
outcome before approving a later batch. Do not delete the ledger to simulate a
fresh allowance. Table expiry is a configured retention measure, **not observed
cleanup evidence**.

SDK behavior was checked locally against installed method signatures. The
official references for [parameterized queries](https://docs.cloud.google.com/bigquery/docs/parameterized-queries),
[query configuration and dry runs](https://docs.cloud.google.com/bigquery/docs/running-queries),
and [Python query parameter types](https://docs.cloud.google.com/python/docs/reference/bigquery/latest/query)
were consulted on October 22, 2026. Actual cloud verification remains pending.
