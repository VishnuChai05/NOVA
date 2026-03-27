from app.db.base import Base
from app.db.session import engine
from app.models import BlogPostIndex, EvaluationResult, GeneratedOutput, PromptTemplate, ScrapeRun, ScrapedPost


def init_db() -> None:
    # Import side effects ensure all model metadata is registered before create_all.
    _ = (BlogPostIndex, EvaluationResult, GeneratedOutput, PromptTemplate, ScrapeRun, ScrapedPost)
    Base.metadata.create_all(bind=engine)
