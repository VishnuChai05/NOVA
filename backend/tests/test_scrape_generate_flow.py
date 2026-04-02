from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.routes.scrape as scrape_routes
from app.core.settings import settings
from app.models.scrape_run import ScrapeRun
from app.models.scraped_post import ScrapedPost
from app.main import app
from app.services.scraper import ConcurrentScrapeError, ScrapeExecutionResult


def test_scrape_then_generate(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    headers = {"X-API-Key": "test-api-key"}

    def fake_run_scrape(db) -> ScrapeExecutionResult:
        created = 0
        url = "https://example.com/mock-post"
        exists = db.query(ScrapedPost).filter(ScrapedPost.url == url).first()
        if not exists:
            db.add(
                ScrapedPost(
                    source="reddit",
                    title="Mock women product review topic",
                    body="Mock body for deterministic integration test",
                    score=11,
                    url=url,
                    scraped_at=datetime.now(timezone.utc),
                    category_tag="other",
                )
            )
            created = 1

        run = ScrapeRun(
            status="success",
            total_fetched=1,
            total_created=created,
            source_stats_json='{"mock": {"fetched": 1, "failed": 0}}',
            failures_json="[]",
            finished_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return ScrapeExecutionResult(run_id=run.id, created=created, fetched=1, status="success")

    monkeypatch.setattr(scrape_routes, "run_scrape", fake_run_scrape)

    with TestClient(app) as client:
        scrape = client.post("/api/scrape/run", headers=headers)
        assert scrape.status_code == 200
        assert scrape.json()["run_id"]

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

    def fake_busy_scrape(db):
        raise ConcurrentScrapeError("Scrape run already in progress")

    monkeypatch.setattr(scrape_routes, "run_scrape", fake_busy_scrape)

    with TestClient(app) as client:
        scrape = client.post("/api/scrape/run", headers=headers)
        assert scrape.status_code == 409
        assert scrape.json()["detail"] == "Scrape run already in progress"
