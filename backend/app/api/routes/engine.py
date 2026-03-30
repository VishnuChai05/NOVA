from fastapi import APIRouter

from app.schemas.engine import (
    BlogMakerRequest,
    EngineResponse,
    ProductRangeRequest,
    ScriptGeneratorRequest,
)
from app.services.engine import run_blog_maker, run_product_range_engine, run_script_generator

router = APIRouter(tags=["engine"])


@router.post("/engine/blog-maker", response_model=EngineResponse)
def blog_maker(payload: BlogMakerRequest) -> EngineResponse:
    title, content = run_blog_maker(payload)
    return EngineResponse(engine="blog_maker", title=title, content=content)


@router.post("/engine/script-generator", response_model=EngineResponse)
def script_generator(payload: ScriptGeneratorRequest) -> EngineResponse:
    title, content = run_script_generator(payload)
    return EngineResponse(engine="script_generator", title=title, content=content)


@router.post("/engine/product-range", response_model=EngineResponse)
def product_range(payload: ProductRangeRequest) -> EngineResponse:
    title, content = run_product_range_engine(payload)
    return EngineResponse(engine="product_range", title=title, content=content)
