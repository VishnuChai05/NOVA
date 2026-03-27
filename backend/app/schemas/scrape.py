from datetime import datetime

from pydantic import BaseModel


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
