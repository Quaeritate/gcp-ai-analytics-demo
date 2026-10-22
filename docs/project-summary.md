# Presenting the project

## A 45-second explanation

I built a server operations analytics prototype to answer what needs attention
and what evidence supports it. It separates service availability from monitoring
coverage, backup freshness from restoration evidence, and retries from final job
failures. Python validates and analyzes a reproducible synthetic dataset and
produces a standalone dashboard. I also implemented six parameterized BigQuery
analyses and a Gemini triage adapter with structured output, evidence references
and bounded requests. An independent Python calculation checks SQL results before
the combined path sends aggregates to Gemini. The local workflow and cloud failure
paths are tested offline; live cloud execution and model-quality evaluation are
the next verification milestone.

## Evidence-supported résumé wording today

**Server & App Operations Insights — Python, BigQuery, Gemini/Vertex AI:** Built
and tested a reproducible server-operations analytics demo with a standalone
dashboard, six BigQuery SQL analyses, and structured Gemini adapters; validated
metric semantics and cloud failure paths with 129 offline tests.

Do not describe the BigQuery loads, actual Gemini inference, measured model
accuracy or verified cleanup as complete until the [verification record](verification.md)
contains observed cloud evidence. After that milestone, update the wording around
the actual results and retain material limitations.

## Design trade-offs to explain

- Local calculations make the demo useful without cloud access and provide an
  independent warehouse reference, at the cost of maintaining two implementations.
- Fixed SQL and a small reviewed runbook constrain the demonstration's scope.
  They keep the boundary inspectable and prevent model-generated execution.
- A static report is portable and inexpensive. It is a snapshot, so it cannot
  replace a continuously updated monitoring service.
- Synthetic data makes the project reproducible and publishable. Private server
  integration still requires source qualification and measured operational value.
