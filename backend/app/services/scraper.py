from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.scrape_run import ScrapeRun
from app.models.scraped_post import ScrapedPost
from app.services.content_validator import create_post_insight
from app.services.content_fetcher import ContentFetcher
from app.services.url_crawler import URLCrawler
from app.services.social_media_scraper import SocialMediaScraper
from app.services.scraped_data_processor import ScrapedDataProcessor

logger = logging.getLogger(__name__)


@dataclass
class ScraperConfig:
    subreddits: list[str]
    quora_queries: list[str]
    discussion_queries: list[str]
    blog_queries: list[str]
    forum_domains: list[str]
    blog_domains: list[str]
    max_posts_per_source: int
    min_score: int
    run_schedule: str
    crawl_full_blog_domains: bool
    blog_crawl_max_urls_per_domain: int


@dataclass
class ScrapeExecutionResult:
    run_id: str
    created: int
    fetched: int
    status: str
    message: str | None = None


@dataclass
class SourceFetchResult:
    source: str
    rows: list[dict]
    failures: list[str]


class ConcurrentScrapeError(RuntimeError):
    pass


_SCRAPE_RUN_LOCK = threading.Lock()


def _content_fetcher() -> ContentFetcher:
    return ContentFetcher()


def _retry_with_backoff(fn, label: str):
    return _content_fetcher().retry_with_backoff(fn, label)


def _classify_topic(text: str) -> str:
    return ScrapedDataProcessor.classify_topic(text)


def _dedupe_by_url(rows: list[dict]) -> list[dict]:
    return ScrapedDataProcessor.dedupe_by_url(rows)


def _url_matches_domains(url: str, domains: list[str]) -> bool:
    return URLCrawler().url_matches_domains(url, domains)


def _fetch_reddit_via_apify(cfg: ScraperConfig) -> SourceFetchResult:
    result = SocialMediaScraper(_content_fetcher()).fetch_reddit_via_apify(cfg)
    return SourceFetchResult(source="reddit_apify", rows=result["rows"], failures=result["failures"])


def _fetch_quora_via_apify(cfg: ScraperConfig) -> SourceFetchResult:
    result = SocialMediaScraper(_content_fetcher()).fetch_quora_via_apify(cfg)
    return SourceFetchResult(source="quora_apify", rows=result["rows"], failures=result["failures"])


def _fetch_quora_via_search(cfg: ScraperConfig) -> SourceFetchResult:
    result = SocialMediaScraper(_content_fetcher()).fetch_quora_via_search(cfg)
    return SourceFetchResult(source="quora_search", rows=result["rows"], failures=result["failures"])


def _crawl_forum_domains(cfg: ScraperConfig) -> SourceFetchResult:
    result = URLCrawler(_content_fetcher()).crawl_forum_domains(
        domains=cfg.forum_domains,
        max_posts_per_source=cfg.max_posts_per_source,
    )
    return SourceFetchResult(source="discussion_forums", rows=result["rows"], failures=result["failures"])


def _crawl_blog_domains(cfg: ScraperConfig) -> SourceFetchResult:
    result = URLCrawler(_content_fetcher()).crawl_blog_domains(
        domains=cfg.blog_domains,
        max_posts_per_source=cfg.max_posts_per_source,
        blog_crawl_max_urls_per_domain=cfg.blog_crawl_max_urls_per_domain,
    )
    return SourceFetchResult(source="blog_crawl", rows=result["rows"], failures=result["failures"])


def _default_config() -> ScraperConfig:
    """Return default scraper configuration."""
    return ScraperConfig(
        subreddits=[
            "TwoXIndia",
            "IndianSkincareAddicts",
            "IndianMakeupAddicts",
            "IndianFashionAddicts",
            "ABraThatFits",
            "AskWomen",
            "WomenInTech",
            "xxfitness",
            "FemaleFashionAdvice",
            "workingmoms",
            "TwoXChromosomes",
        ],
        quora_queries=[
            "women entrepreneurs India",
            "female founders",
            "postpartum body",
            "returned to work mother",
            "salary negotiation women",
            "burnout women",
            "body neutrality",
            "maternity wear India",
            "wireless bra",
            "strapless bra",
            "nursing bra",
            "period care",
            "sustainable fashion",
            "plus size fashion",
        ],
        discussion_queries=[
            "mom guilt",
            "mental load motherhood",
            "body positivity",
            "corporate women challenges",
            "startup women advice",
            "self care routine",
            "comfortable workwear",
            "women activewear",
            "sleepwear comfort",
            "bra fitting",
            "shapewear",
            "women hygiene",
        ],
        blog_queries=[
            "best bras for Indian women blog",
            "women hygiene products India blog",
            "period care tips India blog",
            "shapewear comfort guide India blog",
            "women innerwear reviews India blog",
        ],
        forum_domains=[
            "reddit.com",
            "quora.com",
            "girlsaskguys.com",
            "thegirlsspot.com",
            "community.babycenter.com",
            "mumsnet.com",
            "community.whattoexpect.com",
            "netmums.com",
        ],
        blog_domains=[
            "blog.ohsou.com",
            "healthshots.com",
            "stylecraze.com",
            "bewakoof.com",
            "womensweb.in",
        ],
        max_posts_per_source=50,
        min_score=10,
        run_schedule="0 9 * * 1",
        crawl_full_blog_domains=True,
        blog_crawl_max_urls_per_domain=120,
    )


def _load_config() -> ScraperConfig:
    """Load scraper configuration from YAML file."""
    project_root = Path(__file__).resolve().parents[3]
    config_path = project_root / settings.scraper_config_path
    if not config_path.exists():
        return _default_config()

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    defaults = _default_config()
    return ScraperConfig(
        subreddits=[str(item) for item in data.get("subreddits", [])] or defaults.subreddits,
        quora_queries=[str(item) for item in data.get("quora_queries", [])] or defaults.quora_queries,
        discussion_queries=[str(item) for item in data.get("discussion_queries", [])] or defaults.discussion_queries,
        blog_queries=[str(item) for item in data.get("blog_queries", [])] or defaults.blog_queries,
        forum_domains=[str(item) for item in data.get("forum_domains", [])] or defaults.forum_domains,
        blog_domains=[str(item) for item in data.get("blog_domains", [])] or defaults.blog_domains,
        max_posts_per_source=int(data.get("max_posts_per_source", defaults.max_posts_per_source)),
        min_score=int(data.get("min_score", defaults.min_score)),
        run_schedule=str(data.get("run_schedule", defaults.run_schedule)),
        crawl_full_blog_domains=bool(data.get("crawl_full_blog_domains", defaults.crawl_full_blog_domains)),
        blog_crawl_max_urls_per_domain=int(
            data.get("blog_crawl_max_urls_per_domain", defaults.blog_crawl_max_urls_per_domain)
        ),
    )


def _config_path() -> Path:
    """Get path to scraper configuration file."""
    project_root = Path(__file__).resolve().parents[3]
    return project_root / settings.scraper_config_path


def get_scraper_config() -> ScraperConfig:
    """Get current scraper configuration."""
    return _load_config()


def save_scraper_config(cfg: ScraperConfig) -> ScraperConfig:
    """Save scraper configuration to YAML file."""
    config_path = _config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "subreddits": cfg.subreddits,
        "quora_queries": cfg.quora_queries,
        "discussion_queries": cfg.discussion_queries,
        "blog_queries": cfg.blog_queries,
        "forum_domains": cfg.forum_domains,
        "blog_domains": cfg.blog_domains,
        "max_posts_per_source": cfg.max_posts_per_source,
        "min_score": cfg.min_score,
        "run_schedule": cfg.run_schedule,
        "crawl_full_blog_domains": cfg.crawl_full_blog_domains,
        "blog_crawl_max_urls_per_domain": cfg.blog_crawl_max_urls_per_domain,
    }
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return _load_config()


def _start_run_record(db: Session) -> ScrapeRun:
    """Create and start a new scrape run record."""
    run = ScrapeRun(
        # Some legacy SQLite schemas still have finished_at as NOT NULL.
        # Seed it at start and overwrite with the real completion time later.
        finished_at=datetime.now(timezone.utc),
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
    """Finalize a scrape run record."""
    run.finished_at = datetime.now(timezone.utc)
    run.status = status
    run.total_fetched = fetched
    run.total_created = created
    run.source_stats_json = json.dumps(source_stats)
    run.failures_json = json.dumps(failures)
    db.commit()


def run_scrape(db: Session) -> ScrapeExecutionResult:
    """
    Execute a complete scrape run.
    
    Orchestrates content fetching from all sources, deduplication,
    quality filtering, database persistence, and insight generation.
    
    Raises:
        ConcurrentScrapeError: If a scrape run is already in progress
    """
    if not _SCRAPE_RUN_LOCK.acquire(blocking=False):
        raise ConcurrentScrapeError("A scrape run is already in progress")

    run: ScrapeRun | None = None
    finished = False
    
    try:
        logger.info("Starting scrape run...")
        cfg = _load_config()
        logger.debug(f"Loaded config: {cfg.subreddits}, {cfg.quora_queries}")
        run = _start_run_record(db)
        logger.info(f"Created run record: {run.id}")

        source_stats: dict[str, dict[str, int]] = {}
        all_failures: list[str] = []

        # Reddit fetching (source priority: PRAW > Apify by default)
        reddit_mode = settings.reddit_source_mode.strip().lower()
        reddit_result: SourceFetchResult

        if reddit_mode == "apify":
            logger.info("Fetching from Reddit via Apify...")
            reddit_result = _fetch_reddit_via_apify(cfg)
        elif reddit_mode == "praw":
            logger.info("Fetching from Reddit via PRAW...")
            praw_result = SocialMediaScraper(_content_fetcher()).fetch_reddit_posts(cfg)
            reddit_result = SourceFetchResult(source="reddit", rows=praw_result["rows"], failures=praw_result["failures"])
        else:
            # auto mode: prefer PRAW, fallback to Apify
            logger.info("Fetching from Reddit (auto mode: trying PRAW first)...")
            praw_result = SocialMediaScraper(_content_fetcher()).fetch_reddit_posts(cfg)
            reddit_primary = SourceFetchResult(
                source="reddit",
                rows=praw_result["rows"],
                failures=praw_result["failures"],
            )
            source_stats[reddit_primary.source] = {
                "fetched": len(reddit_primary.rows),
                "failed": len(reddit_primary.failures),
            }
            all_failures.extend(reddit_primary.failures)

            if reddit_primary.rows:
                reddit_result = reddit_primary
            else:
                logger.info("PRAW returned no results, falling back to Apify...")
                reddit_result = _fetch_reddit_via_apify(cfg)

        source_stats[reddit_result.source] = {
            "fetched": len(reddit_result.rows),
            "failed": len(reddit_result.failures),
        }
        all_failures.extend(reddit_result.failures)

        # Quora fetching
        logger.info("Fetching from Quora...")
        quora_result = _fetch_quora_via_apify(cfg)
        source_stats[quora_result.source] = {
            "fetched": len(quora_result.rows),
            "failed": len(quora_result.failures),
        }
        all_failures.extend(quora_result.failures)

        if not quora_result.rows:
            logger.info("Apify Quora returned no results, trying web search...")
            quora_result = _fetch_quora_via_search(cfg)
            source_stats[quora_result.source] = {
                "fetched": len(quora_result.rows),
                "failed": len(quora_result.failures),
            }
            all_failures.extend(quora_result.failures)

        # Discussion forums crawling
        logger.info("Crawling forum domains...")
        discussion_result = _crawl_forum_domains(cfg)
        source_stats[discussion_result.source] = {
            "fetched": len(discussion_result.rows),
            "failed": len(discussion_result.failures),
        }
        all_failures.extend(discussion_result.failures)

        # Blog crawling
        logger.info("Crawling blog domains...")
        if cfg.crawl_full_blog_domains:
            full_blog_result = _crawl_blog_domains(cfg)
        else:
            full_blog_result = SourceFetchResult(source="blog_crawl", rows=[], failures=[])

        source_stats[full_blog_result.source] = {
            "fetched": len(full_blog_result.rows),
            "failed": len(full_blog_result.failures),
        }
        all_failures.extend(full_blog_result.failures)

        # Combine and deduplicate all results
        combined_rows = (
            reddit_result.rows
            + quora_result.rows
            + discussion_result.rows
            + full_blog_result.rows
        )
        rows = _dedupe_by_url(combined_rows)

        if not rows and settings.allow_fallback_seed_data:
            logger.info("No posts fetched, using fallback seed data")
            rows = ScrapedDataProcessor.seed_posts()
            source_stats["fallback_seed"] = {"fetched": len(rows), "failed": 0}

        fetched_count = len(rows)
        logger.info(f"Fetched {fetched_count} total posts after deduplication")

        # Quality filtering and database persistence
        created = 0
        for post in rows:
            # Skip posts that don't meet quality thresholds
            if not ScrapedDataProcessor.is_quality_post(post):
                logger.debug(
                    f"Skipping low-quality post: title={len(post.get('title', ''))} chars, "
                    f"body={len(post.get('body', ''))} chars"
                )
                continue

            url = (post.get("url") or "").strip()
            title = (post.get("title") or "").strip()
            body = (post.get("body") or "").strip()
            score = int(post.get("score") or 0)

            # Skip if already exists
            exists = db.query(ScrapedPost).filter(ScrapedPost.url == url).first()
            if exists:
                continue

            scraped = ScrapedPost(
                source=post["source"],
                title=title,
                body=body,
                score=score,
                url=url,
                scraped_at=datetime.now(timezone.utc),
                category_tag=_classify_topic(f"{title} {body}"),
            )
            db.add(scraped)
            db.flush()

            try:
                create_post_insight(db, scraped)
            except Exception as exc:  # noqa: BLE001
                all_failures.append(f"insight validation failed for {url}: {exc}")

            created += 1

        status = "success" if created > 0 else "partial"
        message = None
        if created == 0 and fetched_count > 0:
            message = "No new posts found. These posts already exist in your library. Try again in a few days or add new sources in Settings."
        elif created == 0 and fetched_count == 0:
            message = "No posts found. Try adjusting your queries or domains in Settings."

        logger.info(f"Scrape run {run.id}: {fetched_count} fetched, {created} created. Status: {status}")
        if message:
            logger.info(f"Message: {message}")

        _finish_run_record(
            db,
            run=run,
            status=status,
            fetched=fetched_count,
            created=created,
            source_stats=source_stats,
            failures=all_failures,
        )
        finished = True
        logger.info(f"Scrape run {run.id} completed successfully")
        return ScrapeExecutionResult(
            run_id=run.id, created=created, fetched=fetched_count, status=status, message=message
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scrape run failed with unexpected error")
        if run is not None and not finished:
            _finish_run_record(
                db,
                run=run,
                status="failed",
                fetched=0,
                created=0,
                source_stats={},
                failures=[str(exc)],
            )
        raise
    finally:
        _SCRAPE_RUN_LOCK.release()


def list_scrape_runs(db: Session, limit: int | None = None) -> list[ScrapeRun]:
    """List recent scrape runs."""
    query = db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()
