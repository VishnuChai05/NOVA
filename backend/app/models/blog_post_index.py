import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BlogPostIndex(Base):
    __tablename__ = "blog_post_index"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    source_id: Mapped[str] = mapped_column(String(64), index=True)
