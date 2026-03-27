from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.scraped_post import ScrapedPost
from app.schemas.scrape import ScrapedPostOut, ScrapeRunOut, ScrapeRunResponse
from app.services.scraper import list_scrape_runs, run_scrape

router = APIRouter(tags=["scrape"])


@router.post("/scrape/run", response_model=ScrapeRunResponse)
def trigger_scrape(db: Session = Depends(get_db)) -> ScrapeRunResponse:
    result = run_scrape(db)
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
