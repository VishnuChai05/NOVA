# oh so u AI Content Engine - Delivery Plan

Date: 2026-03-27
Source docs: `ohsou_PRD.docx`, `ohsou_TRD.docx`

## 1) Delivery Goals

Build an internal AI Content Engine that:
- Aggregates Reddit + Quora + blog data
- Extracts actionable female pain points for the oh so u audience
- Generates high-quality outputs (blog, reel script, product idea)
- Enforces quality, safety, compliance, and auditability on every release
- Supports role-based workflows (Writer, Reviewer, Admin) with accountability

## 2) Product Scope (v1)

In scope (from PRD/TRD):
- Blog counter (WordPress REST API)
- Reddit + Quora scraping (config-driven)
- AI insight extraction and content generation
- Internal dashboard for review and export
- Status workflow: draft / approved / rejected / needs_edit
- Security basics: env secrets, no PII retention, 30-day data retention

Out of scope (v1):
- Auto-publishing to blog/social channels
- Public access
- Advanced analytics and ROI attribution

## 3) Architecture and Tech Decisions

Backend:
- Python 3.11 + FastAPI
- SQLModel or SQLAlchemy + Alembic
- PostgreSQL (prod), SQLite (dev)
- APScheduler or Celery beat for scheduled scraping jobs

Frontend:
- React 18 + Vite + TailwindCSS
- Zustand for predictable state (scrape queue, selected topics, output lifecycle)

AI:
- Primary generation model: follow TRD baseline (`claude-sonnet-4-20250514`)
- Quality evaluator model: strongest available model in your stack for review scoring and regression checks
- Model gateway abstraction so model can be switched with config without code rewrite

Observability:
- Structured logs (JSON)
- Correlation IDs across scrape -> classify -> generate -> review
- Metrics: latency, token use, error rate, approval rate, content edit distance

## 4) Model Quality Strategy (Best-Model-First)

Use a two-stage model pipeline:
1. Generate stage
- Produce initial output from selected prompt template and source insight.

2. Evaluate and improve stage
- Run a quality evaluator prompt that scores:
  - Brand voice match (warm, body-positive, Indian-context)
  - Accuracy and relevance to source insight
  - SEO and structure completeness (for blog)
  - Safety/compliance checks (no competitor mentions, no harmful claims)
- If score < threshold, auto-revise once; otherwise send to human review.

Release policy:
- Every model or prompt change must pass benchmark suite before deployment.
- No unbenchmarked prompt/model change goes live.

## 5) Role-Based Operating Model

Roles and responsibilities:
- Product Manager:
  - Owns roadmap, acceptance criteria, and release gates
- Engineering Lead:
  - Owns architecture, reliability, and migration safety
- ML/Prompt Engineer:
  - Owns prompt templates, evaluation rubric, benchmark set
- QA Lead:
  - Owns automated and manual test quality gates
- Content Lead (Writer/Reviewer):
  - Owns brand voice acceptance and editorial scoring
- Security/Compliance Reviewer:
  - Owns PII controls, retention, secrets management, legal-safe scraping behavior
- Data/Analytics Owner:
  - Owns KPI tracking and post-release quality trends

Approval matrix:
- Functional release: Engineering + QA
- Prompt/model release: ML/Prompt + Content + QA
- Policy/security release: Security/Compliance + Engineering

## 6) End-to-End Build Plan (8 Weeks)

Week 1-2: Foundation + Module 1 (Blog Counter)
- Initialize backend/frontend repos and CI/CD
- Implement `/api/blog-count` with caching and category mapping
- Create baseline dashboard home widgets
- Add first test suite (unit + API contract)

Week 2-3: Module 2 (Scraper Engine)
- Implement Reddit scraper via PRAW with throttling
- Implement Quora source via Apify adapter (preferred for stability)
- Add config-driven queries and limits (`config.yaml`)
- Store normalized data in `scraped_posts`
- Add retries/backoff, dedupe, and URL uniqueness constraints

Week 3-4: Module 3 (Insight + Generation)
- Implement insight extraction endpoint and persistence
- Implement generation endpoint `/api/generate`
- Add output table and status lifecycle
- Add prompt template versioning

Week 4-5: Module 4 (Dashboard UX)
- Build pages: Summary, Scraped Topics, Generator, Content Library, Settings
- Add filtering, preview, status transitions, export to text/markdown
- Add role-aware UI controls (hide admin actions by role)

Week 5-6: Quality and Safety Hardening
- Add evaluator model and score thresholds
- Add moderation and policy checks pre-approval
- Add regression harness for prompt/model changes
- Implement 30-day retention cleanup job

Week 6-7: Full Testing + Audits
- Execute comprehensive test matrix (see section 7)
- Security, privacy, and compliance audits
- Reliability drills (rate limit, provider outage, retry behavior)

Week 8: UAT + Launch
- Multi-role UAT sign-off
- Release checklist completion
- Hypercare monitoring for 2 weeks

## 7) Testing Strategy (Full Range)

Test pyramid:
- Unit tests (fast):
  - Scraper parsers, category mapping, prompt builders, score calculators
- Integration tests:
  - DB writes/reads, external API wrappers (mocked and sandbox)
- Contract tests:
  - API schema validation for `/api/blog-count`, `/api/generate`, listing endpoints
- End-to-end tests:
  - Run engine -> inspect topics -> generate -> approve -> export
- UI tests:
  - Critical flows in Playwright (desktop + mobile viewport)
- Performance tests:
  - Batch generation throughput, P95 latency, queue behavior under load
- Chaos tests:
  - 429 handling, timeout behavior, partial upstream outage
- Security tests:
  - SAST, dependency scanning, secret scanning, authz checks
- Data/privacy tests:
  - Username stripping, retention deletion, no secret leakage in logs
- Prompt/model regression tests:
  - Golden dataset scored against fixed rubric
  - Track quality deltas and reject regressions

Minimum quality gate before merge:
- Unit/integration pass
- No critical/high vulnerabilities
- API contracts unchanged or versioned
- Prompt/model benchmark >= baseline

Minimum quality gate before release:
- E2E pass on staging
- Security audit pass
- Editorial quality pass (sampled outputs)
- Rollback plan verified

## 8) Audit Framework (Multiple Audits)

Audit 1: Product requirement audit
- Trace each PRD requirement to endpoint, UI, and tests

Audit 2: Technical design audit
- Validate TRD architecture, schema, and operational constraints

Audit 3: Security audit
- Secrets, auth controls, PII scrubbing, dependency risk

Audit 4: Compliance/data audit
- TOS compliance, retention policy enforcement, source attribution handling

Audit 5: Content quality audit
- Brand voice, readability, cultural context, harmful-content checks

Audit 6: Reliability audit
- Retries, rate-limit handling, queue durability, observability quality

Cadence:
- Lightweight audit every sprint
- Full cross-functional audit at pre-launch and quarterly

## 9) Release Governance and Change Control

Every change must include:
- Requirement link (PRD/TRD ID)
- Test evidence (automated + manual where applicable)
- Risk classification (low/medium/high)
- Rollback steps
- Monitoring impact notes

Prompt/model change policy:
- Version prompts in repo
- Keep benchmark dataset fixed for comparability
- Store before/after scorecards
- Require two-role sign-off (ML/Prompt + Content)

## 10) KPI Dashboard (Post-Launch)

Track weekly:
- Topics scraped, dedupe rate, source freshness
- Generation success rate and failure reason distribution
- Content approval rate by type
- Median edits required before approval
- Time-to-approved-content
- Safety/policy violation rate
- Cost per approved output (tokens + infra)

## 11) Immediate Next Actions

1. Convert this plan into backlog epics and user stories with acceptance criteria.
2. Build benchmark dataset (100-200 representative topics) for regression scoring.
3. Implement model gateway + prompt versioning first to avoid rework.
4. Stand up CI quality gates from day one (tests + security + benchmark checks).
5. Run a pilot with Content + Product for 1 week before full launch.
