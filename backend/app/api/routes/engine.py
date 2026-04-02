from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_operational_api_key
from app.schemas.engine import (
    BlogMakerRequest,
    EngineResponse,
    ProductRangeRequest,
    ScriptGeneratorRequest,
)
from app.services.engine import run_blog_maker, run_product_range_engine, run_script_generator

router = APIRouter(tags=["engine"], dependencies=[Depends(require_operational_api_key)])


@router.post("/engine/blog-maker", response_model=EngineResponse)
def blog_maker(payload: BlogMakerRequest) -> EngineResponse:
    try:
        title, content, provider_used, used_fallback = run_blog_maker(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EngineResponse(
        engine="blog_maker",
        title=title,
        content=content,
        provider_used=provider_used,
        used_fallback=used_fallback,
    )


@router.post("/engine/script-generator", response_model=EngineResponse)
def script_generator(payload: ScriptGeneratorRequest) -> EngineResponse:
    try:
        title, content, provider_used, used_fallback = run_script_generator(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EngineResponse(
        engine="script_generator",
        title=title,
        content=content,
        provider_used=provider_used,
        used_fallback=used_fallback,
    )


@router.post("/engine/product-range", response_model=EngineResponse)
def product_range(payload: ProductRangeRequest) -> EngineResponse:
    try:
        title, content, provider_used, used_fallback = run_product_range_engine(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EngineResponse(
        engine="product_range",
        title=title,
        content=content,
        provider_used=provider_used,
        used_fallback=used_fallback,
    )
