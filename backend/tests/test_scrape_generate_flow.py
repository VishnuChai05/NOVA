from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.routes.scrape as scrape_routes
from app.core.settings import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.scrape_job import ScrapeJob
from app.models.scrape_run import ScrapeRun
from app.models.scraped_post import ScrapedPost
from app.main import app


def _clear_jobs() -> None:
    init_db()
    db = SessionLocal()
    try:
        db.query(ScrapeJob).delete()
        db.commit()
    finally:
        db.close()


def test_scrape_then_generate(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    monkeypatch.setattr(scrape_routes, "enqueue_scrape_job", lambda job_id: "rq-job-1")
    headers = {"X-API-Key": "test-api-key"}
    _clear_jobs()

    db = SessionLocal()
    try:
        db.add(
            ScrapedPost(
                source="reddit",
                title="Mock women product review topic",
                body="Mock body for deterministic integration test",
                score=11,
                url="https://example.com/mock-post",
                scraped_at=datetime.now(timezone.utc),
                category_tag="other",
            )
        )
        db.add(
            ScrapeRun(
                status="success",
                total_fetched=1,
                total_created=1,
                source_stats_json='{"mock": {"fetched": 1, "failed": 0}}',
                failures_json="[]",
                finished_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        scrape = client.post("/api/scrape/run", headers=headers)
        assert scrape.status_code == 202
        assert scrape.json()["job_id"]

        posts = client.get("/api/scraped-posts", headers=headers)
        assert posts.status_code == 200
        payload = posts.json()
        assert len(payload) >= 1

        post_id = payload[0]["id"]
        generated = client.post(
            "/api/generate",
            json={"post_id": post_id, "output_type": "blog"},
            headers=headers,
        )

        assert generated.status_code == 200
        assert generated.json()["type"] == "blog"

        outputs = client.get("/api/outputs", headers=headers)
        assert outputs.status_code == 200
        assert len(outputs.json()) >= 1


def test_scrape_run_returns_409_when_busy(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    headers = {"X-API-Key": "test-api-key"}
    _clear_jobs()

    db = SessionLocal()
    try:
        db.add(ScrapeJob(status="running", progress_pct=20, message="Busy"))
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        scrape = client.post("/api/scrape/run", headers=headers)
        assert scrape.status_code == 409
        assert scrape.json()["detail"] == "A scrape job is already running"
