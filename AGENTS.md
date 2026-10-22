# Repository working instructions

## Ownership and publication

- The project owner and submitter is Matej Bicej (GitHub: Quaeritate).
- All commits made for this project must use author and committer name `Matej Bicej`
  and email `149827303+Quaeritate@users.noreply.github.com`.
- Verify `git var GIT_AUTHOR_IDENT` and `git var GIT_COMMITTER_IDENT` before committing.
- Do not add AI-agent attribution or AI co-author trailers to commits or documentation.
- Before publishing, verify the authenticated GitHub account is Quaeritate and inspect
  the outgoing files for secrets and private configuration. Do not rewrite existing
  history or alter global Git identity without a specific request.

## Scope and evidence

- Analyze the handoff and explain design choices before implementation.
- Work in small, independently verifiable stages. See `docs/stage-0-plan.md`.
- The owner accepted server-focused **Server & App Operations Insights** as the
  project direction. Keep public documentation focused on that scope.
- Use synthetic data only. Keep credentials, billing identifiers, and private
  configuration out of source control.
- Public examples, fixtures and demonstrations remain synthetic. A future private
  metadata integration needs a bounded agreed export before real data is read or
  collected; any cloud use still needs the approval below. The current analytics
  scope does not authorize live collectors, remediation, or access/auth changes.
- Keep server source review distinct from runtime proof. Do not execute historical
  infrastructure scripts or assume a status command is free of state changes.
- Before any billable cloud operation, show the concrete resource/request plan,
  usage limits, estimated cost basis, and obtain the owner's approval.
- Use Application Default Credentials; never create service-account key files.
- Use the Google Gen AI SDK through Vertex AI. Recheck current official SDK,
  model lifecycle, and location documentation before real inference.
- Do not allow model-generated SQL or commands to execute.
- Separate offline tests from explicit cloud integration tests. Never claim a cloud
  operation, model evaluation, cost, or cleanup succeeded without observed evidence.
- Treat business impact as a demonstration hypothesis until measured.
