# oh so u AI Content Engine

Monorepo implementation of the PRD/TRD for an internal content intelligence platform.

## Structure

- `backend/`: FastAPI service for blog counting, scraping, AI generation, and output workflow.
- `frontend/`: React dashboard for internal content operations.
- `infra/`: Local infra and deployment notes.
- `.github/workflows/`: CI quality gates.

Scraper credential setup guide:
- `SCRAPER_SETUP.md`

## Quickstart

### Backend

1. Create and activate a Python environment.
2. Install dependencies:
   - `pip install -e backend[dev]`
3. Run API:
   - `uvicorn app.main:app --reload --app-dir backend`

### Frontend

1. `cd frontend`
2. `npm install`
3. `npm run dev`

## Primary API Endpoints

- `GET /api/health`
- `GET /api/blog-count`
- `GET /api/scraped-posts`
- `POST /api/scrape/run`
- `GET /api/scrape/runs`
- `POST /api/generate`
- `GET /api/outputs`
- `PATCH /api/outputs/{output_id}/status`

## Quality Gates

- Backend tests: `pytest backend/tests`
- Frontend tests: `npm run test`
- Linting and CI in `.github/workflows/ci.yml`
