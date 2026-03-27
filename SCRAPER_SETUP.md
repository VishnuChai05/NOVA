# Reddit and Quora Scraper Setup

This guide sets up real scraping for the oh so u content engine.

## 1) Reddit API Setup (PRAW)

1. Sign in to Reddit with a service account.
2. Open Reddit developer registration:
   - `https://developers.reddit.com/app-registration`
   - If needed, old path still works in some regions: `https://www.reddit.com/prefs/apps`
3. Create app:
   - App type: `script` (or personal-use/script equivalent in the new UI)
   - Name: `ohsou-content-engine`
   - Redirect URI: `http://localhost:8080`
4. Copy credentials:
   - `client id` (often shown as app ID)
   - `client secret`
5. Add to `.env`:
   - `REDDIT_CLIENT_ID=...`
   - `REDDIT_CLIENT_SECRET=...`
   - `REDDIT_USER_AGENT=ohsou-content-engine/1.0`

Notes:
- The redirect URI is required by the app form, but this scraper flow does not use OAuth browser redirects.
- If the new portal asks for extra fields, keep the app internal and do not enable scopes you do not need.

## 2) Quora Setup (Apify Primary)

1. Create Apify account and API token.
2. Add token to `.env`:
   - `APIFY_API_TOKEN=...`
3. Keep actor ID default or override:
   - `APIFY_ACTOR_ID=apify/google-search-scraper`

Note: The backend searches Quora results via actor query pattern `site:quora.com <topic>`.

## 3) Fallback Behavior

If Apify token is not provided or fails, backend automatically uses Quora web search fallback.
If all sources fail and `ALLOW_FALLBACK_SEED_DATA=true`, seed posts are inserted for local testing.

## 4) Hardening Controls

Set in `.env`:
- `SCRAPER_RETRY_ATTEMPTS=3`
- `SCRAPER_BACKOFF_BASE_SECONDS=1.0`
- `REDDIT_QUERY_DELAY_SECONDS=0.35`

## 5) Run and Verify

From repo root:

```powershell
& "c:/college materials/NOVA/.venv/Scripts/python.exe" -m uvicorn app.main:app --reload --app-dir backend
```

Trigger scrape:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/scrape/run"
```

Check posts:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/scraped-posts"
```

Check audit logs:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/scrape/runs"
```

## 6) Audit Fields Captured Per Run

Each run stores:
- `run id`
- `started_at`, `finished_at`
- `status` (`success` or `partial`)
- `total_fetched`, `total_created`
- `source_stats_json` (fetched/failed counters per source)
- `failures_json` (error strings)
