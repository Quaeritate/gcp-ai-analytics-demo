# Verification record

**October 22, 2026 · Version 0.1.0 · Matej Bicej**

## Verified locally

| Check | Observed result |
| --- | --- |
| Offline suite | **132 passed** on Windows / Python 3.12.10, including the live-discovered response-status regression |
| Ruff lint and format | Passed; 20 Python files checked |
| Dependency consistency | `pip check` passed |
| Installation | Offline editable install succeeded with recorded dependencies |
| Distribution | Wheel built; six SQL resources and the evaluation corpus included |
| Demo reproduction | Fixed-seed dataset and JSON/Markdown/HTML outputs deterministic; import roundtrip agrees |
| Browser verification | Desktop and 390px narrow layouts inspected; native evidence disclosure works; screenshots saved |
| Warehouse preparation | Five normalized exports, schemas, counts, SHA-256 manifest and six-query plan generated offline |
| AI preparation | Current local prompt: 6,146 characters including schema; six findings supplied and 15 explicitly omitted |
| Combined evidence | Current SQL-derived evidence prompt fits in 6,125 characters; the live follow-up used the saved verified SQL aggregates |
| Evaluation corpus | 24 fixtures validated locally; zero corpus inference requests; corpus-wide model accuracy unmeasured |
| SDK behavior | In-process HTTP tests check schema serialization, disabled retry/continuation and ADC precedence over ambient test keys |
| Public content review | Outgoing files checked for credential patterns, private paths and infrastructure context; fixtures are generated synthetic data |
| Hosted CI | **Passed on Windows and Linux**, Python 3.12, for cloud-verification/fix commit `ff61ed7`; [observed run](https://github.com/Quaeritate/gcp-ai-analytics-demo/actions/runs/39849132313) |

Published at [Quaeritate/gcp-ai-analytics-demo](https://github.com/Quaeritate/gcp-ai-analytics-demo).
Commit author and committer: **Matej Bicej**. The hosted workflow also reproduced
the committed example and validated the evaluation corpus without inference.

The separate [live smoke-test record](cloud-smoke-test.md) preserves observed
BigQuery and Gemini results, including failures and limitations. No private
server collection, notification or remediation has been performed. Local
fixtures and HTTP mock transports remain separate from actual cloud evidence.

## Reproducible fixture

Seed `42`, generator version `1`, aliases `compute`, `documents`, `photos`.
UTC reporting interval: `[2026-09-21, 2026-10-19)`.

| Records | Count |
| --- | ---: |
| Service checks | 1,980 |
| Resource samples | 337 |
| Backup attempts | 81 |
| Restore tests | 3 |
| Job runs | 112 |
| Total | **2,513** |

The fixture intentionally yields **21 findings: four critical, 15 warning and
two informational**. These are constructed conditions, not live findings.

Canonical dataset SHA-256:
`23f6b84366462fc39a859150127a397d874ce749ade44afca5e293d37db8d68c`.

## What tests establish

Hand-calculated cases exercise cadence-slot coverage, unknown/missing samples,
window edges, stale resource suppression, raw threshold comparisons, independent
backup/restore evidence, pending carry-in and retries versus final outcomes.
Input tests cover conflicting duplicates, invalid timestamps, contradictory jobs,
measurement types, explicit synthetic labels and source limits.

Cloud tests cover export tampering, BigQuery integer ranges, missing/duplicate
SQL rows, numeric comparisons, preserved ledgers, bounded attempts, oversized
queries and failure paths. CLI integration tests ensure mismatches prevent
inference and BigQuery-only operation does not depend on Gemini prompt limits.
Mocked SDK requests exercise the installed transport and serializer without a
network service. A live evaluation returns a nonzero exit status when automated
acceptance fails and retains each completed case separately.

## Observed cloud smoke test

On October 22, 2026, the original combined command completed five synthetic loads
and six fixed SQL queries in BigQuery US. All **189 metrics matched** the independent
Python calculation, with no query-cache hits. A fresh metadata inspection also
verified all eleven load/query jobs were DONE without errors, 2,513 loaded rows,
and 146,104 logical storage bytes.

The original combined command returned failure after the first Gemini response
failed validation. A separately recorded diagnostic generation also failed:
it returned a non-success top-level status alongside six findings. Schema
descriptions and instructions were clarified without relaxing validation. The
third and final approved generation reused the same verified SQL evidence and
passed schema/reference checks. No load or query was repeated.

This establishes live component execution and the SQL-to-inference evidence
path, not a fresh successful combined CLI run with the revised instructions.
The final response still uses `observed_condition_only` for unknown monitoring
slots, where the prompt requests `insufficient_data`; retain this review caveat.
The [sanitized receipt](../examples/synthetic/cloud-smoke-test.json) preserves
usage, attempt history and the response. No human scores are claimed.

After explicit owner approval, all five source tables and the empty dataset were
deleted and freshly verified absent on October 22, 2026 at 20:31 UTC. The project
and billing link remain active. Six provider-managed query-result tables in an
anonymous dataset remain until their recorded expiry the following day; they
were matched to the six query jobs. See the [cleanup record](cloud-smoke-test.md#cleanup-and-remaining-scope).

## Remaining evidence

| Capability | Still required |
| --- | --- |
| Model evaluation | Obtain separate approval, then execute the 24-case corpus and record human factuality/usefulness/injection-resistance scores |
| Revised combined CLI | A new full cloud run after the instruction clarification, if separately justified and approved |
| Runtime IAM | This smoke used the project owner's ADC; a dedicated least-privilege runtime identity has not been validated |
| Billing | Final charge and credit records after Google's reporting delay; list-price usage is an estimate |
| Server integration | Separately qualified private metadata source; no live collector implemented |

The supported claim is a tested synthetic analytics application with observed
BigQuery parity and Gemini integration, a documented model-contract correction,
and remaining semantic limits. Operational impact and production readiness
remain unproven.
