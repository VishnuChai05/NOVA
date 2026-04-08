from __future__ import annotations

from datetime import datetime, timezone
import time
from types import SimpleNamespace

import app.services.scraper as scraper_service
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.scraped_insight import ScrapedInsight
from app.models.scraped_post import ScrapedPost
from app.services.scraper import ScraperConfig, SourceFetchResult
from app.services.content_fetcher import ContentFetcher
from app.core import settings


def _clear_scrape_tables() -> None:
    init_db()
    db = SessionLocal()
    try:
        db.query(ScrapedInsight).delete()
        db.query(ScrapedPost).delete()
        db.commit()
    finally:
        db.close()


def _stub_run_record_writes(monkeypatch, run_id: str = "test-run-1") -> None:
    monkeypatch.setattr(
        scraper_service,
        "_start_run_record",
        lambda db: SimpleNamespace(id=run_id),
    )
    monkeypatch.setattr(scraper_service, "_finish_run_record", lambda *args, **kwargs: args[0].commit())


def test_retry_with_backoff_retries_runtime_error(monkeypatch) -> None:
    """Test that ContentFetcher.retry_with_backoff retries on RuntimeError."""
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("temporary")
        return "ok"

    fetcher = ContentFetcher(retry_attempts=3, backoff_base_seconds=0.01)
    monkeypatch.setattr(fetcher, "backoff_base_seconds", 0.01)
    
    import app.services.content_fetcher as content_fetcher
    monkeypatch.setattr(content_fetcher.time, "sleep", lambda x: sleeps.append(x))

    result = fetcher.retry_with_backoff(flaky, "flaky-call")

    assert result == "ok"
    assert attempts["n"] == 3
    assert len(sleeps) == 2


def test_save_and_load_scraper_config_round_trip(monkeypatch, tmp_path) -> None:
    cfg_path = tmp_path / "scraper-config.yaml"
    monkeypatch.setattr(scraper_service.settings, "scraper_config_path", str(cfg_path))

    input_cfg = ScraperConfig(
        subreddits=["TwoXIndia"],
        quora_queries=["women comfort"],
        discussion_queries=["forum query"],
        blog_queries=["blog query"],
        forum_domains=["reddit.com"],
        blog_domains=["example.com"],
        max_posts_per_source=25,
        min_score=5,
        run_schedule="0 12 * * 1",
        crawl_full_blog_domains=True,
        blog_crawl_max_urls_per_domain=80,
    )

    saved = scraper_service.save_scraper_config(input_cfg)
    loaded = scraper_service.get_scraper_config()

    assert saved == loaded
    assert loaded.max_posts_per_source == 25
    assert loaded.run_schedule == "0 12 * * 1"


def test_run_scrape_success_persists_run_and_posts(monkeypatch) -> None:
    _clear_scrape_tables()
    _stub_run_record_writes(monkeypatch, run_id="run-success-1")

    cfg = ScraperConfig(
        subreddits=["TwoXIndia"],
        quora_queries=["query"],
        discussion_queries=["forum query"],
        blog_queries=["blog query"],
        forum_domains=["reddit.com"],
        blog_domains=["example.com"],
        max_posts_per_source=50,
        min_score=10,
        run_schedule="0 9 * * 1",
        crawl_full_blog_domains=False,
        blog_crawl_max_urls_per_domain=50,
    )

    monkeypatch.setattr(scraper_service.settings, "reddit_source_mode", "apify")
    monkeypatch.setattr(scraper_service.settings, "allow_fallback_seed_data", False)
    monkeypatch.setattr(scraper_service.settings, "scrape_relevance_min_score", 0)
    monkeypatch.setattr(scraper_service, "_load_config", lambda: cfg)

    reddit_rows = [
        {
            "source": "reddit",
            "title": "A very useful post title",
            "body": "x" * 200,
            "score": 20,
            "url": "https://reddit.com/post-1",
        },
        {
            "source": "reddit",
            "title": "A very useful post title",
            "body": "x" * 200,
            "score": 20,
            "url": "https://reddit.com/post-1",
        },
        {
            "source": "reddit",
            "title": "short",
            "body": "x" * 200,
            "score": 20,
            "url": "https://reddit.com/post-2",
        },
        {
            "source": "reddit",
            "title": "Another acceptable title",
            "body": "too short",
            "score": 20,
            "url": "https://reddit.com/post-3",
        },
    ]

    monkeypatch.setattr(
        scraper_service,
        "_fetch_reddit_via_apify",
        lambda _cfg: SourceFetchResult(source="reddit_apify", rows=reddit_rows, failures=[]),
    )
    monkeypatch.setattr(
        scraper_service,
        "_fetch_quora_via_apify",
        lambda _cfg: SourceFetchResult(source="quora_apify", rows=[], failures=[]),
    )
    monkeypatch.setattr(
        scraper_service,
        "_fetch_quora_via_search",
        lambda _cfg: SourceFetchResult(source="quora_search", rows=[], failures=[]),
    )
    monkeypatch.setattr(
        scraper_service,
        "_crawl_forum_domains",
        lambda _cfg: SourceFetchResult(source="discussion_forums", rows=[], failures=[]),
    )

    db = SessionLocal()
    try:
        result = scraper_service.run_scrape(db)
    finally:
        db.close()

    assert result.status == "success"
    assert result.fetched == 3
    assert result.created == 1
    assert result.message is None

    db = SessionLocal()
    try:
        posts = db.query(ScrapedPost).all()
        insights = db.query(ScrapedInsight).all()
    finally:
        db.close()

    assert len(posts) == 1
    assert posts[0].url == "https://reddit.com/post-1"
    assert len(insights) == 1
    assert insights[0].post_id == posts[0].id


def test_run_scrape_partial_with_no_fetched_rows(monkeypatch) -> None:
    _clear_scrape_tables()
    _stub_run_record_writes(monkeypatch, run_id="run-partial-0")

    cfg = ScraperConfig(
        subreddits=["TwoXIndia"],
        quora_queries=["query"],
        discussion_queries=["forum query"],
        blog_queries=["blog query"],
        forum_domains=["reddit.com"],
        blog_domains=["example.com"],
        max_posts_per_source=50,
        min_score=10,
        run_schedule="0 9 * * 1",
        crawl_full_blog_domains=False,
        blog_crawl_max_urls_per_domain=50,
    )

    monkeypatch.setattr(scraper_service.settings, "reddit_source_mode", "apify")
    monkeypatch.setattr(scraper_service.settings, "allow_fallback_seed_data", False)
    monkeypatch.setattr(scraper_service, "_load_config", lambda: cfg)

    monkeypatch.setattr(scraper_service, "_fetch_reddit_via_apify", lambda _cfg: SourceFetchResult(source="reddit_apify", rows=[], failures=[]))
    monkeypatch.setattr(scraper_service, "_fetch_quora_via_apify", lambda _cfg: SourceFetchResult(source="quora_apify", rows=[], failures=[]))
    monkeypatch.setattr(scraper_service, "_fetch_quora_via_search", lambda _cfg: SourceFetchResult(source="quora_search", rows=[], failures=[]))
    monkeypatch.setattr(scraper_service, "_crawl_forum_domains", lambda _cfg: SourceFetchResult(source="discussion_forums", rows=[], failures=[]))

    db = SessionLocal()
    try:
        result = scraper_service.run_scrape(db)
    finally:
        db.close()

    assert result.status == "partial"
    assert result.fetched == 0
    assert result.created == 0
    assert result.message is not None
    assert "No posts found" in result.message


def test_run_scrape_partial_when_all_fetched_are_duplicates(monkeypatch) -> None:
    _clear_scrape_tables()
    _stub_run_record_writes(monkeypatch, run_id="run-partial-dup")

    existing_url = "https://reddit.com/existing"
    db = SessionLocal()
    try:
        db.add(
            ScrapedPost(
                source="reddit",
                title="Existing row",
                body="x" * 200,
                score=12,
                url=existing_url,
                scraped_at=datetime.now(timezone.utc),
                category_tag="other",
            )
        )
        db.commit()
    finally:
        db.close()

    cfg = ScraperConfig(
        subreddits=["TwoXIndia"],
        quora_queries=["query"],
        discussion_queries=["forum query"],
        blog_queries=["blog query"],
        forum_domains=["reddit.com"],
        blog_domains=["example.com"],
        max_posts_per_source=50,
        min_score=10,
        run_schedule="0 9 * * 1",
        crawl_full_blog_domains=False,
        blog_crawl_max_urls_per_domain=50,
    )

    monkeypatch.setattr(scraper_service.settings, "reddit_source_mode", "apify")
    monkeypatch.setattr(scraper_service.settings, "allow_fallback_seed_data", False)
    monkeypatch.setattr(scraper_service, "_load_config", lambda: cfg)
    monkeypatch.setattr(
        scraper_service,
        "_fetch_reddit_via_apify",
        lambda _cfg: SourceFetchResult(
            source="reddit_apify",
            rows=[
                {
                    "source": "reddit",
                    "title": "Duplicate candidate",
                    "body": "x" * 200,
                    "score": 20,
                    "url": existing_url,
                }
            ],
            failures=[],
        ),
    )
    monkeypatch.setattr(scraper_service, "_fetch_quora_via_apify", lambda _cfg: SourceFetchResult(source="quora_apify", rows=[], failures=[]))
    monkeypatch.setattr(scraper_service, "_fetch_quora_via_search", lambda _cfg: SourceFetchResult(source="quora_search", rows=[], failures=[]))
    monkeypatch.setattr(scraper_service, "_crawl_forum_domains", lambda _cfg: SourceFetchResult(source="discussion_forums", rows=[], failures=[]))

    db = SessionLocal()
    try:
        result = scraper_service.run_scrape(db)
    finally:
        db.close()

    assert result.status == "partial"
    assert result.fetched == 1
    assert result.created == 0
    assert result.message is not None
    assert "No new posts found" in result.message


def test_run_scrape_ingests_blog_crawl_rows_when_enabled(monkeypatch) -> None:
    _clear_scrape_tables()
    _stub_run_record_writes(monkeypatch, run_id="run-blog-crawl")

    cfg = ScraperConfig(
        subreddits=["TwoXIndia"],
        quora_queries=["query"],
        discussion_queries=["forum query"],
        blog_queries=["blog query"],
        forum_domains=["reddit.com"],
        blog_domains=["example.com"],
        max_posts_per_source=50,
        min_score=10,
        run_schedule="0 9 * * 1",
        crawl_full_blog_domains=True,
        blog_crawl_max_urls_per_domain=50,
    )

    monkeypatch.setattr(scraper_service.settings, "reddit_source_mode", "apify")
    monkeypatch.setattr(scraper_service.settings, "allow_fallback_seed_data", False)
    monkeypatch.setattr(scraper_service, "_load_config", lambda: cfg)
    monkeypatch.setattr(scraper_service, "_fetch_reddit_via_apify", lambda _cfg: SourceFetchResult(source="reddit_apify", rows=[], failures=[]))
    monkeypatch.setattr(scraper_service, "_fetch_quora_via_apify", lambda _cfg: SourceFetchResult(source="quora_apify", rows=[], failures=[]))
    monkeypatch.setattr(scraper_service, "_fetch_quora_via_search", lambda _cfg: SourceFetchResult(source="quora_search", rows=[], failures=[]))
    monkeypatch.setattr(scraper_service, "_crawl_forum_domains", lambda _cfg: SourceFetchResult(source="discussion_forums", rows=[], failures=[]))
    monkeypatch.setattr(
        scraper_service,
        "_crawl_blog_domains",
        lambda _cfg: SourceFetchResult(
            source="blog_crawl",
            rows=[
                {
                    "source": "blog_crawl",
                    "title": "Long-form maternity comfort guide",
                    "body": "y" * 400,
                    "score": 0,
                    "url": "https://example.com/blog/deep-guide",
                }
            ],
            failures=[],
        ),
    )

    db = SessionLocal()
    try:
        result = scraper_service.run_scrape(db)
    finally:
        db.close()

    assert result.status == "success"
    assert result.fetched == 1
    assert result.created == 1

    db = SessionLocal()
    try:
        created = db.query(ScrapedPost).filter(ScrapedPost.url == "https://example.com/blog/deep-guide").first()
        insight = db.query(ScrapedInsight).filter(ScrapedInsight.post_id == created.id).first() if created else None
    finally:
        db.close()

    assert created is not None
    assert created.source == "blog_crawl"
    assert insight is not None


def test_run_source_task_with_timeout_returns_failure_for_slow_source() -> None:
    task = scraper_service.SourceFetchTask(
        name="quora",
        timeout_seconds=1,
        fetch_fn=lambda: SourceFetchResult(source="quora_apify", rows=[], failures=[]),
    )

    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(lambda: (time.sleep(2), SourceFetchResult(source="quora_apify", rows=[], failures=[]))[1])
        result = scraper_service._run_source_task_with_timeout(task, future)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    assert result.rows == []
    assert len(result.failures) == 1
    assert "timed out" in result.failures[0]


def test_run_scrape_continues_when_quora_source_fails(monkeypatch) -> None:
    _clear_scrape_tables()
    _stub_run_record_writes(monkeypatch, run_id="run-partial-source-fail")

    cfg = ScraperConfig(
        subreddits=["TwoXIndia"],
        quora_queries=["query"],
        discussion_queries=["forum query"],
        blog_queries=["blog query"],
        forum_domains=["reddit.com"],
        blog_domains=["example.com"],
        max_posts_per_source=50,
        min_score=10,
        run_schedule="0 9 * * 1",
        crawl_full_blog_domains=False,
        blog_crawl_max_urls_per_domain=50,
    )

    monkeypatch.setattr(scraper_service.settings, "reddit_source_mode", "apify")
    monkeypatch.setattr(scraper_service.settings, "allow_fallback_seed_data", False)
    monkeypatch.setattr(scraper_service.settings, "scrape_relevance_min_score", 0)
    monkeypatch.setattr(scraper_service.settings, "scrape_parallel_max_workers", 3)
    monkeypatch.setattr(scraper_service.settings, "scrape_reddit_timeout_seconds", 30.0)
    monkeypatch.setattr(scraper_service.settings, "scrape_quora_timeout_seconds", 30.0)
    monkeypatch.setattr(scraper_service.settings, "scrape_forum_timeout_seconds", 30.0)
    monkeypatch.setattr(scraper_service.settings, "scrape_blog_timeout_seconds", 30.0)
    monkeypatch.setattr(scraper_service, "_load_config", lambda: cfg)

    monkeypatch.setattr(
        scraper_service,
        "_fetch_reddit_via_apify",
        lambda _cfg: SourceFetchResult(
            source="reddit_apify",
            rows=[
                {
                    "source": "reddit",
                    "title": "Resilient source test title",
                    "body": "x" * 220,
                    "score": 22,
                    "url": "https://reddit.com/source-resilience-1",
                }
            ],
            failures=[],
        ),
    )
    monkeypatch.setattr(scraper_service, "_fetch_quora_via_apify", lambda _cfg: (_ for _ in ()).throw(RuntimeError("quora api down")))
    monkeypatch.setattr(scraper_service, "_fetch_quora_via_search", lambda _cfg: SourceFetchResult(source="quora_search", rows=[], failures=[]))
    monkeypatch.setattr(scraper_service, "_crawl_forum_domains", lambda _cfg: SourceFetchResult(source="discussion_forums", rows=[], failures=[]))

    db = SessionLocal()
    try:
        result = scraper_service.run_scrape(db)
    finally:
        db.close()

    assert result.status == "success"
    assert result.created == 1
    assert result.fetched == 1
