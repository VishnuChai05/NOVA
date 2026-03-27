import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    output_id: Mapped[str] = mapped_column(String(36), ForeignKey("generated_outputs.id"), index=True)
    evaluator_model: Mapped[str] = mapped_column(String(128))
    score: Mapped[float] = mapped_column(Float)
    rubric_json: Mapped[str] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
