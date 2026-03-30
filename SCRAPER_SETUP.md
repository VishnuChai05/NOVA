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
   - `REDDIT_SOURCE_MODE=auto` (default)

Notes:
- The redirect URI is required by the app form, but this scraper flow does not use OAuth browser redirects.
- If the new portal asks for extra fields, keep the app internal and do not enable scopes you do not need.
- Reddit source mode options:
   - `REDDIT_SOURCE_MODE=praw`: force official Reddit API via PRAW
   - `REDDIT_SOURCE_MODE=apify`: use Apify token for Reddit discovery
   - `REDDIT_SOURCE_MODE=auto`: prefer PRAW, fallback to Apify

## 2) Apify Setup (Free Actors for Reddit & Quora)

### Free Actor Options (Recommended)

We use free Apify actors for both platforms:

1. **Reddit**: `apify/reddit-post-scraper`
   - Free tier available
   - Searches Reddit posts and comments
   - REDDIT_SOURCE_MODE=apify will use this actor

2. **Quora**: `apify/website-content-crawler`
   - Free tier available
   - Web crawler for Quora question/answer pages
   - APIFY_QUORA_ACTOR_ID preset to this

### Setup Steps

1. Create Apify account at https://apify.com
2. Generate API token from Apify Console: https://console.apify.com/account/integrations
3. Add token to `.env`:
   ```
   APIFY_API_TOKEN=<your_rotated_token>
   APIFY_REDDIT_ACTOR_ID=apify/reddit-post-scraper
   APIFY_QUORA_ACTOR_ID=apify/website-content-crawler
   ```

### Reddit Mode Options

Set `REDDIT_SOURCE_MODE` in `.env`:
- `REDDIT_SOURCE_MODE=praw` - Force official Reddit API via PRAW (requires Reddit dev credentials)
- `REDDIT_SOURCE_MODE=apify` - Use free Apify Reddit actor (requires APIFY_API_TOKEN)
- `REDDIT_SOURCE_MODE=auto` - Try PRAW first, fallback to Apify if PRAW fails

Example for Apify-only setup:
```env
REDDIT_SOURCE_MODE=apify
APIFY_API_TOKEN=apify_xxxxx...
APIFY_REDDIT_ACTOR_ID=apify/reddit-post-scraper
APIFY_QUORA_ACTOR_ID=apify/website-content-crawler
ALLOW_FALLBACK_SEED_DATA=false
```

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
