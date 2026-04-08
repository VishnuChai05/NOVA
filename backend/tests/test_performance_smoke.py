from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from time import perf_counter

from fastapi.testclient import TestClient

import app.api.routes.scrape as scrape_routes
from app.core.settings import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.scrape_job import ScrapeJob
from app.models.scraped_post import ScrapedPost


def _headers() -> dict[str, str]:
    return {"X-API-Key": "test-api-key"}


def _seed_post_if_missing(url: str = "https://example.com/perf-topic") -> str:
    db = SessionLocal()
    try:
        row = db.query(ScrapedPost).filter(ScrapedPost.url == url).first()
        if row:
            return row.id

        row = ScrapedPost(
            source="reddit",
            title="Perf smoke source topic",
            body="Performance smoke body content for generate endpoint stability." * 5,
            score=50,
            url=url,
            scraped_at=datetime.now(timezone.utc),
            category_tag="bra",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def test_scrape_endpoint_performance_smoke(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    monkeypatch.setattr(scrape_routes, "enqueue_scrape_job", lambda job_id: "rq-job-1")

    timings: list[float] = []
    with TestClient(app) as client:
        for _ in range(20):
            db = SessionLocal()
            try:
                db.query(ScrapeJob).delete()
                db.commit()
            finally:
                db.close()

            start = perf_counter()
            resp = client.post("/api/scrape/run", headers=_headers())
            timings.append(perf_counter() - start)
            assert resp.status_code == 202

    assert mean(timings) < 0.12


def test_generate_endpoint_performance_smoke(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    post_id = _seed_post_if_missing()

    timings: list[float] = []
    with TestClient(app) as client:
        for _ in range(20):
            start = perf_counter()
            resp = client.post(
                "/api/generate",
                headers=_headers(),
                json={"post_id": post_id, "output_type": "blog"},
            )
            timings.append(perf_counter() - start)
            assert resp.status_code == 200

    assert mean(timings) < 0.2
