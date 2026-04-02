from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.scraped_post import ScrapedPost


def purge_old_scraped_data(db: Session, days: int = 30) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    count = db.query(ScrapedPost).filter(ScrapedPost.scraped_at < cutoff).delete()
    db.commit()
    return count


def run_compliance_maintenance(db: Session) -> int:
    if not settings.compliance_purge_enabled:
        return 0

    return purge_old_scraped_data(db, days=max(1, int(settings.scraped_data_retention_days)))
