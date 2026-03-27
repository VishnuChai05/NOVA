from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OutputType = Literal["blog", "reel", "product_idea"]
OutputStatus = Literal["draft", "approved", "rejected", "needs_edit"]


class GenerateRequest(BaseModel):
    post_id: str
    output_type: OutputType


class GenerateResponse(BaseModel):
    output_id: str
    type: OutputType
    title: str
    content: str
    generated_at: datetime
    evaluation_score: float | None = None


class GeneratedOutputOut(BaseModel):
    id: str
    post_id: str
    output_type: str
    title: str
    content: str
    status: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class UpdateStatusRequest(BaseModel):
    status: OutputStatus = Field(..., description="New content status")
