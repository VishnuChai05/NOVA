from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.routes.scrape as scrape_routes
from app.core.settings import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.scrape_run import ScrapeRun
from app.models.scraped_post import ScrapedPost
from app.services.scraper import ConcurrentScrapeError, ScrapeExecutionResult


def _headers() -> dict[str, str]:
    return {"X-API-Key": "test-api-key"}


def _clear_data() -> None:
    db = SessionLocal()
    try:
        db.query(ScrapedPost).delete()
        db.query(ScrapeRun).delete()
        db.commit()
    finally:
        db.close()


def test_e2e_happy_path_scrape_to_generate_to_approve(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    _clear_data()

    def fake_run_scrape(db) -> ScrapeExecutionResult:
        url = "https://example.com/e2e-topic"
        created = 0
        if not db.query(ScrapedPost).filter(ScrapedPost.url == url).first():
            db.add(
                ScrapedPost(
                    source="reddit",
                    title="E2E women comfort topic for generation",
                    body="This is a sufficiently long mock body for E2E generation flow." * 5,
                    score=21,
                    url=url,
                    scraped_at=datetime.now(timezone.utc),
                    category_tag="bra",
                )
            )
            created = 1

        db.add(
            ScrapeRun(
                status="success",
                total_fetched=1,
                total_created=created,
                source_stats_json='{"mock": {"fetched": 1, "failed": 0}}',
                failures_json="[]",
                finished_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        return ScrapeExecutionResult(
            run_id="e2e-run-1",
            created=created,
            fetched=1,
            status="success",
            message=None,
        )

    monkeypatch.setattr(scrape_routes, "run_scrape", fake_run_scrape)

    with TestClient(app) as client:
        run_resp = client.post("/api/scrape/run", headers=_headers())
        assert run_resp.status_code == 200
        assert run_resp.json()["status"] == "success"

        posts_resp = client.get("/api/scraped-posts", headers=_headers())
        assert posts_resp.status_code == 200
        posts = posts_resp.json()
        assert len(posts) >= 1

        post_id = posts[0]["id"]
        gen_resp = client.post(
            "/api/generate",
            headers=_headers(),
            json={"post_id": post_id, "output_type": "blog"},
        )
        assert gen_resp.status_code == 200
        output_id = gen_resp.json()["output_id"]

        list_outputs = client.get("/api/outputs", headers=_headers())
        assert list_outputs.status_code == 200
        assert any(row["id"] == output_id for row in list_outputs.json())

        approve_resp = client.patch(
            f"/api/outputs/{output_id}/status",
            headers=_headers(),
            json={"status": "approved"},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "approved"


def test_e2e_failure_path_busy_scrape_and_invalid_generate(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    monkeypatch.setattr(
        scrape_routes,
        "run_scrape",
        lambda db: (_ for _ in ()).throw(ConcurrentScrapeError("Scrape run already in progress")),
    )

    with TestClient(app) as client:
        scrape_resp = client.post("/api/scrape/run", headers=_headers())
        assert scrape_resp.status_code == 409
        assert scrape_resp.json()["detail"] == "Scrape run already in progress"

        generate_resp = client.post(
            "/api/generate",
            headers=_headers(),
            json={"post_id": "missing-post-id", "output_type": "blog"},
        )
        assert generate_resp.status_code == 404
        assert "Post not found" in generate_resp.json()["detail"]
