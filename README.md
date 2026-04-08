# NOVA — Content Intelligence Platform

Internal content intelligence engine built for [ohsou.com](https://ohsou.com) — a women's innerwear and wellness brand in India.

NOVA scrapes community discussions (Reddit, Quora, forums, blogs), classifies them by product category, and generates SEO-optimized content, ad scripts, and product range strategies using LLM providers (Groq, Anthropic) or template fallbacks.

## Why This Exists

Women's product brands in India struggle to find authentic, community-driven insights at scale. NOVA automates the pipeline from **raw discussion → classified topic → generated content → editorial review**.

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Alembic, PRAW, Apify, httpx
- **Frontend:** React 18, Vite, React Router, Axios
- **CI:** GitHub Actions (lint + test + build)

## Deployment Status

NOVA is now deployed in production with this architecture:

- **Frontend:** Firebase Hosting
- **Backend API:** GCP-hosted backend service
- **Worker Queue/Redis:** Upstash Redis

The repository also includes alternative deployment paths (VPS Docker Compose and Railway), but the active production stack is Firebase + GCP + Upstash.

Use these docs based on your target platform:

- [DEPLOYMENT.md](DEPLOYMENT.md) for VPS + Docker Compose
- [RAILWAY.md](RAILWAY.md) for Railway setup
- [OPERATIONS.md](OPERATIONS.md) for production operations and troubleshooting

## Project Structure

```
backend/
  app/
    api/routes/     # FastAPI endpoint handlers
    core/           # Settings, security middleware
    db/             # SQLAlchemy session and base
    models/         # ORM models (ScrapedPost, GeneratedOutput, etc.)
    schemas/        # Pydantic request/response schemas
    services/       # Business logic (scraper, engine, generator)
  tests/            # pytest suite
frontend/
  src/
    components/     # Sidebar, ErrorBoundary
    pages/          # SummaryPage, TopicsPage, LibraryPage, etc.
    lib/            # API client, useApi hook
```

## Quickstart

### Backend

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e backend[dev]
# Copy .env.example to .env and fill in API keys
uvicorn app.main:app --reload --app-dir backend
```

### Background Worker (RQ)

Run Redis and the scrape worker for asynchronous scrape jobs:

```bash
docker run --name nova-redis -p 6379:6379 -d redis:7-alpine
cd backend
python -m app.workers.rq_worker
```

Worker reads REDIS_URL, SCRAPE_JOB_QUEUE_NAME, and SCRAPE_JOB_TIMEOUT_SECONDS from environment.
Scrape orchestration also supports SCRAPE_PARALLEL_MAX_WORKERS, SCRAPE_REDDIT_TIMEOUT_SECONDS,
SCRAPE_QUORA_TIMEOUT_SECONDS, SCRAPE_FORUM_TIMEOUT_SECONDS, and SCRAPE_BLOG_TIMEOUT_SECONDS.
Phase 3 relevance and classification controls: SCRAPE_RELEVANCE_MIN_SCORE and
SCRAPE_TOPIC_CLASSIFIER_PROVIDER (template, groq, anthropic).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Deploy (Easy VPS Path)

NOVA includes a Docker Compose production path for a single VPS.

### Included deployment files

- `docker-compose.yml`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `.env.production.example`
- `DEPLOYMENT.md`

### Quick deploy

```bash
cp .env.production.example .env.production
# edit .env.production with real keys and domain
docker compose --env-file .env.production up -d --build
```

Then open your server domain (or server IP) and verify API health at `/api/health`.

### One-command deploy/update helpers

```bash
chmod +x scripts/deploy.sh scripts/update.sh

# first-time deploy
./scripts/deploy.sh .env.production

# later updates
./scripts/update.sh .env.production
```

For full VPS setup and HTTPS notes, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Deploy (Railway Path)

Railway is also a good fit if you want managed infrastructure without running your own VPS.

Recommended Railway layout:

- Backend service from `backend/Dockerfile`
- Frontend as a Railway Static Site or separate frontend service
- Railway Postgres for production data

Important:

- Set `DATABASE_URL` from Railway Postgres for the backend service.
- Set `VITE_API_URL` in the frontend build to your backend service URL.
- The backend container now listens on Railway's `$PORT` automatically.

See [RAILWAY.md](RAILWAY.md) for the step-by-step setup.

## API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | No | Health check |
| GET | `/api/blog-count` | No | Blog category counts |
| POST | `/api/scrape/run` | Yes | Trigger scraper |
| GET | `/api/scraped-posts` | Yes | List scraped topics |
| POST | `/api/generate` | Yes | Generate content from a topic |
| GET | `/api/outputs` | Yes | List generated content |
| POST | `/api/engine/blog-maker` | Yes | LLM blog blueprint |
| POST | `/api/engine/script-generator` | Yes | LLM ad script pack |
| POST | `/api/engine/product-range` | Yes | LLM product strategy |

Auth = `X-API-Key` header matching `OPERATIONAL_API_KEY` env var.

## Testing

```bash
# Backend
pytest backend/tests -v

# Frontend
cd frontend && npm test
```


Schema migrations are now available through Alembic in `backend/alembic`. The app still
uses `init_db()` for local startup compatibility, but migrations are the preferred path for
production schema changes.

The local launcher runs `alembic upgrade head` automatically before starting the backend.

## Operations

See [OPERATIONS.md](OPERATIONS.md) for log locations, debugging, and data management.
