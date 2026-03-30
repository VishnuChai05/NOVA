from typing import Literal

from pydantic import BaseModel, Field

LLMProvider = Literal["template", "anthropic", "groq"]


class EngineBaseRequest(BaseModel):
    brief: str = Field(..., min_length=8, max_length=2000)
    target_audience: str = Field(default="Women in India", min_length=2, max_length=200)
    brand_name: str = Field(default="oh so u", min_length=2, max_length=120)
    llm_provider: LLMProvider = "template"


class BlogMakerRequest(EngineBaseRequest):
    seo_focus_keyword: str = Field(default="women innerwear comfort India", min_length=2, max_length=200)


class ScriptGeneratorRequest(EngineBaseRequest):
    campaign_goal: str = Field(default="awareness", min_length=2, max_length=120)


class ProductRangeRequest(EngineBaseRequest):
    current_catalog_summary: str = Field(default="bras, shapewear, panties", min_length=3, max_length=1000)


class EngineResponse(BaseModel):
    engine: str
    title: str
    content: str
    provider_used: LLMProvider
    used_fallback: bool = False
