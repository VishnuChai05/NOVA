from __future__ import annotations

from fastapi.testclient import TestClient

import app.api.routes.scrape as scrape_routes
from app.core.settings import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.main import app
from app.models.scrape_job import ScrapeJob


def _headers() -> dict[str, str]:
    return {"X-API-Key": "test-api-key"}


def test_scrape_run_returns_job_id_immediately(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    monkeypatch.setattr(scrape_routes, "enqueue_scrape_job", lambda job_id: "rq-job-1")

    init_db()
    db = SessionLocal()
    try:
        db.query(ScrapeJob).delete()
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.post("/api/scrape/run", headers=_headers())
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"
        assert isinstance(body["job_id"], str) and body["job_id"]


def test_scrape_status_returns_progress(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    init_db()
    db = SessionLocal()
    try:
        db.query(ScrapeJob).delete()
        db.commit()

        job = ScrapeJob(status="running", progress_pct=45, message="Fetching Reddit posts...")
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/scrape/status/{job_id}", headers=_headers())
        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == job_id
        assert body["status"] == "running"
        assert body["progress_pct"] == 45
        assert body["message"] == "Fetching Reddit posts..."
        assert body["result"] is None


def test_scrape_status_404_for_unknown_job(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    with TestClient(app) as client:
        response = client.get("/api/scrape/status/does-not-exist", headers=_headers())
        assert response.status_code == 404


def test_scrape_status_active_returns_current_job(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")

    init_db()
    db = SessionLocal()
    try:
        db.query(ScrapeJob).delete()
        db.commit()

        job = ScrapeJob(status="running", progress_pct=62, message="Crawling blogs...")
        db.add(job)
        db.commit()
        db.refresh(job)
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/api/scrape/status/current", headers=_headers())
        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == job.id
        assert body["status"] == "running"
        assert body["progress_pct"] == 62
