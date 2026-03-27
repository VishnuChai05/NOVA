from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.scraped_post import ScrapedPost


def purge_old_scraped_data(db: Session, days: int = 30) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items = db.query(ScrapedPost).filter(ScrapedPost.scraped_at < cutoff).all()
    count = len(items)
    for item in items:
        db.delete(item)
    db.commit()
    return count
