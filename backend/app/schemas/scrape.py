from datetime import datetime

from pydantic import BaseModel, Field


class ScrapedPostOut(BaseModel):
    id: str
    source: str
    title: str
    body: str
    score: int
    url: str
    scraped_at: datetime
    processed: bool
    category_tag: str

    model_config = {"from_attributes": True}


class ScrapeRunResponse(BaseModel):
    run_id: str
    created: int
    fetched: int
    status: str


class ScrapeRunOut(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime
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
