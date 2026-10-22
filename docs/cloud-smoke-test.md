# Live cloud smoke test

**October 22, 2026 · Matej Bicej · Synthetic data only**

Five BigQuery loads and six SQL analyses completed against Google Cloud. All
**189 compared metrics matched the independent local calculations**. The first
two Gemini responses were rejected. After clarifying the response-status
instructions, a third request passed schema and evidence-reference validation.
An uncertainty-label caveat remains; this is not full semantic acceptance or a
model-accuracy evaluation.

The [sanitized execution record](../examples/synthetic/cloud-smoke-test.json)
contains the observed counts, usage, unchanged final explanations, cited
synthetic evidence and review notes. Private execution receipts are retained
outside source control.

## Reproducibility and execution path

The source baseline was commit
[`2d94c6e3704be61cd0a8d7b7a28a7dd6669a84f5`](https://github.com/Quaeritate/gcp-ai-analytics-demo/commit/2d94c6e3704be61cd0a8d7b7a28a7dd6669a84f5).
The fixture used seed `42`, generator version `1`, and canonical dataset SHA-256
`23f6b84366462fc39a859150127a397d874ce749ade44afca5e293d37db8d68c`.

The third request used the same baseline plus clarified system instructions and
schema descriptions in `gemini_client.py`. Its recorded file SHA-256 was
`4ecf3897d7626cf0312e0a72940a3bd862655348d97883ab2fce5cd70fa26486`.
Response validators, byte/token limits and retry settings were not relaxed.
The focused regression tests and full **132-test offline suite** passed.

The original combined `cloud-demo` invocation finished BigQuery verification but
rejected its model response. Two manually initiated, model-only follow-ups reused
the saved SQL-derived evidence. **BigQuery was not rerun.** This record does not
claim that the original combined invocation completed successfully or that the
revised combined command was rerun end to end.

## Observed BigQuery results

The warehouse ran in `US`, using five explicit schemas and six fixed,
parameterized queries. No model-generated SQL was executed.

| Source | Successfully loaded rows |
| --- | ---: |
| Service checks | 1,980 |
| Resource observations | 337 |
| Backup attempts | 81 |
| Restore tests | 3 |
| Job runs | 112 |
| **Total** | **2,513** |

| Analysis | Processed bytes | Reported billed bytes |
| --- | ---: | ---: |
| Checks | 98,124 | 10,485,760 |
| Freshness | 40,140 | 20,971,520 |
| Resources | 32,584 | 10,485,760 |
| Backups | 4,512 | 10,485,760 |
| Restore tests | 128 | 10,485,760 |
| Jobs | 9,748 | 10,485,760 |
| **Total** | **185,236** | **73,400,320** |

All six dry runs and six real queries completed. Each query returned three
service rows and reported `cache_hit=false`. The billed-byte total is **70 MiB**;
each query stayed below its configured 100,000,000-byte ceiling. A separate local
recomparison of the returned rows confirmed **189 matches and zero mismatches**.

## Model attempts and the discovered contract ambiguity

All three real requests used `gemini-3.5-flash-lite`, the `global` endpoint, API
`v1`, minimal thinking and a 1,024-output-token limit. Each returned `STOP`.
There were no automatic retries, continuations or tool executions.

| Attempt | Prompt characters | Input tokens | Candidate output tokens | Outcome |
| --- | ---: | ---: | ---: | --- |
| 1 | 5,292 | 1,625 | 398 | Rejected by schema/evidence validation |
| 2 | 5,292 | 1,628 | 600 | Rejected: non-OK response contained issues |
| 3 | 6,125 | 1,798 | 668 | Schema and references validated; caveat below |
| **Total** | — | **5,051** | **1,666** | **Three attempts** |

The first rejected response was not retained as raw text, so its exact offending
field is unknown. The second response returned top-level
`status=insufficient_evidence` together with six issues. The contract requires
non-OK responses to contain no advice, so rejection was correct.

The clarification explains that top-level status describes response validity,
not server health. Supported triage uses `ok` with a null refusal reason even
when services are unhealthy or evidence is uncertain; each issue carries its
own uncertainty. The third response satisfied that structural contract and
covered all six supplied findings. Fifteen other findings were explicitly omitted
from the bounded model input.

## Final explanations and review notes

These are the third response's original explanations. Their evidence references
and numerical values are preserved in the JSON record rather than rewritten.
Review notes below are limitations of the observed output; they are not scores
or an approval attributed to the project owner.

| Service / metric | Model explanation | Cited evidence |
| --- | --- | --- |
| compute / `pool_degraded` | Storage pool state is degraded. | `fact_1`: fresh observation, degraded pool |
| documents / `free_inodes_low` | Available file inodes percentage is low. | `fact_2`: fresh observation, 4% free inodes |
| documents / `latest_check_down` | Latest service check status is down. | `fact_3`: latest fresh check is down |
| photos / `latest_restore_failed` | Latest restore attempt failed without a recent passed restore. | `fact_4`: latest restore failed; no passed restore recorded |
| compute / `monitoring_coverage_gap` | Monitoring coverage exhibits gaps with unknown slots. | `fact_5`: 659 known, 13 unknown and zero missing slots out of 672 |
| compute / `restore_test_overdue` | Restore testing has exceeded the maximum age threshold. | `fact_6`: last passed restore 40 days old; threshold 30 days |

The monitoring explanation identifies unknown slots, but its uncertainty field
remains `observed_condition_only`. The prompt requested `insufficient_data` for
unknown evidence. Current validation permits both enum values and does not
enforce this semantic relationship. **This discrepancy remains visible and
unresolved; the original response has not been edited.**

The restore explanation also needs its evidence boundary kept explicit: no
passed restore is recorded in the supplied data. That does not prove no
successful restore happened outside the dataset. A fresh down check likewise
does not establish a continuous outage duration.

## Usage-based cost estimate

Using the October 22, 2026 list prices of
[$6.25/TiB for BigQuery](https://cloud.google.com/bigquery/pricing) and
[$0.30/million input tokens and $2.50/million output tokens for Gemini](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing):

| Component | Calculation | USD estimate |
| --- | --- | ---: |
| Six queries | `73,400,320 / 2^40 * 6.25` | $0.00041723 |
| All three model requests | `(5,051 * 0.30 + 1,666 * 2.50) / 1,000,000` | $0.00568030 |
| **Combined queries and generation** | | **$0.00609753** |

That is approximately **0.61 US cents** before free allowances or credits,
storage, taxes and currency conversion. It is a calculation from observed job
and token metadata, **not a verified invoice**. Reasoning/cache token fields were
null rather than measured zero; each response's reported total equaled its
prompt plus candidate tokens. Delayed billing records remain unverified.

## Cleanup and remaining scope

The five demonstration tables and their now-empty dataset were **deleted and
verified absent on October 22, 2026 at 20:31 UTC**, after explicit owner approval.
Each table returned NotFound after deletion; a fresh listing showed zero tables
before non-recursive dataset deletion, and a subsequent dataset listing confirmed
its absence. The project, billing link and local evidence were retained.

One anonymous dataset remains with six temporary query-result tables, matched to
the six completed query jobs. Their recorded expiry times are October 23, 2026
around 20:17 UTC. These provider-managed results were left to expire; they are
not the five loaded source tables. Google documents
[no storage charge for temporary cached query results](https://docs.cloud.google.com/bigquery/docs/cached-results).
Their future expiry has not yet been observed. Deletion of the source tables
does not establish a finalized bill or erase cloud job history.

No recurring schedule, cloud VM or hosted application service was deployed.
The dashboard remains a labeled local reference. This test used only generated
data and did not collect real server measurements, send notifications or perform
remediation.

The separate **24-case live model evaluation was not run**. One dataset and
three attempts do not establish model reliability, production readiness or
measured business impact. Owner review, the uncertainty-label limitation and
final billing remain outstanding.
