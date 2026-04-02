from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

import app.api.routes.scrape as scrape_routes
from app.core.settings import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.main import app
from app.models.evaluation_result import EvaluationResult
from app.models.generated_output import GeneratedOutput
from app.models.scraped_insight import ScrapedInsight
from app.models.scraped_post import ScrapedPost
from app.services.scraper import ScrapeExecutionResult, ScraperConfig



def _headers() -> dict[str, str]:
    return {"X-API-Key": "test-api-key"}


def test_scrape_endpoints_require_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    with TestClient(app) as client:
        response = client.get("/api/scraped-posts")
        assert response.status_code == 401


def test_scrape_config_get_put_roundtrip(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    monkeypatch.setattr(settings, "scraper_config_path", str(tmp_path / "cfg.yaml"))

    payload = {
        "subreddits": ["TwoXIndia", "ABraThatFits"],
        "quora_queries": ["women comfort"],
        "discussion_queries": ["forum comfort"],
        "blog_queries": ["blog comfort"],
        "forum_domains": ["reddit.com"],
        "blog_domains": ["example.com"],
        "max_posts_per_source": 33,
        "min_score": 7,
        "run_schedule": "0 9 * * 1",
        "crawl_full_blog_domains": True,
        "blog_crawl_max_urls_per_domain": 120,
    }

    with TestClient(app) as client:
        before = client.get("/api/scrape/config", headers=_headers())
        assert before.status_code == 200
        assert "subreddits" in before.json()

        updated = client.put("/api/scrape/config", json=payload, headers=_headers())
        assert updated.status_code == 200
        assert updated.json() == payload

        after = client.get("/api/scrape/config", headers=_headers())
        assert after.status_code == 200
        assert after.json() == payload


def test_scrape_config_validation_is_strict(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    invalid_payload = {
        "subreddits": [],
        "quora_queries": ["q"],
        "discussion_queries": ["d"],
        "blog_queries": ["b"],
        "forum_domains": ["reddit.com"],
        "blog_domains": ["example.com"],
        "max_posts_per_source": 1,
        "min_score": -1,
        "run_schedule": "x",
        "crawl_full_blog_domains": True,
        "blog_crawl_max_urls_per_domain": 5,
    }

    with TestClient(app) as client:
        response = client.put("/api/scrape/config", json=invalid_payload, headers=_headers())
        assert response.status_code == 422


def test_trigger_scrape_response_contract_includes_message(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    fake = ScrapeExecutionResult(
        run_id="run-123",
        created=0,
        fetched=0,
        status="partial",
        message="No posts found. Try adjusting your queries or domains in Settings.",
    )
    monkeypatch.setattr(scrape_routes, "run_scrape", lambda db: fake)

    with TestClient(app) as client:
        response = client.post("/api/scrape/run", headers=_headers())
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"run_id", "created", "fetched", "status", "message"}
        assert body["message"] == fake.message


def test_scheduler_endpoints_and_interval_validation(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    state = {
        "running": False,
        "interval_minutes": 60,
        "last_run_started_at": None,
        "last_run_finished_at": None,
        "last_run_status": None,
    }

    def fake_status():
        return dict(state)

    def fake_start():
        state["running"] = True

    def fake_stop():
        state["running"] = False

    def fake_interval(minutes: int):
        state["interval_minutes"] = minutes

    monkeypatch.setattr(scrape_routes, "get_scrape_scheduler_status", fake_status)
    monkeypatch.setattr(scrape_routes, "start_continuous_scraper", fake_start)
    monkeypatch.setattr(scrape_routes, "stop_continuous_scraper", fake_stop)
    monkeypatch.setattr(scrape_routes, "set_scrape_interval_minutes", fake_interval)

    with TestClient(app) as client:
        start = client.post("/api/scrape/scheduler/start", headers=_headers())
        assert start.status_code == 200
        assert start.json()["running"] is True

        interval = client.post(
            "/api/scrape/scheduler/interval",
            json={"interval_minutes": 45},
            headers=_headers(),
        )
        assert interval.status_code == 200
        assert interval.json()["interval_minutes"] == 45

        invalid_interval = client.post(
            "/api/scrape/scheduler/interval",
            json={"interval_minutes": 3},
            headers=_headers(),
        )
        assert invalid_interval.status_code == 422

        stop = client.post("/api/scrape/scheduler/stop", headers=_headers())
        assert stop.status_code == 200
        assert stop.json()["running"] is False


def test_scrape_runs_allows_null_finished_at(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    run_obj = SimpleNamespace(
        id="run-null-finish",
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        status="running",
        total_fetched=0,
        total_created=0,
        source_stats_json="{}",
        failures_json="[]",
    )
    monkeypatch.setattr(scrape_routes, "list_scrape_runs", lambda db: [run_obj])

    with TestClient(app) as client:
        response = client.get("/api/scrape/runs", headers=_headers())
        assert response.status_code == 200
        body = response.json()
        assert len(body) >= 1
        assert body[0]["finished_at"] is None


def test_scraped_insights_endpoint_returns_rows(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    init_db()
    db = SessionLocal()
    try:
        post = ScrapedPost(
            source="blog_crawl",
            title="Insights endpoint seed",
            body="Seed body for insights endpoint validation." * 4,
            score=0,
            url=f"https://example.com/insights-seed-{uuid4().hex}",
            scraped_at=datetime.now(timezone.utc),
            category_tag="other",
        )
        db.add(post)
        db.flush()
        db.add(
            ScrapedInsight(
                post_id=post.id,
                provider_used="template",
                model_used="template",
                confidence=0.6,
                primary_topic="other",
                suggestions_json='["Draft a topic cluster"]',
                rationale="Seed rationale",
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/api/scraped-insights", headers=_headers())
        assert response.status_code == 200
        rows = response.json()
        assert any(row["provider_used"] == "template" for row in rows)


def test_scraped_insights_endpoint_deduplicates_and_enriches_generic_rows(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    init_db()
    db = SessionLocal()
    try:
        post_one = ScrapedPost(
            source="blog_crawl",
            title="Bra strap pain and cup fit confusion",
            body="Need support without shoulder pain and digging straps." * 4,
            score=0,
            url=f"https://example.com/enrich-one-{uuid4().hex}",
            scraped_at=datetime.now(timezone.utc),
            category_tag="bra",
        )
        post_two = ScrapedPost(
            source="blog_crawl",
            title="Best breathable innerwear for humid days",
            body="Heat and sweat discomfort while choosing daily bra options." * 4,
            score=0,
            url=f"https://example.com/enrich-two-{uuid4().hex}",
            scraped_at=datetime.now(timezone.utc),
            category_tag="bra",
        )
        db.add(post_one)
        db.add(post_two)
        db.flush()

        repeated_generic = '["Create a myth-vs-fact educational post around this pain point."]'
        db.add(
            ScrapedInsight(
                post_id=post_one.id,
                provider_used="template",
                model_used="template",
                confidence=0.55,
                primary_topic="bra",
                suggestions_json=repeated_generic,
                rationale="Generic rationale one",
            )
        )
        db.add(
            ScrapedInsight(
                post_id=post_two.id,
                provider_used="template",
                model_used="template",
                confidence=0.55,
                primary_topic="other",
                suggestions_json=repeated_generic,
                rationale="Generic rationale two",
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/api/scraped-insights", headers=_headers())
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) >= 1

        normalized_topics = {row["primary_topic"] for row in rows}
        assert any(topic != "other" for topic in normalized_topics)
        assert any("bra" in topic.lower() for topic in normalized_topics)
        first_suggestions = [row["suggestions_json"] for row in rows]
        assert not all("educational post around this pain point" in text for text in first_suggestions)


def test_scraped_keyword_candidates_endpoint_returns_ranked_aggregates(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    init_db()
    db = SessionLocal()
    try:
        post_one = ScrapedPost(
            source="blog_crawl",
            title="Keyword candidate seed one",
            body="Seed body one for candidate aggregation." * 4,
            score=0,
            url=f"https://example.com/candidate-one-{uuid4().hex}",
            scraped_at=datetime.now(timezone.utc),
            category_tag="other",
        )
        post_two = ScrapedPost(
            source="blog_crawl",
            title="Keyword candidate seed two",
            body="Seed body two for candidate aggregation." * 4,
            score=0,
            url=f"https://example.com/candidate-two-{uuid4().hex}",
            scraped_at=datetime.now(timezone.utc),
            category_tag="other",
        )
        db.add(post_one)
        db.add(post_two)
        db.flush()

        db.add(
            ScrapedInsight(
                post_id=post_one.id,
                provider_used="template",
                model_used="template",
                confidence=0.8,
                primary_topic="wirefree support",
                suggestions_json='["wirefree support", "soft cup fit"]',
                rationale="Seed rationale one",
            )
        )
        db.add(
            ScrapedInsight(
                post_id=post_two.id,
                provider_used="template",
                model_used="template",
                confidence=0.6,
                primary_topic="wirefree support",
                suggestions_json='["wirefree support", "seamless comfort"]',
                rationale="Seed rationale two",
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/api/scraped-keyword-candidates?limit=10", headers=_headers())
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) >= 1

        wirefree = next((row for row in rows if row["keyword"] == "wirefree support"), None)
        assert wirefree is not None
        assert wirefree["appearances"] >= 2
        assert wirefree["avg_confidence"] >= 0.69
        assert "wirefree support" in wirefree["source_topics"]


def test_delete_scraped_post_cascades_related_rows(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    init_db()
    db = SessionLocal()
    post_id = ""
    output_id = ""
    try:
        post = ScrapedPost(
            source="blog_crawl",
            title="Delete candidate row",
            body="Body text to support delete cascade checks." * 4,
            score=0,
            url=f"https://example.com/delete-candidate-{uuid4().hex}",
            scraped_at=datetime.now(timezone.utc),
            category_tag="other",
        )
        db.add(post)
        db.flush()
        post_id = post.id

        insight = ScrapedInsight(
            post_id=post.id,
            provider_used="template",
            model_used="template",
            confidence=0.7,
            primary_topic="comfort",
            suggestions_json='["test suggestion"]',
            rationale="test rationale",
        )
        db.add(insight)
        db.flush()

        output = GeneratedOutput(
            post_id=post.id,
            output_type="blog",
            title="Generated row",
            content="Generated content",
            status="draft",
            generated_at=datetime.now(timezone.utc),
        )
        db.add(output)
        db.flush()
        output_id = output.id

        db.add(
            EvaluationResult(
                output_id=output.id,
                evaluator_model="test",
                score=0.8,
                rubric_json='{"ok": true}',
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.delete(f"/api/scraped-posts/{post_id}", headers=_headers())
        assert response.status_code == 200
        payload = response.json()
        assert payload["deleted"] is True
        assert payload["post_id"] == post_id

    db = SessionLocal()
    try:
        assert db.query(ScrapedPost).filter(ScrapedPost.id == post_id).first() is None
        assert db.query(ScrapedInsight).filter(ScrapedInsight.post_id == post_id).count() == 0
        assert db.query(GeneratedOutput).filter(GeneratedOutput.id == output_id).first() is None
        assert db.query(EvaluationResult).filter(EvaluationResult.output_id == output_id).count() == 0
    finally:
        db.close()
