import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from storage import db
from internal_context.ingestion.website import scrape_website
from internal_context.ingestion.github import scrape_github
from internal_context.embedding.embedder import embed_chunks
from internal_context.extraction.extractor import extract_team_context

router = APIRouter()


class IngestRequest(BaseModel):
    team_name: str
    org_url: str
    urls: list[str] = []  # website, docs, wiki — wtv the team has


@router.post("/ingest")
async def ingest(req: IngestRequest):
    await db.delete_chunks(req.team_name)
    chunks = []

    if req.urls:
        website_chunks = await asyncio.to_thread(scrape_website, req.urls, req.team_name)
        chunks.extend(website_chunks)
        print(f"got {len(website_chunks)} chunks from websites")

    if req.org_url:
        github_chunks = await asyncio.to_thread(scrape_github, req.org_url, req.team_name)
        chunks.extend(github_chunks)
        print(f"got {len(github_chunks)} chunks from github")

    if chunks:
        chunks = await asyncio.to_thread(embed_chunks, chunks)
        await db.insert_chunks(chunks)
        # sanity check
        sample = await db.get_chunks(req.team_name)
        if sample:
            emb = sample[0].get("embedding")
            print(f"sample embedding: {'ok' if emb and len(emb) == 1536 else 'MISSING or wrong size'} (len={len(emb) if emb else 0})")

        ctx = await asyncio.to_thread(extract_team_context, req.team_name, chunks)
        await db.upsert_team_context(ctx)
        print(f"team context: {ctx}")

    return {"status": "ok", "team": req.team_name, "chunks_inserted": len(chunks)}


@router.get("/context/{team_name}")
async def get_context(team_name: str):
    ctx = await db.get_team_context(team_name)
    if not ctx:
        raise HTTPException(status_code=404, detail="no context found for team")
    return ctx


@router.get("/chunks/{team_name}")
async def get_chunks(team_name: str):
    chunks = await db.get_chunks(team_name)
    if not chunks:
        raise HTTPException(status_code=404, detail="no chunks found for team")
    return chunks
