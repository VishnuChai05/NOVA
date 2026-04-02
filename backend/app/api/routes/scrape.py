import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_operational_api_key
from app.db.session import get_db
from app.models.evaluation_result import EvaluationResult
from app.models.generated_output import GeneratedOutput
from app.models.scraped_insight import ScrapedInsight
from app.models.scraped_post import ScrapedPost
from app.schemas.scrape import (
    ScraperConfigIn,
    ScraperConfigOut,
    ScrapedInsightOut,
    ScrapedKeywordCandidateOut,
    ScrapedPostOut,
    ScrapeRunOut,
    ScrapeRunResponse,
    ScrapeSchedulerIntervalIn,
    ScrapeSchedulerStatusOut,
)
from app.services.content_validator import derive_template_insight
from app.services.scrape_scheduler import (
    get_scrape_scheduler_status,
    set_scrape_interval_minutes,
    start_continuous_scraper,
    stop_continuous_scraper,
)
from app.services.scraper import ConcurrentScrapeError, list_scrape_runs, run_scrape
from app.services.scraper import ScraperConfig, get_scraper_config, save_scraper_config

router = APIRouter(tags=["scrape"], dependencies=[Depends(require_operational_api_key)])

_KEYWORD_NORMALIZE_RE = re.compile(r"[^a-z0-9\s]+")
_GENERIC_SUGGESTION_HINTS = (
    "myth-vs-fact educational post",
    "myth-vs-fact post",
    "short-form reel",
)


def _to_config_out(cfg: ScraperConfig) -> ScraperConfigOut:
    return ScraperConfigOut(
        subreddits=cfg.subreddits,
        quora_queries=cfg.quora_queries,
        discussion_queries=cfg.discussion_queries,
        blog_queries=cfg.blog_queries,
        forum_domains=cfg.forum_domains,
        blog_domains=cfg.blog_domains,
        max_posts_per_source=cfg.max_posts_per_source,
        min_score=cfg.min_score,
        run_schedule=cfg.run_schedule,
        crawl_full_blog_domains=cfg.crawl_full_blog_domains,
        blog_crawl_max_urls_per_domain=cfg.blog_crawl_max_urls_per_domain,
    )


def _normalize_candidate_keyword(value: str) -> str:
    lowered = value.strip().lower()
    normalized = _KEYWORD_NORMALIZE_RE.sub(" ", lowered)
    return " ".join(normalized.split())


def _extract_suggestions(raw_suggestions: str) -> list[str]:
    try:
        parsed = json.loads(raw_suggestions or "[]")
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    suggestions: list[str] = []
    for item in parsed:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if cleaned:
            suggestions.append(cleaned)
    return suggestions


def _is_generic_insight(topic: str, suggestions: list[str]) -> bool:
    normalized_topic = _normalize_candidate_keyword(topic)

    if not suggestions:
        return not normalized_topic or normalized_topic == "other"

    joined = " ".join(suggestions).lower()
    has_generic_suggestion = any(hint in joined for hint in _GENERIC_SUGGESTION_HINTS)
    if has_generic_suggestion:
        return True

    return not normalized_topic or normalized_topic == "other"


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
        message=result.message,
    )


@router.get("/scraped-posts", response_model=list[ScrapedPostOut])
def list_scraped_posts(
    skip: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ScrapedPostOut]:
    query = db.query(ScrapedPost).order_by(ScrapedPost.scraped_at.desc()).offset(skip)
    if limit is not None:
        query = query.limit(limit)

    rows = query.all()
    return [ScrapedPostOut.model_validate(row) for row in rows]


@router.delete("/scraped-posts/{post_id}")
def delete_scraped_post(post_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    post = db.query(ScrapedPost).filter(ScrapedPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Scraped post not found")

    outputs = db.query(GeneratedOutput).filter(GeneratedOutput.post_id == post_id).all()
    output_ids = [output.id for output in outputs]
    deleted_evaluations = 0
    if output_ids:
        deleted_evaluations = (
            db.query(EvaluationResult)
            .filter(EvaluationResult.output_id.in_(output_ids))
            .delete(synchronize_session=False)
        )
        db.query(GeneratedOutput).filter(GeneratedOutput.post_id == post_id).delete(synchronize_session=False)

    deleted_insights = (
        db.query(ScrapedInsight)
        .filter(ScrapedInsight.post_id == post_id)
        .delete(synchronize_session=False)
    )
    db.delete(post)
    db.commit()

    return {
        "deleted": True,
        "post_id": post_id,
        "deleted_insights": deleted_insights,
        "deleted_outputs": len(output_ids),
        "deleted_evaluations": deleted_evaluations,
    }


@router.get("/scraped-insights", response_model=list[ScrapedInsightOut])
def list_scraped_insights(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[ScrapedInsightOut]:
    rows = db.query(ScrapedInsight).order_by(ScrapedInsight.created_at.desc()).all()
    if not rows:
        return []

    post_ids = [row.post_id for row in rows]
    posts = db.query(ScrapedPost).filter(ScrapedPost.id.in_(post_ids)).all()
    post_map = {post.id: post for post in posts}

    deduped: dict[str, ScrapedInsightOut] = {}
    for row in rows:
        suggestions = _extract_suggestions(row.suggestions_json)
        primary_topic = row.primary_topic
        confidence = float(row.confidence or 0.0)
        rationale = row.rationale

        if _is_generic_insight(row.primary_topic, suggestions):
            post = post_map.get(row.post_id)
            if post:
                topic, derived_confidence, derived_suggestions, derived_rationale = derive_template_insight(post)
                primary_topic = topic
                suggestions = derived_suggestions
                confidence = max(confidence, float(derived_confidence))
                rationale = derived_rationale or rationale

        dedupe_key = f"{_normalize_candidate_keyword(primary_topic)}|{_normalize_candidate_keyword(suggestions[0] if suggestions else '')}"
        insight_out = ScrapedInsightOut(
            id=row.id,
            post_id=row.post_id,
            provider_used=row.provider_used,
            model_used=row.model_used,
            confidence=confidence,
            primary_topic=primary_topic,
            suggestions_json=json.dumps(suggestions),
            rationale=rationale,
            created_at=row.created_at,
        )

        current = deduped.get(dedupe_key)
        if current is None or insight_out.confidence > current.confidence:
            deduped[dedupe_key] = insight_out

    ranked = sorted(deduped.values(), key=lambda row: (row.confidence, row.created_at), reverse=True)
    return ranked[skip : skip + limit]


@router.get("/scraped-keyword-candidates", response_model=list[ScrapedKeywordCandidateOut])
def list_scraped_keyword_candidates(
    limit: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[ScrapedKeywordCandidateOut]:
    rows = db.query(ScrapedInsight).order_by(ScrapedInsight.created_at.desc()).all()
    aggregate: dict[str, dict[str, object]] = {}

    for row in rows:
        normalized_topic = _normalize_candidate_keyword(row.primary_topic)
        source_topic = normalized_topic or "other"
        suggestion_values = _extract_suggestions(row.suggestions_json)
        candidate_keywords: dict[str, str | None] = {}

        if normalized_topic and normalized_topic != "other":
            candidate_keywords[normalized_topic] = suggestion_values[0] if suggestion_values else None

        for suggestion in suggestion_values[:3]:
            normalized_suggestion = _normalize_candidate_keyword(suggestion)
            if not normalized_suggestion:
                continue
            if len(normalized_suggestion.split()) > 6:
                normalized_suggestion = " ".join(normalized_suggestion.split()[:6])
            candidate_keywords[normalized_suggestion] = suggestion

        for keyword, sample in candidate_keywords.items():
            entry = aggregate.setdefault(
                keyword,
                {
                    "keyword": keyword,
                    "appearances": 0,
                    "confidence_sum": 0.0,
                    "source_topics": set(),
                    "sample_suggestion": None,
                },
            )
            entry["appearances"] = int(entry["appearances"]) + 1
            entry["confidence_sum"] = float(entry["confidence_sum"]) + float(row.confidence or 0.0)
            cast_topics = entry["source_topics"]
            if isinstance(cast_topics, set):
                cast_topics.add(source_topic)
            if sample and not entry["sample_suggestion"]:
                entry["sample_suggestion"] = sample

    candidates: list[ScrapedKeywordCandidateOut] = []
    for item in aggregate.values():
        appearances = int(item["appearances"])
        confidence_sum = float(item["confidence_sum"])
        source_topics = item["source_topics"]
        sample_suggestion = item["sample_suggestion"]
        candidates.append(
            ScrapedKeywordCandidateOut(
                keyword=str(item["keyword"]),
                appearances=appearances,
                avg_confidence=round(confidence_sum / appearances, 3) if appearances else 0.0,
                source_topics=sorted(source_topics) if isinstance(source_topics, set) else [],
                sample_suggestion=str(sample_suggestion) if sample_suggestion else None,
            )
        )

    candidates.sort(key=lambda item: (-item.appearances, -item.avg_confidence, item.keyword))
    return candidates[:limit]


@router.get("/scrape/runs", response_model=list[ScrapeRunOut])
def get_scrape_runs(
    skip: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ScrapeRunOut]:
    rows = list_scrape_runs(db)
    if limit is not None:
        rows = rows[skip : skip + limit]
    else:
        rows = rows[skip:]
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


@router.get("/scrape/config", response_model=ScraperConfigOut)
def get_config() -> ScraperConfigOut:
    return _to_config_out(get_scraper_config())


@router.put("/scrape/config", response_model=ScraperConfigOut)
def update_config(payload: ScraperConfigIn) -> ScraperConfigOut:
    cfg = ScraperConfig(
        subreddits=payload.subreddits,
        quora_queries=payload.quora_queries,
        discussion_queries=payload.discussion_queries,
        blog_queries=payload.blog_queries,
        forum_domains=payload.forum_domains,
        blog_domains=payload.blog_domains,
        max_posts_per_source=payload.max_posts_per_source,
        min_score=payload.min_score,
        run_schedule=payload.run_schedule,
        crawl_full_blog_domains=payload.crawl_full_blog_domains,
        blog_crawl_max_urls_per_domain=payload.blog_crawl_max_urls_per_domain,
    )
    updated = save_scraper_config(cfg)
    return _to_config_out(updated)
