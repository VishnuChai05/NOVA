from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Callable

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
from app.services.topic_classifier import classify_post_topic

logger = logging.getLogger(__name__)

_FORUM_SOURCE_CAP = 25
_FORUM_ALLOWED_CATEGORIES = {
    "bra",
    "shapewear",
    "panty",
    "fashion",
    "period-care",
}


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
    created_post_ids: list[str] | None = None


@dataclass
class SourceFetchResult:
    source: str
    rows: list[dict]
    failures: list[str]


@dataclass
class SourceFetchTask:
    name: str
    timeout_seconds: float
    fetch_fn: Callable[[], SourceFetchResult]


class ConcurrentScrapeError(RuntimeError):
    pass


_SCRAPE_RUN_LOCKS = {
    "all": threading.Lock(),
    "social": threading.Lock(),
    "web": threading.Lock(),
}


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
        max_posts_per_source=min(cfg.max_posts_per_source, _FORUM_SOURCE_CAP),
    )
    return SourceFetchResult(source="discussion_forums", rows=result["rows"], failures=result["failures"])


def _crawl_blog_domains(cfg: ScraperConfig) -> SourceFetchResult:
    result = URLCrawler(_content_fetcher()).crawl_blog_domains(
        domains=cfg.blog_domains,
        max_posts_per_source=cfg.max_posts_per_source,
        blog_crawl_max_urls_per_domain=cfg.blog_crawl_max_urls_per_domain,
    )
    return SourceFetchResult(source="blog_crawl", rows=result["rows"], failures=result["failures"])


def _fetch_reddit_with_fallback(cfg: ScraperConfig) -> SourceFetchResult:
    """Fetch Reddit data based on configured source mode with automatic fallback."""
    reddit_mode = settings.reddit_source_mode.strip().lower()

    if reddit_mode == "apify":
        logger.info("Fetching from Reddit via Apify...")
        return _fetch_reddit_via_apify(cfg)

    if reddit_mode == "praw":
        logger.info("Fetching from Reddit via PRAW...")
        praw_result = SocialMediaScraper(_content_fetcher()).fetch_reddit_posts(cfg)
        return SourceFetchResult(source="reddit", rows=praw_result["rows"], failures=praw_result["failures"])

    # auto mode: prefer PRAW, fallback to Apify
    logger.info("Fetching from Reddit (auto mode: trying PRAW first)...")
    praw_result = SocialMediaScraper(_content_fetcher()).fetch_reddit_posts(cfg)
    primary = SourceFetchResult(source="reddit", rows=praw_result["rows"], failures=praw_result["failures"])

    if primary.rows:
        return primary

    logger.info("PRAW returned no results, falling back to Apify...")
    fallback = _fetch_reddit_via_apify(cfg)
    return SourceFetchResult(
        source=fallback.source,
        rows=fallback.rows,
        failures=[*primary.failures, *fallback.failures],
    )


def _fetch_quora_with_fallback(cfg: ScraperConfig) -> SourceFetchResult:
    """Fetch Quora via Apify first, then web search fallback when empty."""
    logger.info("Fetching from Quora...")
    primary = _fetch_quora_via_apify(cfg)
    if primary.rows:
        return primary

    logger.info("Apify Quora returned no results, trying web search...")
    fallback = _fetch_quora_via_search(cfg)
    return SourceFetchResult(
        source=fallback.source,
        rows=fallback.rows,
        failures=[*primary.failures, *fallback.failures],
    )


def _run_source_task_with_timeout(task: SourceFetchTask, future: Future[SourceFetchResult]) -> SourceFetchResult:
    """Resolve a source fetch future with timeout and convert exceptions into failures."""
    timeout_seconds = max(1.0, float(task.timeout_seconds))
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        future.cancel()
        message = f"{task.name} timed out after {int(timeout_seconds)}s"
        logger.warning(message)
        return SourceFetchResult(source=task.name, rows=[], failures=[message])
    except Exception as exc:  # noqa: BLE001
        message = f"{task.name} failed: {exc}"
        logger.warning(message)
        return SourceFetchResult(source=task.name, rows=[], failures=[message])


def _fetch_sources_parallel(
    cfg: ScraperConfig,
    report: Callable[[int, str], None],
    source_type: str = "all",
) -> dict[str, SourceFetchResult]:
    """Fetch independent sources in parallel with per-source timeout guards."""
    tasks: list[SourceFetchTask] = []
    
    if source_type in ("all", "social"):
        tasks.extend([
            SourceFetchTask(
                name="reddit",
                timeout_seconds=settings.scrape_reddit_timeout_seconds,
                fetch_fn=lambda: _fetch_reddit_with_fallback(cfg),
            ),
            SourceFetchTask(
                name="quora",
                timeout_seconds=settings.scrape_quora_timeout_seconds,
                fetch_fn=lambda: _fetch_quora_with_fallback(cfg),
            ),
        ])

    if source_type in ("all", "web"):
        tasks.append(
            SourceFetchTask(
                name="discussion_forums",
                timeout_seconds=settings.scrape_forum_timeout_seconds,
                fetch_fn=lambda: _crawl_forum_domains(cfg),
            )
        )
        if cfg.crawl_full_blog_domains:
            tasks.append(
                SourceFetchTask(
                    name="blog_crawl",
                    timeout_seconds=settings.scrape_blog_timeout_seconds,
                    fetch_fn=lambda: _crawl_blog_domains(cfg),
                )
            )

    max_workers = max(1, min(int(settings.scrape_parallel_max_workers), len(tasks)))
    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures: list[tuple[SourceFetchTask, Future[SourceFetchResult]]] = []
    results: dict[str, SourceFetchResult] = {}

    try:
        for task in tasks:
            futures.append((task, executor.submit(task.fetch_fn)))

        total = len(futures)
        for index, (task, future) in enumerate(futures, start=1):
            result = _run_source_task_with_timeout(task, future)
            results[task.name] = result
            progress = 15 + int((50 * index) / max(1, total))
            report(progress, f"Fetched {task.name} ({len(result.rows)} rows)")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if source_type in ("all", "web") and not cfg.crawl_full_blog_domains:
        results["blog_crawl"] = SourceFetchResult(source="blog_crawl", rows=[], failures=[])

    return results


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


def generate_insights_for_posts(
    post_ids: list[str],
    db: Session,
    batch_size: int = 5,
    pause_seconds: float = 1.0,
) -> list[str]:
    """Generate insights for new posts in small batches to avoid API burst limits."""
    failures: list[str] = []
    if not post_ids:
        return failures

    for start in range(0, len(post_ids), batch_size):
        chunk = post_ids[start : start + batch_size]
        posts = db.query(ScrapedPost).filter(ScrapedPost.id.in_(chunk)).all()
        for post in posts:
            try:
                create_post_insight(db, post)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"insight validation failed for {post.url}: {exc}")
        if start + batch_size < len(post_ids):
            time.sleep(max(0.0, pause_seconds))

    return failures


def run_scrape(
    db: Session,
    progress_callback: Callable[[int, str], None] | None = None,
    generate_insights: bool = True,
    source_type: str = "all",
) -> ScrapeExecutionResult:
    lock = _SCRAPE_RUN_LOCKS.get(source_type, _SCRAPE_RUN_LOCKS["all"])
    if not lock.acquire(blocking=False):
        raise ConcurrentScrapeError(f"A {source_type} scrape run is already in progress")

    run: ScrapeRun | None = None
    finished = False
    
    try:
        def _report(progress: int, message: str) -> None:
            if progress_callback is not None:
                progress_callback(max(0, min(100, int(progress))), message)

        _report(5, "Loading configuration...")
        logger.info("Starting scrape run...")
        cfg = _load_config()
        logger.debug(f"Loaded config: {cfg.subreddits}, {cfg.quora_queries}")
        run = _start_run_record(db)
        logger.info(f"Created run record: {run.id}")

        source_stats: dict[str, dict[str, int]] = {}
        all_failures: list[str] = []
        _report(15, f"Fetching {source_type} sources in parallel...")
        fetched_sources = _fetch_sources_parallel(cfg, _report, source_type)
        
        reddit_result = fetched_sources.get("reddit")
        quora_result = fetched_sources.get("quora")
        discussion_result = fetched_sources.get("discussion_forums")
        full_blog_result = fetched_sources.get("blog_crawl")

        combined_rows = []
        for result in (reddit_result, quora_result, discussion_result, full_blog_result):
            if result:
                source_stats[result.source] = {
                    "fetched": len(result.rows),
                    "failed": len(result.failures),
                }
                all_failures.extend(result.failures)
                combined_rows.extend(result.rows)

        rows = _dedupe_by_url(combined_rows)
        _report(70, "Deduplicating and filtering...")

        if not rows and settings.allow_fallback_seed_data:
            logger.info("No posts fetched, using fallback seed data")
            rows = ScrapedDataProcessor.seed_posts()
            source_stats["fallback_seed"] = {"fetched": len(rows), "failed": 0}

        fetched_count = len(rows)
        logger.info(f"Fetched {fetched_count} total posts after deduplication")

        # Quality filtering and database persistence
        created = 0
        created_post_ids: list[str] = []
        _report(85, "Saving posts to database...")
        for post in rows:
            # Skip posts that don't meet quality thresholds
            if not ScrapedDataProcessor.is_quality_post(post):
                logger.debug(
                    f"Skipping low-quality post: title={len(post.get('title', ''))} chars, "
                    f"body={len(post.get('body', ''))} chars"
                )
                continue

            # Phase 3 relevance gate: skip off-topic rows before expensive downstream work.
            if not ScrapedDataProcessor.is_relevant_post(post, min_score=settings.scrape_relevance_min_score):
                continue

            url = (post.get("url") or "").strip()
            title = (post.get("title") or "").strip()
            body = (post.get("body") or "").strip()
            score = int(post.get("score") or 0)

            # Skip if already exists
            exists = db.query(ScrapedPost).filter(ScrapedPost.url == url).first()
            if exists:
                continue

            category_tag = classify_post_topic(title, body)

            # Keep forum crawl focused on core product-intent discussions to avoid noisy generic threads.
            if post.get("source") == "discussion_forums" and category_tag not in _FORUM_ALLOWED_CATEGORIES:
                continue

            published_at = ContentFetcher.parse_datetime_value(post.get("published_at"))

            scraped = ScrapedPost(
                source=post["source"],
                title=title,
                body=body,
                score=score,
                url=url,
                published_at=published_at,
                scraped_at=datetime.now(timezone.utc),
                category_tag=category_tag,
            )
            db.add(scraped)
            db.flush()

            created_post_ids.append(scraped.id)

            created += 1

        if generate_insights:
            _report(95, "Generating insights...")
            all_failures.extend(generate_insights_for_posts(created_post_ids, db))

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
        _report(100, "Done")
        logger.info(f"Scrape run {run.id} completed successfully")
        return ScrapeExecutionResult(
            run_id=run.id,
            created=created,
            fetched=fetched_count,
            status=status,
            message=message,
            created_post_ids=created_post_ids,
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
        lock.release()


def list_scrape_runs(db: Session, limit: int | None = None) -> list[ScrapeRun]:
    """List recent scrape runs."""
    query = db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()
