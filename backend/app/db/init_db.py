import logging

from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app.models import (
    BlogPostIndex,
    EvaluationResult,
    GeneratedOutput,
    PromptTemplate,
    ScrapeJob,
    ScrapeRun,
    ScrapedInsight,
    ScrapedPost,
)


logger = logging.getLogger(__name__)


def init_db() -> None:
    # Import side effects ensure all model metadata is registered before create_all.
    _ = (
        BlogPostIndex,
        EvaluationResult,
        GeneratedOutput,
        PromptTemplate,
        ScrapeJob,
        ScrapeRun,
        ScrapedInsight,
        ScrapedPost,
    )
    Base.metadata.create_all(bind=engine)

    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("scraped_posts")}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not inspect scraped_posts schema (may be first run or Postgres): %s", exc)
        return

    if "published_at" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE scraped_posts ADD COLUMN published_at DATETIME"))
