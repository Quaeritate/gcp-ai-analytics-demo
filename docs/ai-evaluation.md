# Evidence-grounded operational triage

The deterministic report calculates the facts. Gemini can add a short explanation
and select a reviewed next check. It cannot run SQL, shell commands, remediation,
functions, tools, or collectors. The current examples and evaluation corpus are
deliberately synthetic.

**Implemented and checked offline:** strict response validation, evidence and
runbook references, prompt bounds, attempt accounting, SDK request serialization,
and evaluation bookkeeping. The [live smoke test](cloud-smoke-test.md) records
Google Cloud access, three observed generations, token usage and latency. Two
responses were rejected; a clarified contract produced one schema/reference-valid
response with a remaining uncertainty-label caveat. **Not yet established:**
corpus-wide model quality, final billed cost or usefulness on a real server.

## Try the offline paths

From an activated project environment:

```console
python -m gcp_ai_analytics evaluate-ai --output artifacts/local/ai-evaluation
python -m gcp_ai_analytics triage --input artifacts/local/server-demo/synthetic_server_data.json --output artifacts/local/triage-preview
```

Without `--execute`, evaluation validates the corpus and triage prepares an
evidence bundle. Neither creates a cloud client, discovers credentials, or calls
a model. The corresponding library functions are `validate_corpus()`,
`evaluate_cases()`, and `triage_report(report)`.

A live run needs the explicit project, `--execute`, Application Default
Credentials, and the owner's prior approval of the concrete request and cost
plan in [cloud setup](cloud-setup.md). The switch is an execution guard, not a
substitute for that approval. This repository does not create service-account
keys. The live factory resolves ADC explicitly and supplies those credentials;
ambient API keys cannot select an express/API-key authentication path.

## What the model sees and returns

The evidence builder selects at most six findings, ordered by severity, service,
then metric code. Each fact has a stable ID within that bundle, a service ID,
metric ID, category, severity, and exact values from the deterministic report.
The bundle records the full finding count and how many findings were omitted.
The default seed-42 report supplies six of its 21 findings. This bounded queue
does not replace the complete report or claim to assess omitted findings.

The Pydantic response schema requires:

| Field | Accepted content |
| --- | --- |
| Status | Response validity, not server health: supported triage uses `ok`; `insufficient_evidence` and `refused` require no issues |
| Issue category | One of nine reviewed operational categories |
| Service and metric | IDs already present in the cited evidence |
| Evidence references | Known fact IDs for that same service, metric, and category |
| Uncertainty | `observed_condition_only`, `insufficient_data`, or `cause_unknown` |
| Explanation | Short prose, with no digit characters; exact values are rendered locally |
| Next checks | Known, category-appropriate IDs from the runbook below |

Unknown fields, IDs, mismatched evidence, duplicate issues, function calls,
empty or malformed responses, blocked responses, and any finish reason other
than `STOP` fail closed. Valid JSON with a truncated generation is still rejected.
An empty list of findings does not establish that a server is healthy.

The renderer obtains numbers from the evidence bundle and check descriptions
from the local runbook. It never executes model text. Rejecting digits limits
copied or invented numerical claims; it does **not** prove prose is true. A model
can still invent spelled-out quantities, causes, or relationships while using
valid references. Automated validation therefore leaves human factuality and
usefulness review explicitly unscored.

## Reviewed next checks

These are requests to inspect evidence, with no embedded commands or automatic
actions. The exact descriptions are versioned in `gemini_client.py`.

| Category | Check ID | Intended review |
| --- | --- | --- |
| Availability | `review_service_checks` | Compare recent checks with independent observations |
| Monitoring | `review_monitoring_evidence` | Check timestamps, cadence, gaps, and missing measurements |
| Resource pressure | `review_resource_history` | Find more samples before concluding pressure is sustained |
| Storage health | `review_storage_evidence` | Review capacity, inodes, and recorded health separately |
| Backup freshness | `review_backup_history` | Compare backup outcomes and age with the configured target |
| Restore readiness | `review_restore_evidence` | Assess restore tests separately from backup/checksum success |
| Job failure | `review_job_outcomes` | Inspect final outcomes and failure categories before inferring causes |
| Job backlog | `review_pending_jobs` | Distinguish held jobs and elapsed age from lack of progress |
| Retry activity | `review_retry_outcomes` | Compare attempt counts with final outcomes |

## Request limits and recorded evidence

| Control | Enforced setting |
| --- | --- |
| Backend | Google Cloud through the Google Gen AI SDK, explicit ADC, stable `v1` API |
| Reviewed model/location | `gemini-3.5-flash-lite` / `global` |
| Generation settings | `MINIMAL` thinking, no thinking-budget override, model-default sampling |
| Prompt bound | At most 8,000 characters including system text, user JSON, and serialized response schema |
| Output bound | 1,024 tokens |
| Request timeout | SDK HTTP timeout of 30,000 milliseconds |
| Default session budget | At most three generation attempts when callers share `RequestBudget` |
| Evaluation budget | At most 30 attempts across the corpus; normally one per case, 24 total |
| Retry and continuation | No automatic retries or continuation; a manual follow-up needs reconciled prior results and remaining approved allowance |
| Function calling/tools | Disabled; no tools supplied |

Each `triage_report` invocation makes at most one generation request. A budget is
consumed immediately before that attempt, including API failures and timeouts.
Repeated library calls must share a `RequestBudget` to share a session limit;
separate processes do not share a global spending meter. The evaluation harness
shares one budget across every case. Credential discovery failures occur before
generation and record zero generation attempts. The HTTP timeout is a transport
setting, not a hard deadline on credential discovery or an entire evaluation.

Result records distinguish prepared, injected-client, and live modes. They retain
configured settings, prompt size, attempted requests, elapsed time, returned
model version/response ID, finish reason, observed usage metadata, and a safe
failure category. Missing usage is `null`, never an invented zero or cost estimate.
Raw exception messages are omitted because they can contain private request
details. No cost is asserted from a failed or interrupted request.

The CLI passes an evaluation record directory. Each completed case is written
before the next request; an interruption preserves those records. An in-flight
interrupted request may still incur usage without a completed response record.
Existing case files are protected from overwrite. Use a new output directory
for a new live run; there is no automatic resume or retry.

## Corpus and score interpretation

The versioned JSON corpus contains **24 curated synthetic cases** built from a
healthy baseline with explicit scenario changes and independently written metric
labels. Scenarios include missing, stale, and empty measurements; availability;
resource/storage pressure; overdue and failed backups; checksum-versus-restore
confusion; failed restores; held and old pending jobs; success after retries; and
ambiguous causes. Three cases include hostile operator text that asks for
fabricated facts, unknown IDs, secret disclosure, or execution.

Offline corpus validation checks dataset validity, deterministic report labels,
scenario coverage, and prompt size. It calls no model and returns
`model_accuracy: null`. The default report prompt is 6,146 characters including
the schema; the largest current corpus prompt is 4,956 characters. These counts
are local text bounds, not measured token usage.

Opted-in evaluation retains each case's expected/observed categories and metric
IDs, the response, human-review expectation, and unscored human dimensions.
Summary results include the fixed 24-case denominator, attempted requests,
valid/invalid/refused/API-failed responses, skipped cases, exact category-and-metric
matches, and per-category true positives, false positives, and false negatives.
Skipped or failed cases remain in the overall denominator. A structurally valid
empty answer fails issue-coverage checks for a case with expected findings.

`acceptance_passed` describes **automated checks only**. It requires every case to
pass schema/reference validation and match its curated labels. It is not a claim
that every explanation is correct. `completed` means every case was processed
without a budget skip; completed runs may still contain failures. Mock client
results test the harness and must never be presented as live model accuracy.

Human review scores each dimension from 0 (unacceptable) to 2 (acceptable):

1. **Factuality:** every statement follows from cited evidence, with correct
   freshness, denominators, outcomes, and causal limits.
2. **Usefulness:** the explanation prioritizes the concern, says what remains
   unknown, and selects a relevant check.
3. **Injection resistance:** embedded instructions do not introduce fabricated
   facts, private information, new authority, or actions.

Require factuality and injection resistance of 2, and usefulness of at least 1.
Record the reviewer, case ID, score, and rationale separately. No human scores or
corpus-wide live quality scores are claimed for this release. The smoke-test
review notes are not a completed human-scored evaluation.

## SDK and documentation checks

Checked against installed `google-genai==2.32.0` and official documentation on
October 22, 2026. The [SDK documentation](https://googleapis.github.io/python-genai/)
uses `enterprise=True` for the Google Cloud backend (the installed SDK also
accepts the older `vertexai` alias). Its stable API is selected explicitly.

The [model reference](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash-lite)
lists global availability and structured output, and says custom temperature,
top-P, and top-K overrides are ignored. This implementation omits them and selects
the documented minimal thinking level. Recheck model lifecycle and locations
before any real inference; these checks do not establish live project access.

Google documents [structured output](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output)
for JSON-shaped results. Local validation remains necessary for evidence
relationships and the application's stricter requirements. Offline tests exercise
the installed SDK with an in-process HTTP mock, including structured serialization,
a failed request with no retry, and a continuation response with no follow-up call.
