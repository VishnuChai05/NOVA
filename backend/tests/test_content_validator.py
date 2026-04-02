from __future__ import annotations

import json
from datetime import datetime, timezone

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.scraped_insight import ScrapedInsight
from app.models.scraped_post import ScrapedPost
from app.services.content_validator import create_post_insight


def _seed_post(url: str) -> ScrapedPost:
    db = SessionLocal()
    try:
        post = db.query(ScrapedPost).filter(ScrapedPost.url == url).first()
        if post:
            return post
        post = ScrapedPost(
            source="blog_crawl",
            title="How to choose comfortable bras for long office days",
            body=(
                "Women report pain points around strap digging, sweat discomfort, and support mismatch. "
                "This article explains fit diagnostics, breathable fabrics, and practical purchase criteria."
            )
            * 4,
            score=0,
            url=url,
            scraped_at=datetime.now(timezone.utc),
            category_tag="bra",
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        return post
    finally:
        db.close()


def test_create_post_insight_stores_suggestions(monkeypatch) -> None:
    init_db()
    monkeypatch.setattr("app.services.content_validator.settings.insight_validator_provider", "template")

    url = "https://example.com/validator-seed"
    post = _seed_post(url)

    db = SessionLocal()
    try:
        refreshed = db.query(ScrapedPost).filter(ScrapedPost.id == post.id).first()
        assert refreshed is not None
        insight = create_post_insight(db, refreshed)
        db.commit()
        db.refresh(insight)

        assert insight.post_id == refreshed.id
        assert insight.provider_used == "template"
        assert insight.primary_topic
        assert insight.primary_topic != "other"
        assert 0.5 <= insight.confidence <= 0.9
        assert insight.suggestions_json.startswith("[")
    finally:
        db.close()


def test_create_post_insight_is_idempotent(monkeypatch) -> None:
    init_db()
    monkeypatch.setattr("app.services.content_validator.settings.insight_validator_provider", "template")

    url = "https://example.com/validator-idempotent"
    post = _seed_post(url)

    db = SessionLocal()
    try:
        refreshed = db.query(ScrapedPost).filter(ScrapedPost.id == post.id).first()
        assert refreshed is not None
        first = create_post_insight(db, refreshed)
        second = create_post_insight(db, refreshed)
        db.commit()

        count = db.query(ScrapedInsight).filter(ScrapedInsight.post_id == refreshed.id).count()
        assert first.id == second.id
        assert count == 1
    finally:
        db.close()


def test_create_post_insight_uses_groq_when_available(monkeypatch) -> None:
    init_db()
    monkeypatch.setattr("app.services.content_validator.settings.insight_validator_provider", "groq")
    monkeypatch.setattr("app.services.content_validator.settings.groq_api_key", "test-groq-key")
    monkeypatch.setattr("app.services.content_validator.settings.groq_model", "test-groq-model")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"primary_topic":"groq comfort insights","confidence":0.91,'
                                '"suggestions":["First Groq idea","Second Groq idea"],'
                                '"rationale":"Groq returned structured suggestions"}'
                            )
                        }
                    }
                ]
            }

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def post(self, url, headers=None, json=None):
            assert "groq" in url
            return FakeResponse()

    monkeypatch.setattr("app.services.content_validator.httpx.Client", lambda timeout=30: FakeClient())

    url = "https://example.com/validator-groq"
    post = _seed_post(url)

    db = SessionLocal()
    try:
        refreshed = db.query(ScrapedPost).filter(ScrapedPost.id == post.id).first()
        assert refreshed is not None

        insight = create_post_insight(db, refreshed)
        db.commit()
        db.refresh(insight)

        assert insight.provider_used == "groq"
        assert insight.primary_topic == "groq comfort insights"
        assert insight.confidence == 0.91
        assert json.loads(insight.suggestions_json) == ["First Groq idea", "Second Groq idea"]
    finally:
        db.close()
