# Server insight roadmap

The project starts with one question: **What needs attention, and what evidence supports it?**
This catalog covers 38 useful questions for a personal server and the applications it hosts.
It describes product scope, not an assessment of any live system.

**Implemented** means a deterministic calculation exists for the synthetic contract.
**Partial** means only the stated subset exists. **Planned** means the source contract,
collector, and analysis still need implementation and verification.

## Protect data and identify work needing attention

| ID | Question | Coverage today | Evidence needed next |
| --- | --- | --- | --- |
| S01 | What needs attention now? | Partial: severity-ranked rule findings and evidence | Persistence, acknowledgement, dependencies |
| S02 | Are intended hosts and guests running? | Planned | Expected state, boot identity, timestamped guest state |
| S03 | Can each service be used? | Partial: sampled up/down/unknown outcomes and success rate | Qualified functional checks |
| S04 | Where has monitoring gone silent? | Implemented: coverage slots and last-observation freshness | Separate source and collector clocks |
| S05 | How recent is a successful backup? | Implemented: last success, deadline, latest failed attempt | Actual backup receipts |
| S06 | What data is outside the backups? | Planned | Workload-to-backup coverage and exclusions |
| S07 | Could the workload be restored? | Partial: independent restore-test age and outcome | Tested generation, components and recovery duration |
| S08 | Would backups survive loss of this machine? | Planned | Verified independent-copy and failure-domain inventory |
| S09 | Which filesystem could run out of capacity? | Partial: latest byte usage and free inodes | Per-volume mapping, reserve policies and history |
| S10 | Is the storage pool degraded? | Partial: latest pool-health summary | Device states, error deltas, scrub evidence |
| S11 | Are disks showing warning signs? | Partial: latest disk-health summary | Protocol-specific SMART/NVMe fields and history |
| S12 | Which scheduled jobs are failing or unfinished? | Partial: outcomes, retries and old pending work | Expected schedule and missed-run detection |
| S13 | Is document processing waiting for review or broken? | Partial: generic blocked/running job states | Qualified document-processing metadata adapter |
| S14 | Is photo processing growing or stuck? | Planned | Version-qualified queue snapshots and pause state |
| S15 | Did a maintenance change leave something degraded? | Planned | Change windows and before/after functional checks |

## Diagnose bottlenecks and recurring failures

| ID | Question | Coverage today | Evidence needed next |
| --- | --- | --- | --- |
| S16 | Is a slowdown related to CPU, memory or storage? | Partial: fresh CPU and memory pressure thresholds | Concurrent pressure, I/O latency and user symptoms |
| S17 | Which workload consumes capacity? | Planned | Comparable per-workload time series without double counting |
| S18 | Is there room for another app? | Planned | Peak headroom, reservations and workload envelope |
| S19 | When might storage need attention? | Planned | Sufficient comparable history and forecast uncertainty |
| S20 | What category of data is growing? | Planned | Storage category accounting, snapshots and shared layers |
| S21 | Does maintenance compete with normal use? | Planned | Actual job intervals and simultaneous performance samples |
| S22 | Which failures recur or recover? | Partial: final failures and extra attempts are separate | Incident episodes and confirming recovery observations |
| S23 | Are services repeatedly restarting? | Planned | Restart/OOM events qualified by boot/container identity |
| S24 | Are queues draining fast enough? | Planned | Arrival/completion events and oldest waiting timestamps |
| S25 | Is temperature limiting work? | Planned | Qualified sensors, thresholds and throttle evidence |
| S26 | Which failures share a dependency? | Planned | Explicit topology and aligned failure intervals |
| S27 | What changed since yesterday or last week? | Planned | Comparable windows and coverage denominators |
| S28 | Are alerts useful and delivered? | Planned | Durable incident history, acknowledgements and delivery tests |

## Resilience, access and power

| ID | Question | Coverage today | Evidence needed next |
| --- | --- | --- | --- |
| S29 | Are certificates near expiry? | Planned | Served certificate checks plus separate renewal receipts |
| S30 | Is access failing at DNS, routing, TLS or the app? | Planned | Layered checks from qualified vantage points |
| S31 | Have access or exposure controls drifted? | Planned | Reviewed baseline and minimal metadata export |
| S32 | Which software needs lifecycle review? | Planned | Timestamped versions and current official lifecycle evidence |
| S33 | Can recovery controls be reached during an outage? | Planned | Independent scenario-specific access tests |
| S34 | Is UPS reserve adequate? | Planned | Supported UPS observations and measured shutdown duration |
| S35 | Does shutdown protection cover all dependencies? | Planned | Load topology and an explicitly authorized recovery test |
| S36 | How much energy does the server use? | Planned | Timestamped measured watts with coverage accounting |
| S37 | Can clocks support reliable correlations? | Planned | Synchronization state and offset uncertainty |
| S38 | What is still unknown? | Partial: missing/stale metrics and explicit limitations | Full expected-asset/source coverage matrix |

## Interpretation rules

Missing evidence is unknown. A sampled success rate is not continuous uptime.
A recent backup is not proof of restoration, and checksum verification does not
prove independent protection. A passing disk summary does not predict future
failure. Pending age measures time since start, not time since last progress.
Correlation across observations does not establish a root cause.

Start a private integration with a small, explicitly agreed metadata export.
Qualify the source semantics and collection side effects before connecting it.
The public project uses synthetic aliases only and contains no live collector,
notification sender, remediation endpoint or private infrastructure inventory.
