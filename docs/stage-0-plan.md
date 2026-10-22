# Implementation and acceptance plan

**Owner: Matej Bicej.** Server & App Operations Insights turns synthetic service,
resource, backup, restore and job records into an evidence-backed attention list.
The [architecture](architecture.md) describes the local and cloud paths.

## Design decisions

- One Python package and CLI keep the demonstration reproducible.
- Strict Pydantic contracts reject contradictory records and ambiguous timestamps.
- A deterministic local engine provides an independent BigQuery reference.
- Fixed SQL templates and explicit parameters keep the warehouse boundary reviewable.
- Gemini selects evidence and reviewed checks; deterministic code renders facts.
- A standalone HTML report works without a web service, external assets or JavaScript.
- Real infrastructure collection is a separate [integration boundary](practical-use-proposal.md).

## Metric semantics

The reporting interval is `[window_start, as_of)` in UTC. Historical observations
before the window can establish latest evidence. Events at or after `as_of` are
rejected. Identical event IDs collapse; conflicting duplicates fail validation.

Checks occupy cadence slots anchored to the window start. The latest check in a
slot determines its outcome. Known observations are up plus down; the sampled
success rate is up / known. Coverage is known / expected slots. Unknown and
missing slots never count as successful. Freshness expires after twice the
configured check interval.

Resource thresholds use the latest observation and raw values before display
rounding. Stale observations do not generate current capacity alerts. Default
warning/critical thresholds are 85%/95% utilization and 10%/5% free inodes.
Missing measurements remain visible.

Backup success age, latest attempt failure, checksum status and restore-test
age are independent. The contract does not prove which backup generation a
restore test covered. Completed jobs are selected by finish time in the window;
unfinished carry-in jobs remain visible. Extra attempts are distinct from final
failures. Old pending work is measured since start, not since last progress.

## Acceptance stages

| Stage | Evidence required |
| --- | --- |
| Local analytics | Repeatable dataset; hand-calculated edge cases; JSON, Markdown and HTML outputs |
| BigQuery implementation | Five explicit load schemas, six SQL analyses, bounded execution and offline client tests |
| BigQuery live verification | Successful synthetic loads, observed jobs and SQL/local parity |
| Gemini implementation | Structured output, validated evidence/runbook references, failure handling and labeled corpus |
| Gemini live evaluation | Actual model responses, success/failure examples, label and grounding scores |
| Combined cloud demo | Verified BigQuery aggregates gate the Gemini interpretation |
| Publication | Clean repository, demo screenshot, setup, tests, limitations and cost documentation |
| Private integration | Separately agreed source contract, collection effects and retention |

[Verification](verification.md) records which stages have actually run. Cloud
adapters and mocked tests do not establish real cloud execution.

Before any billable Google Cloud operation, prepare the concrete request/resource
plan, usage limits and cost basis and obtain the owner's approval. Use ADC;
never create service-account key files. No generated SQL, command, remediation
or notification is executed from model output.
