# Practical use and private integration

The report helps a server owner prioritize three decisions: whether important
data is protected, whether services are usable, and which unfinished work needs
attention. The local workflow is useful without Google Cloud; BigQuery adds a
SQL analytics path and Gemini adds reviewed triage recommendations.

## First integration boundary

A future adapter should export a bounded set of metadata: service aliases,
observation timestamps, check outcomes, resource readings, backup receipts,
restore-test receipts and job outcomes. Agree the exact fields, retention,
collection effects and destination before connecting a source.

Keep alias mappings and real infrastructure configuration private. Exclude
contents, filenames, user identifiers, network addresses, authentication data,
raw logs and arbitrary command output. A status command may open a database or
initialize state; inspect its behavior before treating it as a collector.

The current Dataset contract deliberately requires `data_classification` to be
`synthetic`. A private adapter needs a separate explicit contract and storage
boundary; changing the label of real records is not an integration mechanism.
No real data has been collected or uploaded by this project.

## Suggested order

1. Qualify one application job export and one source of backup receipts.
2. Add host/service health and resource snapshots with explicit collection cadence.
3. Add expected schedules, per-volume accounting and tested backup-generation links.
4. Accumulate enough history for comparable periods and capacity forecasts.
5. Measure usefulness: time to identify a problem, repeated false findings,
   coverage gaps resolved, and whether recommendations led to verified outcomes.

The [38-question roadmap](server-insight-catalog.md) keeps broader server coverage
visible. Prioritize by operational value and available evidence. No business
improvement or production readiness is claimed before measurement.
