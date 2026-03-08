from pydantic import BaseModel
from datetime import datetime


class Chunk(BaseModel):
    id: str | None = None
    team_name: str
    source_type: str
    source_url: str | None = None
    content: str
    content_hash: str | None = None
    embedding: list[float] | None = None
    created_at: datetime | None = None
