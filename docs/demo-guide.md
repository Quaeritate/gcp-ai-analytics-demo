# Run and present the demonstration

This demonstration answers one question: **What needs attention on a server, and
what evidence supports it?** It uses generic service aliases and deliberately
synthetic observations. It does not connect to infrastructure or use Google Cloud.

## Run locally

Use Python 3.12 or newer. From the repository root, create a virtual environment
and install the application with its development tools:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m gcp_ai_analytics demo-local --seed 42 --output artifacts/local/server-demo
```

On macOS or Linux, use `.venv/bin/python` in place of
`.\.venv\Scripts\python.exe`. Installation needs package access; the generated
demo itself runs offline and needs no credentials.

Open `artifacts/local/server-demo/report.html` in a browser. It is a standalone
file with no scripts, tracking, external fonts or other remote assets. Its
evidence controls work with JavaScript disabled. Use the browser's print dialog
for a printable view.

| Output | Purpose |
| --- | --- |
| `report.html` | Visual operations report with summary counts, priority observations, service comparison, resource readings, protection evidence and jobs. |
| `report.md` | Text report for review and documentation. |
| `report.json` | Calculated facts, evidence, limitations and input provenance. |
| `synthetic_server_data.json` | Reproducible input, including demonstration policies and observations. |

The generator uses a fixed UTC window ending at `2026-10-19T00:00:00Z`. The report
is a reproducible historical snapshot. Its “fresh” labels refer to the fixed
cutoff rather than today's date.

## A five-minute walkthrough

1. **Start with the scope and summary.** Point out the synthetic label and fixed
   cutoff. Critical and warning counts count findings, not distinct incidents.
   A single service can have multiple findings.
2. **Open the attention queue.** Inspect the storage-pool observation, document
   service check and free-inode observation. Expand their evidence to connect the
   summary to the measured field, observation time or configured target.
3. **Compare sampled success with coverage.** Missing and unknown slots are shown
   separately. A high sampled success percentage does not imply continuous
   uptime. The photo service's stale `up` result correctly leaves its current
   status unknown.
4. **Review resources and recovery.** Grey resource bars are historical. The
   backup and restore cards deliberately separate a recent successful backup
   from evidence that restoration was tested successfully and recently.
5. **Finish with unfinished work and provenance.** Show final failures, retries
   and pending jobs as different quantities. Open evidence and limitations, then
   use the dataset hash to connect the report to its precise input.

The default fixture contains these cases by design. They describe no real server
or application. The useful project feature is the chain from bounded input to
validated metrics to an inspectable finding.

## Re-analyze the same input

```powershell
.\.venv\Scripts\python.exe -m gcp_ai_analytics analyze-local --input artifacts/local/server-demo/synthetic_server_data.json --output artifacts/local/server-recheck
```

The imported-input workflow applies the same schema and calculations. Outputs
from the same validated input are deterministic. Existing identical files can be
reused; a differing existing file causes the command to stop. Choose a new output
directory to compare a different seed or scenario.

```powershell
.\.venv\Scripts\python.exe -m gcp_ai_analytics demo-local --seed 7 --output artifacts/local/server-seed-7
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Offline tests cover validation, metric boundaries, reproducibility, missing-data
semantics and presentation escaping. Passing these tests does not prove live
server collection, BigQuery execution or Gemini output quality.

## Explain the Google Cloud extension

The [architecture](architecture.md) shows separate local and cloud paths. The
BigQuery module prepares five normalized JSONL tables and fixed parameterized
queries. Its executed results must be compared with the local reference metrics.
The Gemini module prepares a bounded evidence bundle and validates structured
triage against known evidence and reviewed runbook checks. The HTML report itself
does not contain model-generated explanations.

Preparing inputs is different from executing cloud work. Before any billable
execution, the owner must review the exact resources, request limits, current
cost estimate and cleanup plan. Follow [cloud setup](cloud-setup.md), and cite
only observed evidence from [verification](verification.md) when presenting what
has been tested.

These preparation commands remain local. `synthetic-demo-project` is an example
identifier used to inspect a plan, not a provisioned Google Cloud project:

```powershell
.\.venv\Scripts\python.exe -m gcp_ai_analytics plan-cloud --input artifacts/local/server-demo/synthetic_server_data.json --project synthetic-demo-project --output artifacts/local/cloud-plan
.\.venv\Scripts\python.exe -m gcp_ai_analytics triage --input artifacts/local/server-demo/synthetic_server_data.json --project synthetic-demo-project --output artifacts/local/triage-preview
.\.venv\Scripts\python.exe -m gcp_ai_analytics evaluate-ai --output artifacts/local/ai-evaluation
```

The preview prepares a request; it is not a Gemini response. Offline evaluation
checks local validation behavior; it is not evidence of a model's measured
quality. The optional execution commands use an explicit `--execute` gate.
In the combined `cloud-demo` workflow, a BigQuery parity failure stops the flow
before model inference. No live execution command is needed for this walkthrough.
