# Operations Guide

## Production Topology

- Frontend is served from Firebase Hosting.
- Backend API runs on GCP.
- Background scrape jobs use Upstash Redis for the queue backend.

## Log Files

| File | Contains | Size Limit |
|---|---|---|
| `backend/.logs/backend.log` | All backend events | 10 MB (5 rotated) |
| `backend/.logs/backend_errors.log` | Errors only | 5 MB (3 rotated) |
| `backend/.logs/scraper.log` | Scraper-specific events | 10 MB (5 rotated) |

All logs auto-rotate when they hit their size limit.

## Starting Services

```powershell
# Automated
.\start-nova.ps1

# Manual
# Terminal 1:
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2:
cd frontend
npm run dev
```

## Viewing Logs

```powershell
# Last 50 lines of main log
Get-Content backend\.logs\backend.log -Tail 50

# Watch scraper log in real-time
Get-Content backend\.logs\scraper.log -Wait -Tail 20

# Check recent errors
Get-Content backend\.logs\backend_errors.log -Tail 30
```

## Debugging Scraper Issues

1. Check `backend/.logs/scraper.log` for fetch results per source
2. Verify API keys are set: `APIFY_API_TOKEN`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`
3. Check `config.yaml` for correct subreddits and queries
4. If all sources fail, the scraper falls back to seed data (when `ALLOW_FALLBACK_SEED_DATA=true`)

## Data Management

- Scrape runs are logged in `scrape_runs` table with source stats and failure details
- Posts older than 30 days can be purged via `compliance.purge_old_scraped_data()`
- The SQLite database is at `backend/ohsou.db`
