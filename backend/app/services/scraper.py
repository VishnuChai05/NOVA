from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.scrape_run import ScrapeRun
from app.models.scraped_post import ScrapedPost

try:
    import praw
except ImportError:  # pragma: no cover - optional runtime dependency
    praw = None

try:
    from apify_client import ApifyClient
except ImportError:  # pragma: no cover - optional runtime dependency
    ApifyClient = None


@dataclass
class ScraperConfig:
    subreddits: list[str]
    quora_queries: list[str]
    max_posts_per_source: int
    min_score: int


@dataclass
class ScrapeExecutionResult:
    run_id: str
    created: int
    fetched: int
    status: str


@dataclass
class SourceFetchResult:
    source: str
    rows: list[dict]
    failures: list[str]


def _reddit_queries() -> list[str]:
    return [
        "bra uncomfortable",
        "bra fit",
        "shapewear recommendation",
        "strapless bra",
        "nursing bra India",
        "seamless bra review",
        "bra for big chest",
        "invisible bra",
        "lingerie India",
    ]


def _classify_topic(text: str) -> str:
    content = text.lower()
    if "bra" in content:
        return "bra"
    if "shape" in content:
        return "shapewear"
    if "panty" in content:
        return "panty"
    if "fashion" in content or "outfit" in content:
        return "fashion"
    return "other"


def _default_config() -> ScraperConfig:
    return ScraperConfig(
        subreddits=[
            "ABraThatFits",
            "femalefashionadvice",
            "AskWomen",
            "IndiaFashion",
            "bigboobproblems",
            "weddingplanning",
        ],
        quora_queries=[
            "best bra for Indian women",
            "shapewear India",
            "comfortable bra all day",
            "bra size guide India",
            "lingerie for saree",
            "wireless bra review India",
        ],
        max_posts_per_source=50,
        min_score=10,
    )


def _load_config() -> ScraperConfig:
    project_root = Path(__file__).resolve().parents[3]
    config_path = project_root / settings.scraper_config_path
    if not config_path.exists():
        return _default_config()

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return ScraperConfig(
        subreddits=[str(item) for item in data.get("subreddits", [])] or _default_config().subreddits,
        quora_queries=[str(item) for item in data.get("quora_queries", [])]
        or _default_config().quora_queries,
        max_posts_per_source=int(data.get("max_posts_per_source", 50)),
        min_score=int(data.get("min_score", 10)),
    )


def _retry_with_backoff(fn, label: str):
    last_error: Exception | None = None
    attempts = max(1, int(settings.scraper_retry_attempts))
    base = max(0.1, float(settings.scraper_backoff_base_seconds))

    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(base * (2 ** (attempt - 1)))

    raise RuntimeError(f"{label} failed after {attempts} attempts: {last_error}") from last_error


def _fetch_reddit_posts(cfg: ScraperConfig) -> SourceFetchResult:
    if not settings.reddit_client_id or not settings.reddit_client_secret or praw is None:
        return SourceFetchResult(source="reddit", rows=[], failures=["Reddit credentials or dependency missing"])

    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )

    queries = _reddit_queries()

    results: list[dict] = []
    failures: list[str] = []
    per_subreddit_limit = max(3, cfg.max_posts_per_source // max(1, len(cfg.subreddits)))
    for sub_name in cfg.subreddits:
        subreddit = reddit.subreddit(sub_name)
        for query in queries:
            try:
                submissions = _retry_with_backoff(
                    lambda: list(subreddit.search(query, sort="new", limit=per_subreddit_limit)),
                    f"reddit search {sub_name}:{query}",
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(str(exc))
                continue

            for submission in submissions:
                if int(getattr(submission, "score", 0)) < cfg.min_score:
                    continue

                top_comments: list[str] = []
                try:
                    submission.comments.replace_more(limit=0)
                    top_comments = [c.body for c in submission.comments[:5] if getattr(c, "body", "")]
                except Exception:  # noqa: BLE001
                    top_comments = []

                body = (submission.selftext or "").strip()
                if top_comments:
                    body = f"{body}\n\nTop comments:\n" + "\n".join(f"- {c}" for c in top_comments)

                results.append(
                    {
                        "source": "reddit",
                        "title": submission.title,
                        "body": body,
                        "score": int(submission.score or 0),
                        "url": f"https://www.reddit.com{submission.permalink}",
                    }
                )

                if len(results) >= cfg.max_posts_per_source:
                    return SourceFetchResult(source="reddit", rows=results, failures=failures)

            # Keep request pace predictable even if API wrappers also throttle.
            time.sleep(max(0.0, float(settings.reddit_query_delay_seconds)))

    return SourceFetchResult(source="reddit", rows=results, failures=failures)


def _fetch_reddit_via_apify(cfg: ScraperConfig) -> SourceFetchResult:
    if not settings.apify_api_token or ApifyClient is None:
        return SourceFetchResult(source="reddit_apify", rows=[], failures=["Apify token or dependency missing"])

    client = ApifyClient(settings.apify_api_token)
    actor_id = settings.apify_reddit_actor_id

    # Format Reddit queries for the dedicated Reddit scraper
    queries: list[str] = _reddit_queries()

    run_input = {
        "queries": queries,
        "maxResults": cfg.max_posts_per_source,
    }

    try:
        run = _retry_with_backoff(lambda: client.actor(actor_id).call(run_input=run_input), "apify reddit actor run")
    except Exception as exc:  # noqa: BLE001
        return SourceFetchResult(source="reddit_apify", rows=[], failures=[str(exc)])

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        return SourceFetchResult(source="reddit_apify", rows=[], failures=["No dataset id from Apify actor"])

    results: list[dict] = []
    failures: list[str] = []
    try:
        items_iter = client.dataset(dataset_id).iterate_items()
    except Exception as exc:  # noqa: BLE001
        return SourceFetchResult(source="reddit_apify", rows=[], failures=[str(exc)])

    for item in items_iter:
        url = str(item.get("url") or "")
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        if "reddit.com" not in url or not title:
            continue

        results.append(
            {
                "source": "reddit",
                "title": title,
                "body": description,
                "score": 0,
                "url": url,
            }
        )
        if len(results) >= cfg.max_posts_per_source:
            break

    return SourceFetchResult(source="reddit_apify", rows=results, failures=failures)


def _fetch_quora_via_apify(cfg: ScraperConfig) -> SourceFetchResult:
    if not settings.apify_api_token or ApifyClient is None:
        return SourceFetchResult(source="quora_apify", rows=[], failures=["Apify token or dependency missing"])

    client = ApifyClient(settings.apify_api_token)
    actor_id = settings.apify_quora_actor_id
    
    # Website crawler for Quora - scrape top URLs for each query
    urls: list[str] = []
    for q in cfg.quora_queries:
        urls.append(f"https://www.quora.com/search?q={q.replace(' ', '+')}&type=question")
    
    run_input = {
        "startUrls": [f"https://www.quora.com/search?q={q.replace(' ', '+')}&type=question" for q in cfg.quora_queries],
        "maxRequestsPerCrawl": cfg.max_posts_per_source,
        "includeUrlGlobs": ["+quora.com**"],
    }

    try:
        run = _retry_with_backoff(lambda: client.actor(actor_id).call(run_input=run_input), "apify actor run")
    except Exception as exc:  # noqa: BLE001
        return SourceFetchResult(source="quora_apify", rows=[], failures=[str(exc)])

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        return SourceFetchResult(source="quora_apify", rows=[], failures=["No dataset id from Apify actor"])

    results: list[dict] = []
    failures: list[str] = []
    try:
        items_iter = client.dataset(dataset_id).iterate_items()
    except Exception as exc:  # noqa: BLE001
        return SourceFetchResult(source="quora_apify", rows=[], failures=[str(exc)])

    for item in items_iter:
        url = str(item.get("url") or "")
        title = str(item.get("title") or "").strip()
        if "quora.com" not in url or not title:
            continue

        results.append(
            {
                "source": "quora",
                "title": title,
                "body": str(item.get("description") or "").strip(),
                "score": int(item.get("rank") or 0),
                "url": url,
            }
        )
        if len(results) >= cfg.max_posts_per_source:
            break

    return SourceFetchResult(source="quora_apify", rows=results, failures=failures)


def _fetch_quora_via_search(cfg: ScraperConfig) -> SourceFetchResult:
    results: list[dict] = []
    failures: list[str] = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ohsou-content-engine/1.0)"}

    with httpx.Client(timeout=20, headers=headers, follow_redirects=True) as client:
        for query in cfg.quora_queries:
            try:
                response = _retry_with_backoff(
                    lambda: client.get("https://duckduckgo.com/html/", params={"q": f"site:quora.com {query}"}),
                    f"quora search query {query}",
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(str(exc))
                continue

            if response.status_code != 200:
                failures.append(f"query '{query}' status={response.status_code}")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            links = soup.select("a.result__a")
            snippets = soup.select("a.result__snippet")

            for idx, link in enumerate(links):
                title = link.get_text(" ", strip=True)
                url = link.get("href") or ""
                snippet = snippets[idx].get_text(" ", strip=True) if idx < len(snippets) else ""
                if "quora.com" not in url or not title:
                    continue

                results.append(
                    {
                        "source": "quora",
                        "title": title,
                        "body": snippet,
                        "score": 0,
                        "url": url,
                    }
                )
                if len(results) >= cfg.max_posts_per_source:
                    return SourceFetchResult(source="quora_search", rows=results, failures=failures)

            time.sleep(max(0.0, float(settings.reddit_query_delay_seconds)))

    return SourceFetchResult(source="quora_search", rows=results, failures=failures)


def _seed_posts() -> list[dict]:
    return [
        {
            "source": "reddit",
            "title": "Need a comfortable bra for long office days",
            "body": "My straps dig in by evening. Looking for seamless options.",
            "score": 41,
            "url": "https://reddit.com/r/ABraThatFits/sample-1",
        },
        {
            "source": "quora",
            "title": "What shapewear works under saree for weddings?",
            "body": "Seeking breathable support for long ceremonies.",
            "score": 27,
            "url": "https://quora.com/sample-1",
        },
    ]


def _dedupe_by_url(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for row in rows:
        url = str(row.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(row)
    return deduped


def _start_run_record(db: Session) -> ScrapeRun:
    run = ScrapeRun(
        status="running",
        source_stats_json="{}",
        failures_json="[]",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _finish_run_record(
    db: Session,
    run: ScrapeRun,
    status: str,
    fetched: int,
    created: int,
    source_stats: dict,
    failures: list[str],
) -> None:
    run.finished_at = datetime.now(timezone.utc)
    run.status = status
    run.total_fetched = fetched
    run.total_created = created
    run.source_stats_json = json.dumps(source_stats)
    run.failures_json = json.dumps(failures)
    db.commit()


def run_scrape(db: Session) -> ScrapeExecutionResult:
    cfg = _load_config()
    run = _start_run_record(db)

    source_stats: dict[str, dict[str, int]] = {}
    all_failures: list[str] = []

    reddit_mode = settings.reddit_source_mode.strip().lower()
    reddit_result: SourceFetchResult

    if reddit_mode == "apify":
        reddit_result = _fetch_reddit_via_apify(cfg)
        source_stats[reddit_result.source] = {
            "fetched": len(reddit_result.rows),
            "failed": len(reddit_result.failures),
        }
        all_failures.extend(reddit_result.failures)
    elif reddit_mode == "praw":
        reddit_result = _fetch_reddit_posts(cfg)
        source_stats[reddit_result.source] = {
            "fetched": len(reddit_result.rows),
            "failed": len(reddit_result.failures),
        }
        all_failures.extend(reddit_result.failures)
    else:
        # auto mode: prefer PRAW, then fallback to Apify if no rows.
        reddit_primary = _fetch_reddit_posts(cfg)
        source_stats[reddit_primary.source] = {
            "fetched": len(reddit_primary.rows),
            "failed": len(reddit_primary.failures),
        }
        all_failures.extend(reddit_primary.failures)

        if reddit_primary.rows:
            reddit_result = reddit_primary
        else:
            reddit_secondary = _fetch_reddit_via_apify(cfg)
            source_stats[reddit_secondary.source] = {
                "fetched": len(reddit_secondary.rows),
                "failed": len(reddit_secondary.failures),
            }
            all_failures.extend(reddit_secondary.failures)
            reddit_result = reddit_secondary

    quora_result = _fetch_quora_via_apify(cfg)
    source_stats[quora_result.source] = {"fetched": len(quora_result.rows), "failed": len(quora_result.failures)}
    all_failures.extend(quora_result.failures)
    if not quora_result.rows:
        quora_result = _fetch_quora_via_search(cfg)
        source_stats[quora_result.source] = {
            "fetched": len(quora_result.rows),
            "failed": len(quora_result.failures),
        }
        all_failures.extend(quora_result.failures)

    rows = _dedupe_by_url(reddit_result.rows + quora_result.rows)

    if not rows and settings.allow_fallback_seed_data:
        rows = _seed_posts()
        source_stats["fallback_seed"] = {"fetched": len(rows), "failed": 0}

    fetched_count = len(rows)

    created = 0
    for post in rows:
        exists = db.query(ScrapedPost).filter(ScrapedPost.url == post["url"]).first()
        if exists:
            continue

        db.add(
            ScrapedPost(
                source=post["source"],
                title=post["title"],
                body=post["body"],
                score=post["score"],
                url=post["url"],
                scraped_at=datetime.now(timezone.utc),
                category_tag=_classify_topic(f"{post['title']} {post['body']}"),
            )
        )
        created += 1

    status = "success" if created > 0 else "partial"
    _finish_run_record(
        db,
        run=run,
        status=status,
        fetched=fetched_count,
        created=created,
        source_stats=source_stats,
        failures=all_failures,
    )
    return ScrapeExecutionResult(run_id=run.id, created=created, fetched=fetched_count, status=status)


def list_scrape_runs(db: Session, limit: int = 20) -> list[ScrapeRun]:
    return db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(limit).all()
