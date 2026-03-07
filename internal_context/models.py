from pydantic import BaseModel
from datetime import datetime


class Chunk(BaseModel):
    id: str | None = None
    team_name: str
    source_type: str  # "github_readme", "github_issue", "website"
    source_url: str | None = None
    content: str
    embedding: list[float] | None = None
    created_at: datetime | None = None
