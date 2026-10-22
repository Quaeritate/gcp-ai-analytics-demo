# Server & App Operations Insights

**Synthetic demonstration — these are not observations of your server.**

Reporting window: 2026-09-21T00:00:00+00:00 to 2026-10-19T00:00:00+00:00 (exclusive).

## What needs attention

- **CRITICAL · compute**: The latest storage pool observation reports degraded.

  Evidence: Event id: resource-compute-0671; Observed at: 2026-10-18T23:00:00+00:00; Age hours: 1.00; Pool health: degraded
- **CRITICAL · documents**: Free inodes are low in the latest sample.

  Evidence: Event id: resource-documents-0671; Observed at: 2026-10-18T23:00:00+00:00; Age hours: 1.00; Free inodes pct: 4.00; Warning threshold pct: 10; Critical threshold pct: 5
- **CRITICAL · documents**: The latest fresh service check reports down.

  Evidence: Event id: check-documents-0671; Observed at: 2026-10-18T23:00:00+00:00; Age hours: 1.00; Observed status: down
- **CRITICAL · photos**: The latest recorded restore test failed.

  Evidence: Event id: restore-photos; Completed at: 2026-10-17T00:00:00+00:00; Last passed restore at: Unknown / not applicable
- **WARNING · compute**: Some expected monitoring slots have no known up/down observation.

  Evidence: Expected slots: 672; Known status slots: 659; Missing slots: 0; Unknown slots: 13; Monitoring coverage pct: 98.07
- **WARNING · compute**: The most recent successful restore test exceeds its configured age target.

  Evidence: Event id: restore-compute; Completed at: 2026-09-09T00:00:00+00:00; Age days: 40.00; Max age days: 30.00
- **WARNING · documents**: Some job runs are blocked at the report cutoff.

  Evidence: Blocked runs: 1
- **WARNING · documents**: Some job runs completed with a final failure during the reporting window.

  Evidence: Failed runs: 4; Completed runs: 55; Failure categories: {"dependency_unavailable": 4}
- **WARNING · documents**: The latest recorded backup attempt failed.

  Evidence: Event id: backup-documents-27; Completed at: 2026-10-18T02:00:00+00:00; Last success at: 2026-10-17T02:00:00+00:00
- **WARNING · documents**: Memory utilization exceeds the demonstration threshold in the latest sample.

  Evidence: Event id: resource-documents-0671; Observed at: 2026-10-18T23:00:00+00:00; Age hours: 1.00; Metric: memory_pct; Value pct: 94.00; Warning threshold pct: 85; Critical threshold pct: 95
- **WARNING · documents**: Some expected monitoring slots have no known up/down observation.

  Evidence: Expected slots: 672; Known status slots: 636; Missing slots: 24; Unknown slots: 12; Monitoring coverage pct: 94.64
- **WARNING · documents**: Some pending job runs exceed the configured pending-age target.

  Evidence: Stale pending runs: 1; Oldest pending age hours: 20.00; Age target hours: 4.00; Job ids: ["job-documents-054"]
- **WARNING · photos**: The most recent successful backup exceeds its configured age target.

  Evidence: Event id: backup-photos-24; Last success at: 2026-10-15T02:00:00+00:00; Age hours: 94.00; Max age hours: 48.00
- **WARNING · photos**: The latest service check is too old to describe current status.

  Evidence: Event id: check-photos-0659; Observed at: 2026-10-18T11:00:00+00:00; Age hours: 13.00; Freshness limit seconds: 7200; Observed status: up
- **WARNING · photos**: Some job runs completed with a final failure during the reporting window.

  Evidence: Failed runs: 4; Completed runs: 55; Failure categories: {"dependency_unavailable": 4}
- **WARNING · photos**: Some expected monitoring slots have no known up/down observation.

  Evidence: Expected slots: 672; Known status slots: 647; Missing slots: 12; Unknown slots: 13; Monitoring coverage pct: 96.28
- **WARNING · photos**: Some pending job runs exceed the configured pending-age target.

  Evidence: Stale pending runs: 1; Oldest pending age hours: 20.00; Age target hours: 4.00; Job ids: ["job-photos-054"]
- **WARNING · photos**: The latest resource sample is too old for current resource alerts.

  Evidence: Event id: resource-photos-0660; Observed at: 2026-10-18T12:00:00+00:00; Age hours: 12.00; Freshness limit seconds: 7200
- **WARNING · photos**: No successful restore test is recorded; backup success alone does not prove recovery.

  Evidence: Recorded restore tests: 1; Max age days: 30.00
- **INFO · documents**: Recorded job attempts include retries; retries are separate from final failures.

  Evidence: Retries: 24; Completed runs: 55; Pending runs: 1; Final failed runs: 4
- **INFO · photos**: Recorded job attempts include retries; retries are separate from final failures.

  Evidence: Retries: 24; Completed runs: 55; Pending runs: 1; Final failed runs: 4

## compute

### Checks

| Measure | Result |
| --- | --- |
| Raw observations | 672 |
| Expected slots | 672 |
| Observed slots | 672 |
| Known status slots | 659 |
| Up slots | 659 |
| Down slots | 0 |
| Unknown slots | 13 |
| Missing slots | 0 |
| Sampled success pct | 100.00 |
| Monitoring coverage pct | 98.07 |
| Latest observed at | 2026-10-18T23:00:00+00:00 |
| Latest status | up |
| Latest latency ms | 79.46 |
| Latest age hours | 1.00 |
| Is fresh | Yes |
| Freshness limit seconds | 7200 |

### Resources

| Measure | Result |
| --- | --- |
| Latest observed at | 2026-10-18T23:00:00+00:00 |
| Latest age hours | 1.00 |
| Is fresh | Yes |
| Freshness limit seconds | 7200 |
| Measured fields | ["cpu_pct", "memory_pct", "disk_used_bytes", "disk_total_bytes", "disk_free_inodes_pct", "pool_health", "disk_health"] |
| Missing fields | [] |
| Cpu pct | 53.97 |
| Memory pct | 45.00 |
| Disk used bytes | 490000000000 |
| Disk total bytes | 1000000000000 |
| Disk used pct | 49.00 |
| Disk free inodes pct | 55.00 |
| Pool health | degraded |
| Disk health | passed |

### Backups

| Measure | Result |
| --- | --- |
| Max age hours | 48.00 |
| Latest attempt at | 2026-10-18T02:00:00+00:00 |
| Latest attempt outcome | success |
| Last success at | 2026-10-18T02:00:00+00:00 |
| Last success age hours | 22.00 |
| Last success checksum verified | Yes |
| Is overdue | No |
| Restore max age days | 30.00 |
| Latest restore at | 2026-09-09T00:00:00+00:00 |
| Latest restore outcome | passed |
| Last passed restore at | 2026-09-09T00:00:00+00:00 |
| Last passed restore age days | 40.00 |
| Restore is overdue | Yes |

### Jobs

| Measure | Result |
| --- | --- |
| Completed runs | 0 |
| Succeeded runs | 0 |
| Failed runs | 0 |
| Success pct | Unknown / not applicable |
| Running runs | 0 |
| Blocked runs | 0 |
| Retries | 0 |
| Completed run retries | 0 |
| Pending run retries | 0 |
| Failure categories | {} |
| Slowest completed job id | Unknown / not applicable |
| Slowest completed duration seconds | Unknown / not applicable |
| Oldest pending job id | Unknown / not applicable |
| Oldest pending age hours | Unknown / not applicable |
| Stale pending runs | 0 |
| Pending age target hours | 4.00 |


## documents

### Checks

| Measure | Result |
| --- | --- |
| Raw observations | 648 |
| Expected slots | 672 |
| Observed slots | 648 |
| Known status slots | 636 |
| Up slots | 627 |
| Down slots | 9 |
| Unknown slots | 12 |
| Missing slots | 24 |
| Sampled success pct | 98.58 |
| Monitoring coverage pct | 94.64 |
| Latest observed at | 2026-10-18T23:00:00+00:00 |
| Latest status | down |
| Latest latency ms | Unknown / not applicable |
| Latest age hours | 1.00 |
| Is fresh | Yes |
| Freshness limit seconds | 7200 |

### Resources

| Measure | Result |
| --- | --- |
| Latest observed at | 2026-10-18T23:00:00+00:00 |
| Latest age hours | 1.00 |
| Is fresh | Yes |
| Freshness limit seconds | 7200 |
| Measured fields | ["cpu_pct", "memory_pct", "disk_used_bytes", "disk_total_bytes", "disk_free_inodes_pct", "pool_health", "disk_health"] |
| Missing fields | [] |
| Cpu pct | 20.44 |
| Memory pct | 94.00 |
| Disk used bytes | 490000000000 |
| Disk total bytes | 1000000000000 |
| Disk used pct | 49.00 |
| Disk free inodes pct | 4.00 |
| Pool health | online |
| Disk health | passed |

### Backups

| Measure | Result |
| --- | --- |
| Max age hours | 48.00 |
| Latest attempt at | 2026-10-18T02:00:00+00:00 |
| Latest attempt outcome | failed |
| Last success at | 2026-10-17T02:00:00+00:00 |
| Last success age hours | 46.00 |
| Last success checksum verified | Yes |
| Is overdue | No |
| Restore max age days | 30.00 |
| Latest restore at | 2026-10-09T00:00:00+00:00 |
| Latest restore outcome | passed |
| Last passed restore at | 2026-10-09T00:00:00+00:00 |
| Last passed restore age days | 10.00 |
| Restore is overdue | No |

### Jobs

| Measure | Result |
| --- | --- |
| Completed runs | 55 |
| Succeeded runs | 51 |
| Failed runs | 4 |
| Success pct | 92.73 |
| Running runs | 0 |
| Blocked runs | 1 |
| Retries | 24 |
| Completed run retries | 24 |
| Pending run retries | 0 |
| Failure categories | {"dependency_unavailable": 4} |
| Slowest completed job id | job-documents-034 |
| Slowest completed duration seconds | 4740.00 |
| Oldest pending job id | job-documents-054 |
| Oldest pending age hours | 20.00 |
| Stale pending runs | 1 |
| Pending age target hours | 4.00 |


## photos

### Checks

| Measure | Result |
| --- | --- |
| Raw observations | 660 |
| Expected slots | 672 |
| Observed slots | 660 |
| Known status slots | 647 |
| Up slots | 647 |
| Down slots | 0 |
| Unknown slots | 13 |
| Missing slots | 12 |
| Sampled success pct | 100.00 |
| Monitoring coverage pct | 96.28 |
| Latest observed at | 2026-10-18T11:00:00+00:00 |
| Latest status | up |
| Latest latency ms | 82.89 |
| Latest age hours | 13.00 |
| Is fresh | No |
| Freshness limit seconds | 7200 |

### Resources

| Measure | Result |
| --- | --- |
| Latest observed at | 2026-10-18T12:00:00+00:00 |
| Latest age hours | 12.00 |
| Is fresh | No |
| Freshness limit seconds | 7200 |
| Measured fields | ["cpu_pct", "memory_pct", "disk_used_bytes", "disk_total_bytes", "disk_free_inodes_pct", "pool_health", "disk_health"] |
| Missing fields | [] |
| Cpu pct | 20.55 |
| Memory pct | 45.00 |
| Disk used bytes | 954098360655 |
| Disk total bytes | 1000000000000 |
| Disk used pct | 95.41 |
| Disk free inodes pct | 55.00 |
| Pool health | online |
| Disk health | passed |

### Backups

| Measure | Result |
| --- | --- |
| Max age hours | 48.00 |
| Latest attempt at | 2026-10-15T02:00:00+00:00 |
| Latest attempt outcome | success |
| Last success at | 2026-10-15T02:00:00+00:00 |
| Last success age hours | 94.00 |
| Last success checksum verified | Yes |
| Is overdue | Yes |
| Restore max age days | 30.00 |
| Latest restore at | 2026-10-17T00:00:00+00:00 |
| Latest restore outcome | failed |
| Last passed restore at | Unknown / not applicable |
| Last passed restore age days | Unknown / not applicable |
| Restore is overdue | Unknown / not applicable |

### Jobs

| Measure | Result |
| --- | --- |
| Completed runs | 55 |
| Succeeded runs | 51 |
| Failed runs | 4 |
| Success pct | 92.73 |
| Running runs | 1 |
| Blocked runs | 0 |
| Retries | 24 |
| Completed run retries | 24 |
| Pending run retries | 0 |
| Failure categories | {"dependency_unavailable": 4} |
| Slowest completed job id | job-photos-037 |
| Slowest completed duration seconds | 4800.00 |
| Oldest pending job id | job-photos-054 |
| Oldest pending age hours | 20.00 |
| Stale pending runs | 1 |
| Pending age target hours | 4.00 |

## Interpretation limits

- All input is synthetic; these findings do not describe an actual server.
- The reporting window is [window_start, as_of), in UTC; as_of is exclusive.
- Monitoring cadence slots start at window_start; a partial final slot is expected. Only the latest check per slot counts. Known coverage excludes missing and unknown slots. Sampled success uses only known up/down slots and is not continuous uptime.
- Freshness uses at most twice the configured check cadence for checks and resources. Latest observations use available history before as_of. Stale resource values remain visible as historical evidence and do not produce current threshold alerts.
- Resource warnings use demonstration thresholds: CPU, memory and disk used at 85%/95%; free inodes at 10%/5%. Single samples do not establish sustained load. No storage exhaustion forecast or cause is inferred.
- Backup and restore history may predate window_start. A successful or checksum verified backup does not prove a restore will succeed. Restore records do not identify which backup was tested; no latest-backup restore claim is made.
- Completed job runs count by finished_at within the window. Pending runs include carry-in runs and are observed at as_of. Retries are attempts minus one for those included runs, not individual retry events timed within the window. Pending age measures elapsed time since start, not time since last progress.
- Missing measurements and empty outcome denominators remain null; no observation is not evidence of health. Configured targets are demonstration assumptions.

## Provenance

Dataset SHA-256: `23f6b84366462fc39a859150127a397d874ce749ade44afca5e293d37db8d68c`.

Computed locally from supplied synthetic records. BigQuery and Gemini have not run.
