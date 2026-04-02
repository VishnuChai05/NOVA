from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import httpx

from app.db.session import get_db
from app.schemas.blog import BlogCountResponse
from app.services.blog_counter import get_blog_count_summary, refresh_blog_index

router = APIRouter(tags=["blog"])


@router.get("/blog-count", response_model=BlogCountResponse)
def blog_count(db: Session = Depends(get_db)) -> BlogCountResponse:
    summary = get_blog_count_summary(db)
    return BlogCountResponse(**summary)


@router.post("/blog-count/refresh", response_model=BlogCountResponse)
def blog_count_refresh(db: Session = Depends(get_db)) -> BlogCountResponse:
    try:
        refresh_blog_index(db)
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch WordPress posts: {exc}") from exc

    summary = get_blog_count_summary(db)
    return BlogCountResponse(**summary)
