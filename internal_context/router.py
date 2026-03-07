import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from storage import db
from internal_context.ingestion.website import scrape_website

router = APIRouter()


class IngestRequest(BaseModel):
    team_name: str
    org_url: str
    urls: list[str] = []  # website, docs, wiki — wtv the team has


@router.post("/ingest")
async def ingest(req: IngestRequest):
    chunks = []

    if req.urls:
        website_chunks = await asyncio.to_thread(scrape_website, req.urls, req.team_name)
        chunks.extend(website_chunks)
        print(f"got {len(website_chunks)} chunks from websites")

    # TODO: github stuff

    if chunks:
        await db.insert_chunks(chunks)

    return {"status": "ok", "team": req.team_name, "chunks_inserted": len(chunks)}


@router.get("/chunks/{team_name}")
async def get_chunks(team_name: str):
    chunks = await db.get_chunks(team_name)
    if not chunks:
        raise HTTPException(status_code=404, detail="no chunks found for team")
    return chunks
