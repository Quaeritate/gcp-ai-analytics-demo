# Presenting the project

## A 45-second explanation

I built a server operations analytics prototype to answer what needs attention
and what evidence supports it. It separates service availability from monitoring
coverage, backup freshness from restoration evidence, and retries from final job
failures. Python validates and analyzes a reproducible synthetic dataset and
produces a standalone dashboard. I also implemented six parameterized BigQuery
analyses and a Gemini triage adapter with structured output, evidence references
and bounded requests. An independent Python calculation checks SQL results before
the combined path sends aggregates to Gemini. A real cloud test loaded the
synthetic fixture and matched all 189 metrics. Two model responses were rejected;
clarifying response-status semantics produced a schema/reference-valid response.
I retained the failures and a remaining uncertainty-label limitation. The project
has 132 offline tests; broader model evaluation and private server integration
remain future work.

## Evidence-supported résumé wording today

**Server & App Operations Insights — Python, BigQuery, Gemini/Vertex AI:** Built
and tested a reproducible server-operations analytics prototype; verified six
live BigQuery SQL analyses against 189 independent Python metrics, integrated
structured Gemini triage with evidence-reference validation, and covered metric
semantics and cloud failure paths with 132 offline tests.

Use the [verification record](verification.md) and [cloud test](cloud-smoke-test.md)
to explain the actual scope. Do not claim production deployment, real-server
impact, corpus-wide model accuracy or finalized billing from this smoke test.

## Design trade-offs to explain

- Local calculations make the demo useful without cloud access and provide an
  independent warehouse reference, at the cost of maintaining two implementations.
- Fixed SQL and a small reviewed runbook constrain the demonstration's scope.
  They keep the boundary inspectable and prevent model-generated execution.
- A static report is portable and inexpensive. It is a snapshot, so it cannot
  replace a continuously updated monitoring service.
- Synthetic data makes the project reproducible and publishable. Private server
  integration still requires source qualification and measured operational value.
