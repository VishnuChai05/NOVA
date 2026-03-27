import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="success", index=True)
    total_fetched: Mapped[int] = mapped_column(Integer, default=0)
    total_created: Mapped[int] = mapped_column(Integer, default=0)
    source_stats_json: Mapped[str] = mapped_column(Text, default="{}")
    failures_json: Mapped[str] = mapped_column(Text, default="[]")
