# Quality Gates

## Merge Gate

- Backend unit/integration tests pass
- Frontend test and build pass
- API contract changes reviewed
- Security scan clean of critical/high vulnerabilities
- Prompt/model benchmark run for any generation change

## Release Gate

- Staging E2E flow pass: scrape -> generate -> review -> export
- Editorial quality sample pass (at least 20 samples)
- Privacy checks pass (no usernames retained, no secret leakage)
- Rate-limit behavior pass (Reddit/Claude backoff)
- Rollback playbook verified

## Benchmark Policy

- Keep a fixed golden dataset for regression scoring
- Block release if quality score drops below baseline
- Store per-release scorecard for traceability
