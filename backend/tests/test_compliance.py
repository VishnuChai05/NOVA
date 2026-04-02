from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.settings import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.scraped_post import ScrapedPost
from app.services.compliance import run_compliance_maintenance


def test_compliance_maintenance_purges_only_old_scraped_posts(monkeypatch) -> None:
    init_db()
    monkeypatch.setattr(settings, "compliance_purge_enabled", True)
    monkeypatch.setattr(settings, "scraped_data_retention_days", 30)

    db = SessionLocal()
    try:
        db.query(ScrapedPost).delete(synchronize_session=False)
        db.commit()

        now = datetime.now(timezone.utc)
        old_post = ScrapedPost(
            source="blog_crawl",
            title="Old post",
            body="Old body" * 4,
            score=0,
            url="https://example.com/old-compliance-row",
            scraped_at=now - timedelta(days=60),
            category_tag="other",
        )
        old_url = old_post.url
        recent_post = ScrapedPost(
            source="blog_crawl",
            title="Recent post",
            body="Recent body" * 4,
            score=0,
            url="https://example.com/recent-compliance-row",
            scraped_at=now - timedelta(days=3),
            category_tag="other",
        )
        recent_url = recent_post.url
        db.add(old_post)
        db.add(recent_post)
        db.commit()

        purged = run_compliance_maintenance(db)
        assert purged == 1
        assert db.query(ScrapedPost).filter(ScrapedPost.url == old_url).first() is None
        assert db.query(ScrapedPost).filter(ScrapedPost.url == recent_url).first() is not None
    finally:
        db.close()
