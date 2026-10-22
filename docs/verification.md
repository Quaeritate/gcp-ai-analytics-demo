# Verification record

**October 22, 2026 · Version 0.1.0 · Matej Bicej**

## Verified locally

| Check | Observed result |
| --- | --- |
| Offline suite | **129 passed** on Windows / Python 3.12.10 |
| Ruff lint and format | Passed; 20 Python files checked |
| Dependency consistency | `pip check` passed |
| Installation | Offline editable install succeeded with recorded dependencies |
| Distribution | Wheel built; six SQL resources and the evaluation corpus included |
| Demo reproduction | Fixed-seed dataset and JSON/Markdown/HTML outputs deterministic; import roundtrip agrees |
| Browser verification | Desktop and 390px narrow layouts inspected; native evidence disclosure works; screenshots saved |
| Warehouse preparation | Five normalized exports, schemas, counts, SHA-256 manifest and six-query plan generated offline |
| AI preparation | Default local prompt: 5,313 characters including schema; six findings supplied and 15 explicitly omitted |
| Combined evidence | SQL-derived evidence fixture fits in 5,292 characters; tests prove returned SQL values reach the model adapter |
| Evaluation corpus | 24 fixtures validated locally; zero inference requests; model accuracy unmeasured |
| SDK behavior | In-process HTTP tests check schema serialization, disabled retry/continuation and ADC precedence over ambient test keys |
| Public content review | Outgoing files checked for credential patterns, private paths and infrastructure context; fixtures are generated synthetic data |
| Hosted CI | **Passed on Windows and Linux**, Python 3.12, for implementation commit `52a35f5`; [observed run](https://github.com/Quaeritate/gcp-ai-analytics-demo/actions/runs/39834905000) |

Published at [Quaeritate/gcp-ai-analytics-demo](https://github.com/Quaeritate/gcp-ai-analytics-demo).
Commit author and committer: **Matej Bicej**. The hosted workflow also reproduced
the committed example and validated the evaluation corpus without inference.

No live Google Cloud operation, private server collection, notification or
remediation has been performed. Local fixtures, injected clients and HTTP mock
transports are not cloud execution evidence.

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

## Pending evidence

| Capability | Still required |
| --- | --- |
| BigQuery | Real table creation/load, SQL syntax acceptance, row counts and independent metric parity |
| Gemini through Google Cloud | Actual request success, returned model version, token usage and validated response |
| Model evaluation | Real successful/unsuccessful examples plus human factuality/usefulness review |
| Combined cloud demo | Observed SQL-derived evidence passed to actual inference |
| IAM, billing and cleanup | Verified permissions, actual charges, fresh resource-removal evidence |
| Server integration | Separately qualified private metadata source; no live collector implemented |

The supported claim is a tested synthetic analytics application with implemented,
offline-tested Google Cloud adapters. Cloud execution, operational impact and
production readiness remain unproven.
