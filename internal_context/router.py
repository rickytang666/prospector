from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from storage import db

router = APIRouter()


class IngestRequest(BaseModel):
    team_name: str
    org_url: str
    website_url: str | None = None


@router.post("/ingest")
async def ingest(req: IngestRequest):
    # TODO: wire up scraping -> chunking -> embedding -> db
    return {"status": "ok", "team": req.team_name}


@router.get("/chunks/{team_name}")
async def get_chunks(team_name: str):
    chunks = await db.get_chunks(team_name)
    if not chunks:
        raise HTTPException(status_code=404, detail="no chunks found for team")
    return chunks
