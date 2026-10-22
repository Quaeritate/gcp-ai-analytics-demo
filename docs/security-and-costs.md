# Costs, security and cleanup

Prices checked **October 22, 2026**. USD illustrations below use public list
prices and exclude taxes, currency conversion and unrelated account workloads.
The [first live smoke test](cloud-smoke-test.md) recorded query/token usage;
final billed charges are still pending and are distinct from list-price estimates.

## What costs money

The local generator, tests and dashboard make no cloud requests. This repository
uses standard GitHub Actions runners in a public repository, whose execution
minutes are [free](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
The workflow uploads no Actions artifacts and uses no paid larger runners.
Existing computer, electricity and development-tool subscriptions are separate.

Optional cloud execution uses BigQuery query/storage capacity and Gemini tokens.
There is no deployed VM, persistent API service, scheduled task, reserved
warehouse capacity or hosted model endpoint in this design.

## Concrete first-run plan

| Operation | Enforced scope |
| --- | --- |
| Dataset | One explicit project/dataset, labeled synthetic; default name `operations_insights`, location `US` |
| Tables | Five source-hash-named tables; seven-day expiry; existing tables rejected |
| Data | Synthetic checks, resources, backups, restore tests and jobs; combined exports plus manifest <=5 MiB |
| Loads | At most five attempts; explicit schemas, no autodetection, no bad records accepted |
| SQL | Six fixed analyses; a dry run before each; at most six query attempts |
| Query bytes | Maximum 100,000,000 billed bytes per query; 600,000,000 combined configured ceiling |
| AI smoke test | `cloud-demo` attempts one generation; reviewed allowance at most three attempts across an approved smoke-test batch |
| AI request | Text only; <=8,000 assembled characters including instructions/schema; <=1,024 output tokens; 30-second request timeout |
| Automatic follow-ups | SDK retries, continuation, function calling and tools disabled |
| Evaluation | Separate 24-case workload; shared maximum 30 generation attempts; no automatic retries |

Failures and timeouts consume an attempted-request allowance. Limits apply to
the declared run/batch, not to the whole billing account. Starting a new command
is not permission to repeat an uncertain billed operation.

## Cost illustrations

[BigQuery on-demand analysis](https://cloud.google.com/bigquery/pricing) at
$6.25/TiB gives `600,000,000 / 2^40 * 6.25 = $0.00341` for the six-query byte
ceiling, before any free allowance. Storage is charged separately according to
actual stored size, region and billing model. For a fixture below 5 MiB retained
for seven days, storage is expected to be far below one cent; verify the actual
logical size and applicable rate. Batch loading uses the shared load pool and
this design requests no reservation.

[Gemini 3.5 Flash-Lite global Standard pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)
is $0.30 per million input tokens and $2.50 per million output tokens, including
reasoning. **Characters are not tokens.** The following is a planning scenario,
assuming 8,000 billed input tokens and 1,024 billed output tokens per request:

| Scenario | Calculation | Illustrative cost |
| --- | --- | ---: |
| One triage request | `(8000 * 0.30 + 1024 * 2.50) / 1,000,000` | $0.00496 |
| Three smoke-test attempts | `3 * $0.00496` | $0.01488 |
| 24-case evaluation | `24 * $0.00496` | $0.11904 |
| Full 30-attempt evaluation allowance | `30 * $0.00496` | $0.14880 |

The first bounded cloud batch is therefore expected to be **a few cents** under
these assumptions, plus tiny storage. This is not an exact quote or hard dollar
cap. Before running, verify complete token accounting and output-limit semantics
for the selected model. After running, retain actual input, candidate, reasoning
and total token counts and check billing records; do not sum overlapping usage
fields as though each were independently billable. Timeouts can leave a remote
outcome unknown.

A hypothetical daily run with one such AI request would spend about $0.15/month
on inference plus about $0.10/month at the configured daily query-byte ceiling,
before storage and free allowances. **No daily schedule is configured.** Real
server data volume, query frequency, model choice, retained logs and hosting
would change that estimate and need a new plan.

Budget alerts can be set at a small monthly amount (for example $5 with
50%/80%/100% notifications), but
[ordinary budget alerts do not cap spending](https://docs.cloud.google.com/billing/docs/how-to/budgets).
A budget amount is not authorization to consume it. There is no account-wide
spending cap enforced by this program.

## Observed first-test usage

The six real queries billed 73,400,320 bytes. Three model attempts used 5,051
reported input tokens and 1,666 candidate output tokens in total; the first two
responses were rejected by application validation. All attempts count toward
usage. At the rates above, the combined query/inference estimate is **$0.00609753**,
before storage, taxes, free allowances and credits. BigQuery reported 146,104
logical storage bytes. This is measured usage with an estimated list-price cost,
not an invoice or a guarantee of a zero card charge.

Any credit application and residual charges require delayed billing records.
No recurring workflow was set
up. Do not upgrade an account or provision additional services merely to reproduce
these results without reviewing the changed cost scope.

## Data and execution boundaries

The public examples contain only generated aliases and synthetic events. The
contract requires explicit synthetic classification and rejects extra fields,
invalid timestamps, inconsistent states and conflicting duplicates. The label
is a contract, not a private-data detector. Real telemetry requires a separately
agreed export and private storage boundary.

Credentials, billing identifiers, real project/job IDs and raw cloud receipts
must stay outside Git. ADC replaces key files. The application executes only
packaged parameterized SQL. Gemini can select known evidence and reviewed checks;
it cannot run tools or commands. Schema/reference validation reduces unsupported
output but does not prove natural-language factuality. Human review remains
required, including prompt-injection evaluation.

## Cleanup after an approved run

1. Read the private plan and ledger; verify the exact project, dataset and five
   table names. Reconcile any unfinished/uncertain jobs first.
2. Retain only sanitized evidence needed for the demonstration.
3. Using the BigQuery console or SDK, remove only the five demonstration tables after
   owner approval. Inspect the dataset before deleting it; do not recursively
   remove a dataset that contains unrelated tables.
4. Confirm a fresh listing no longer contains those resources. Seven-day expiry
   is a fallback; it does not establish that deletion already occurred.
5. Review delayed billing records and document residual resources/charges.
   Remove project-specific IAM grants or the dedicated project only with
   explicit authorization. ADC may be shared with other work; do not revoke it
   automatically.

The application has no destructive cleanup command. For the first smoke test,
an explicitly approved operator cleanup removed the five source tables and empty
dataset; fresh API reads verified removal. Six provider-managed temporary query
results remain with a recorded expiry on the following day. Google documents
[no storage charge for cached query-result tables](https://docs.cloud.google.com/bigquery/docs/cached-results).
The [smoke-test record](cloud-smoke-test.md#cleanup-and-remaining-scope) preserves
this distinction. Final charges and credit application remain unverified.
