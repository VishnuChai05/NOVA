from app.db.base import Base
from app.db.session import engine
from app.models import (
    BlogPostIndex,
    EvaluationResult,
    GeneratedOutput,
    PromptTemplate,
    ScrapeRun,
    ScrapedInsight,
    ScrapedPost,
)


def init_db() -> None:
    # Import side effects ensure all model metadata is registered before create_all.
    _ = (BlogPostIndex, EvaluationResult, GeneratedOutput, PromptTemplate, ScrapeRun, ScrapedInsight, ScrapedPost)
    Base.metadata.create_all(bind=engine)
