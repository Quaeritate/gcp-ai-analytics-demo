# Optional Google Cloud setup

The repository works locally without a Google Cloud account. The cloud adapters
are implemented and tested offline; actual API execution remains unverified.
Review the [cost and resource plan](security-and-costs.md) before a live run.

## Dedicated project and credentials

1. Create a dedicated project and link an approved billing account. Keep its
   identifier and billing details in local configuration, not public examples.
2. Enable only `bigquery.googleapis.com` and `aiplatform.googleapis.com`.
3. Install the official [Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/install-sdk).
4. Configure user [Application Default Credentials](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment)
   with `gcloud auth application-default login`. A normal CLI login alone is not ADC.
5. Set the ADC quota project to the dedicated project. Never create or download
   a service-account key file.
6. Grant the runtime identity only the roles needed: BigQuery Job User for
   jobs, dataset creation permission for initial provisioning and scoped data
   access, plus Vertex AI User for inference. An administrator can provision
   the labeled dataset first and then scope table access to it. API enablement,
   billing linkage and IAM administration are setup privileges, not ongoing
   runtime requirements. Verify the final permission set in the selected project.

This release uses BigQuery `US` and Gemini `gemini-3.5-flash-lite` at `global`.
The current Google Gen AI SDK names the Cloud backend `enterprise=True`; it uses
the same Cloud AI endpoint family associated with Vertex AI. The client explicitly
resolves ADC and passes credentials, preventing ambient API keys from choosing
a different authentication mode.

The model and location were checked against the
[official model documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash-lite)
on October 22, 2026. Recheck support before inference. The configuration omits a
custom temperature, requests minimal thinking, bounds output to 1,024 tokens,
and disables automatic retries, continuation and function calling.

`.env.example` documents reference values only; the CLI does not read `.env`.
Project, dataset and BigQuery location are explicit command arguments. Usage
limits are enforced in code and are not mutable through environment variables.

## Prepare, review, then execute

First generate the [local demo](demo-guide.md) and inspect a plan:

```powershell
.\.venv\Scripts\python.exe -m gcp_ai_analytics plan-cloud --input examples/synthetic/synthetic_server_data.json --project YOUR_PROJECT_ID --output artifacts/local/cloud-plan
```

`YOUR_PROJECT_ID` must be replaced with a valid project ID. This command is local;
it does not create resources or resolve credentials. Review the manifest, target
tables, SQL hashes, limits and [cost assumptions](security-and-costs.md).

After the exact project and bounded operations have been approved:

```powershell
.\.venv\Scripts\python.exe -m gcp_ai_analytics cloud-demo --input examples/synthetic/synthetic_server_data.json --project YOUR_PROJECT_ID --output artifacts/local/cloud-run-01 --execute
```

This creates/verifies the dedicated labeled dataset, creates five tables with
seven-day expiry, loads the validated synthetic records, dry-runs and runs six
queries, compares the results with Python and then attempts one Gemini request.
The model receives a bounded selection of returned SQL aggregates. Any parity
failure prevents inference. The HTML report remains a labeled local reference;
`verified-cloud-report.json` and `cloud-verification.json` record the distinct
cloud evidence and provenance. `triage.json` and `triage.md` retain the model result.

Separate commands are available: `run-bigquery` for warehouse verification,
`triage` for one model request, and `evaluate-ai` for the 24-case model evaluation.
Each needs `--execute` for real calls. `triage` and `evaluate-ai` prepare/validate
locally without that flag. The evaluation is a separate workload requiring its
own cost approval; passing a flag does not create spending authorization.

Live commands require a **new** output directory beneath ignored `artifacts/local/`.
Cloud job IDs and response metadata stay there. Evaluation saves each completed
case before the next request. Inspect ambiguous jobs before retrying; neither
success nor timeout permits automatic resubmission. See [BigQuery recovery](bigquery.md).

## Evidence required after a real run

Record actual load counts, job outcomes, processed/billed bytes, SQL parity,
model version, settings, token use, failures and human-reviewed output quality.
Publish only sanitized excerpts. Query configuration is not proof of a bill,
and table expiry is not proof of cleanup. Follow the dedicated-resource cleanup
procedure in [security and costs](security-and-costs.md).
