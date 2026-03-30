from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_operational_api_key
from app.db.session import get_db
from app.models.scraped_post import ScrapedPost
from app.schemas.scrape import (
    ScrapedPostOut,
    ScrapeRunOut,
    ScrapeRunResponse,
    ScrapeSchedulerIntervalIn,
    ScrapeSchedulerStatusOut,
)
from app.services.scrape_scheduler import (
    get_scrape_scheduler_status,
    set_scrape_interval_minutes,
    start_continuous_scraper,
    stop_continuous_scraper,
)
from app.services.scraper import ConcurrentScrapeError, list_scrape_runs, run_scrape

router = APIRouter(tags=["scrape"], dependencies=[Depends(require_operational_api_key)])


@router.post("/scrape/run", response_model=ScrapeRunResponse)
def trigger_scrape(db: Session = Depends(get_db)) -> ScrapeRunResponse:
    try:
        result = run_scrape(db)
    except ConcurrentScrapeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return ScrapeRunResponse(
        run_id=result.run_id,
        created=result.created,
        fetched=result.fetched,
        status=result.status,
    )


@router.get("/scraped-posts", response_model=list[ScrapedPostOut])
def list_scraped_posts(db: Session = Depends(get_db)) -> list[ScrapedPostOut]:
    rows = db.query(ScrapedPost).order_by(ScrapedPost.scraped_at.desc()).all()
    return [ScrapedPostOut.model_validate(row) for row in rows]


@router.get("/scrape/runs", response_model=list[ScrapeRunOut])
def get_scrape_runs(db: Session = Depends(get_db)) -> list[ScrapeRunOut]:
    rows = list_scrape_runs(db)
    return [ScrapeRunOut.model_validate(row) for row in rows]


@router.get("/scrape/scheduler", response_model=ScrapeSchedulerStatusOut)
def get_scheduler_status() -> ScrapeSchedulerStatusOut:
    return ScrapeSchedulerStatusOut.model_validate(get_scrape_scheduler_status())


@router.post("/scrape/scheduler/start", response_model=ScrapeSchedulerStatusOut)
def start_scheduler() -> ScrapeSchedulerStatusOut:
    start_continuous_scraper()
    return ScrapeSchedulerStatusOut.model_validate(get_scrape_scheduler_status())


@router.post("/scrape/scheduler/stop", response_model=ScrapeSchedulerStatusOut)
def stop_scheduler() -> ScrapeSchedulerStatusOut:
    stop_continuous_scraper()
    return ScrapeSchedulerStatusOut.model_validate(get_scrape_scheduler_status())


@router.post("/scrape/scheduler/interval", response_model=ScrapeSchedulerStatusOut)
def set_scheduler_interval(payload: ScrapeSchedulerIntervalIn) -> ScrapeSchedulerStatusOut:
    set_scrape_interval_minutes(payload.interval_minutes)
    return ScrapeSchedulerStatusOut.model_validate(get_scrape_scheduler_status())
