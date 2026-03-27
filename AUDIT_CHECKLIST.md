# Audit Checklist (Multi-Role)

## Product Audit (PM)

- All PRD requirements mapped to implementation
- Out-of-scope items not accidentally shipped
- Success metrics instrumentation present

## Technical Audit (Engineering)

- TRD architecture reflected in code
- Schema and endpoint contracts documented
- Error handling and retries implemented

## QA Audit (QA Lead)

- Unit/integration/E2E coverage present
- Negative test cases for API errors included
- Regression tests for key flows included

## Security and Compliance Audit (Security)

- Env secrets only on backend
- Data retention policy active (30 days)
- No PII persistence from scraped sources
- Scraping behavior aligned to source terms

## Editorial Audit (Content Reviewer)

- Body-positive, warm tone
- Indian context relevance
- No competitor mentions
- Output quality scoring and correction loop active

## Reliability Audit (SRE/Engineering)

- Queue and retry behavior tested
- Health endpoint and basic telemetry available
- Incident rollback procedure documented
