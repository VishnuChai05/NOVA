import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScrapedInsight(Base):
    __tablename__ = "scraped_insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("scraped_posts.id"), index=True)
    provider_used: Mapped[str] = mapped_column(String(32), default="template")
    model_used: Mapped[str] = mapped_column(String(128), default="template")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    primary_topic: Mapped[str] = mapped_column(String(120), default="other", index=True)
    suggestions_json: Mapped[str] = mapped_column(Text, default="[]")
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
