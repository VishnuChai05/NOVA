from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.main import app
from app.models.evaluation_result import EvaluationResult
from app.models.generated_output import GeneratedOutput
from app.models.scrape_run import ScrapeRun
from app.models.scraped_insight import ScrapedInsight
from app.models.scraped_post import ScrapedPost


def _headers() -> dict[str, str]:
    return {"X-API-Key": "test-api-key"}


def _seed_list_data() -> None:
    init_db()
    db = SessionLocal()
    try:
        db.query(EvaluationResult).delete(synchronize_session=False)
        db.query(GeneratedOutput).delete(synchronize_session=False)
        db.query(ScrapedInsight).delete(synchronize_session=False)
        db.query(ScrapeRun).delete(synchronize_session=False)
        db.query(ScrapedPost).delete(synchronize_session=False)
        db.commit()

        base_time = datetime.now(timezone.utc)
        posts: list[ScrapedPost] = []
        for index in range(3):
            post = ScrapedPost(
                source="blog_crawl",
                title=f"Pagination post {index + 1}",
                body=("Pagination body text for testing list endpoints." * 4),
                score=0,
                url=f"https://example.com/pagination-post-{index}-{uuid4().hex}",
                scraped_at=base_time - timedelta(minutes=index),
                category_tag="bra",
            )
            db.add(post)
            posts.append(post)
        db.flush()

        for index, post in enumerate(posts):
            db.add(
                GeneratedOutput(
                    post_id=post.id,
                    output_type="blog",
                    title=f"Pagination output {index + 1}",
                    content="Generated content for pagination tests.",
                    status="draft",
                    generated_at=base_time - timedelta(minutes=index),
                )
            )
            db.add(
                ScrapeRun(
                    status="success",
                    total_fetched=index + 1,
                    total_created=index + 1,
                    source_stats_json="{}",
                    failures_json="[]",
                    started_at=base_time - timedelta(minutes=index),
                    finished_at=base_time - timedelta(minutes=index),
                )
            )
            db.add(
                ScrapedInsight(
                    post_id=post.id,
                    provider_used="template",
                    model_used="template",
                    confidence=0.5 + (index * 0.1),
                    primary_topic=f"topic {index + 1}",
                    suggestions_json=f'["Suggestion {index + 1}"]',
                    rationale=f"Rationale {index + 1}",
                    created_at=base_time - timedelta(minutes=index),
                )
            )

        db.commit()
    finally:
        db.close()


def test_list_endpoints_support_skip_and_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    _seed_list_data()

    with TestClient(app) as client:
        posts_resp = client.get("/api/scraped-posts?skip=1&limit=1", headers=_headers())
        assert posts_resp.status_code == 200
        posts = posts_resp.json()
        assert len(posts) == 1
        assert posts[0]["title"] == "Pagination post 2"

        outputs_resp = client.get("/api/outputs?skip=1&limit=1", headers=_headers())
        assert outputs_resp.status_code == 200
        outputs = outputs_resp.json()
        assert len(outputs) == 1
        assert outputs[0]["title"] == "Pagination output 2"

        runs_resp = client.get("/api/scrape/runs?skip=1&limit=1", headers=_headers())
        assert runs_resp.status_code == 200
        runs = runs_resp.json()
        assert len(runs) == 1
        assert runs[0]["total_created"] == 2


def test_scraped_insights_support_skip_and_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    _seed_list_data()

    with TestClient(app) as client:
        response = client.get("/api/scraped-insights?skip=1&limit=1", headers=_headers())
        assert response.status_code == 200
        insights = response.json()
        assert len(insights) == 1
        assert insights[0]["primary_topic"] == "topic 2"


def test_delete_output_removes_output_and_evaluations(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "operational_api_key", "test-api-key")
    _seed_list_data()

    db = SessionLocal()
    try:
        output = db.query(GeneratedOutput).order_by(GeneratedOutput.generated_at.desc()).first()
        assert output is not None
        output_id = output.id

        db.add(
            EvaluationResult(
                output_id=output_id,
                evaluator_model="test-model",
                score=0.82,
                rubric_json='{"quality": true}',
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.delete(f"/api/outputs/{output_id}", headers=_headers())
        assert response.status_code == 200
        payload = response.json()
        assert payload["deleted"] is True
        assert payload["output_id"] == output_id
        assert payload["deleted_evaluations"] == 1

    db = SessionLocal()
    try:
        assert db.query(GeneratedOutput).filter(GeneratedOutput.id == output_id).first() is None
        assert db.query(EvaluationResult).filter(EvaluationResult.output_id == output_id).count() == 0
    finally:
        db.close()
