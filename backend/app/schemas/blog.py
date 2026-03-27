from pydantic import BaseModel


class BlogCountResponse(BaseModel):
    total: int
    categories: dict[str, int]
    last_updated: str
    topic_gap_flags: list[str]
