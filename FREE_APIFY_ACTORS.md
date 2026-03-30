# Free Apify Actors Guide

## Overview

This guide documents the free Apify actors integrated into the oh so u content engine for Reddit and Quora scraping.

## Actors Used

### 1. Reddit Scraper: `apify/reddit-post-scraper`

**URL**: https://apify.com/apify/reddit-post-scraper

**Features**:
- Scrapes Reddit posts, comments, and user profiles
- Free tier available (limited results per run)
- Supports search queries and subreddit browsing
- Returns structured data with title, description, score, URL

**Input Schema** (simplified):
```json
{
  "queries": ["bra fit", "shapewear recommendation", ...],
  "maxResults": 50,
  "includeNSFW": false
}
```

**Output Fields**:
- `url`: Post URL
- `title`: Post title
- `description`: Post content
- `score`: Upvote count

**Pricing**: Free tier with rate limits, paid runs available for higher volumes

---

### 2. Quora Scraper: `apify/website-content-crawler`

**URL**: https://apify.com/apify/website-content-crawler

**Features**:
- General-purpose web crawler, works well for Quora
- Crawls pages matching URL patterns
- Free tier available
- Extracts text content from HTML structure

**Input Schema** (simplified):
```json
{
  "startUrls": [
    "https://www.quora.com/search?q=bra+fit&type=question",
    "https://www.quora.com/search?q=shapewear&type=question"
  ],
  "maxRequestsPerCrawl": 50,
  "includeUrlGlobs": ["+quora.com**"]
}
```

**Output Fields**:
- `url`: Page URL
- `title`: Page title/heading
- `description`: Extracted text content
- `rank`: Success indicator

**Pricing**: Free tier with request limits, paid plans for scale

---

## Configuration

### Environment Variables

```env
# Required
APIFY_API_TOKEN=apify_xxxxx...

# Optional (defaults provided)
APIFY_REDDIT_ACTOR_ID=apify/reddit-post-scraper
APIFY_QUORA_ACTOR_ID=apify/website-content-crawler
```

### Backend Settings

From `backend/app/core/settings.py`:

```python
apify_reddit_actor_id: str = "apify/reddit-post-scraper"
apify_quora_actor_id: str = "apify/website-content-crawler"
```

---

## How to Get Free Credits

1. Sign up at https://apify.com
2. Every new account gets $5 free credits (as of 2026)
3. Each actor call consumes credits based on:
   - Number of API requests made
   - Volume of data extracted
   - Compute resources used

**Example Usage Costs**:
- Reddit scraper: ~$0.10–$0.50 per 50 posts (depends on intensity)
- Quora crawler: ~$0.15–$0.60 per 50 pages (depends on page size)

Free tier typically allows ~100–200 small runs before exhausting credits.

---

## Testing Locally

After setting `APIFY_API_TOKEN` in `.env`:

```powershell
# Trigger a scrape run
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/scrape/run"

# Check audit logs
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/scrape/runs" | ConvertTo-Json -Depth 5
```

Expected output in `source_stats_json`:
```json
{
  "reddit_apify": { "fetched": 25, "failed": 0 },
  "quora_apify": { "fetched": 30, "failed": 0 }
}
```

---

## Alternatives & Fallbacks

If free tier credits are exhausted:

1. **Use Reddit API directly** (free, no credits):
   - Set `REDDIT_SOURCE_MODE=praw`
   - Provide Reddit OAuth credentials
   - Quora still uses fallback web search

2. **Use Web Search Fallback**:
   - Set `ALLOW_FALLBACK_SEED_DATA=true`
   - Backend uses DuckDuckGo for Quora search
   - Returns fewer but real results

3. **Upgrade Apify Plan**:
   - $5–$50/month recurring
   - Higher rate limits and priority processing

---

## Monitoring & Debugging

The backend logs all Apify calls via `ScrapeRun` audit records:

```python
# View per-source statistics
GET /api/scrape/runs

# Response includes:
{
  "source_stats_json": {
    "reddit_apify": { "fetched": 10, "failed": 2 },
    "quora_apify": { "fetched": 8, "failed": 0 },
    "quora_search": { "fetched": 5, "failed": 1 }
  },
  "failures_json": [
    "reddit_apify: rate-limited (retry in 60s)",
    "quora_search: HTTP 429 from DuckDuckGo"
  ]
}
```

---

## Support & Links

- **Apify Console**: https://console.apify.com
- **Actor Store**: https://apify.com/store
- **Apify Docs**: https://docs.apify.com
- **API Reference**: https://docs.apify.com/api/client

---

## Version History

- **v1.0** (Mar 30, 2026): Integrated free Reddit and Quora actors
