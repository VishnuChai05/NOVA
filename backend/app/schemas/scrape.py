from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScrapedPostOut(BaseModel):
    id: str
    source: str
    title: str
    body: str
    score: int
    url: str
    published_at: datetime | None = None
    scraped_at: datetime
    processed: bool
    category_tag: str

    model_config = {"from_attributes": True}


class ScrapedInsightOut(BaseModel):
    id: str
    post_id: str
    provider_used: str
    model_used: str
    confidence: float
    primary_topic: str
    suggestions_json: str
    rationale: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ScrapedKeywordCandidateOut(BaseModel):
    keyword: str
    appearances: int
    avg_confidence: float
    source_topics: list[str]
    sample_suggestion: str | None = None


class ScrapeRunResponse(BaseModel):
    run_id: str
    created: int
    fetched: int
    status: str
    message: str | None = None


class ScrapeJobRunAcceptedOut(BaseModel):
    job_id: str
    status: str
    source_type: str


class ScrapeJobStatusOut(BaseModel):
    job_id: str
    status: str
    source_type: str
    progress_pct: int
    message: str | None = None
    result: dict | None = None


class ScrapeRunOut(BaseModel):
    id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    total_fetched: int
    total_created: int
    source_stats_json: str
    failures_json: str

    model_config = {"from_attributes": True}


class ScrapeSchedulerStatusOut(BaseModel):
    running: bool
    interval_minutes: int
    last_run_started_at: datetime | None = None
    last_run_finished_at: datetime | None = None
    last_run_status: str | None = None


class ScrapeSchedulerIntervalIn(BaseModel):
    interval_minutes: int = Field(ge=5, le=1440)


class ScraperConfigOut(BaseModel):
    subreddits: list[str]
    quora_queries: list[str]
    discussion_queries: list[str]
    blog_queries: list[str]
    forum_domains: list[str]
    blog_domains: list[str]
    max_posts_per_source: int
    min_score: int
    run_schedule: str
    crawl_full_blog_domains: bool
    blog_crawl_max_urls_per_domain: int


class ScraperConfigIn(BaseModel):
    subreddits: list[str] = Field(min_length=1)
    quora_queries: list[str] = Field(min_length=1)
    discussion_queries: list[str] = Field(min_length=1)
    blog_queries: list[str] = Field(min_length=1)
    forum_domains: list[str] = Field(min_length=1)
    blog_domains: list[str] = Field(min_length=1)
    max_posts_per_source: int = Field(ge=5, le=500)
    min_score: int = Field(ge=0, le=5000)
    run_schedule: str = Field(min_length=3, max_length=100)
    crawl_full_blog_domains: bool = True
    blog_crawl_max_urls_per_domain: int = Field(ge=10, le=2000)
