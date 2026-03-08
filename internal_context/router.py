import asyncio
import hashlib
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from rate_limit import limiter
from storage import db
from internal_context.ingestion.website import scrape_website
from internal_context.ingestion.github import scrape_github
from internal_context.ingestion.discord_ingestion import fetch_channel_chunks
from internal_context.ingestion.notion import scrape_notion
from internal_context.ingestion.confluence import scrape_confluence
from internal_context.embedding.embedder import embed_chunks
from internal_context.extraction.extractor import extract_team_context

router = APIRouter()


class IngestRequest(BaseModel):
    team_name: str
    org_url: str
    urls: list[str] = []  # website, docs, wiki — wtv the team has
    discord_channel_ids: list[int] = []  # team picks which channels to ingest
    notion_urls: list[str] = []
    confluence_urls: list[str] = []


@router.post("/ingest")
@limiter.limit("15/minute")
async def ingest(request: Request, req: IngestRequest):
    chunks = []
    ctx = None

    if req.urls:
        website_chunks = await asyncio.to_thread(scrape_website, req.urls, req.team_name)
        chunks.extend(website_chunks)
        print(f"got {len(website_chunks)} chunks from websites")

    if req.org_url:
        github_chunks = await asyncio.to_thread(scrape_github, req.org_url, req.team_name)
        chunks.extend(github_chunks)
        print(f"got {len(github_chunks)} chunks from github")

    if req.confluence_urls:
        for url in req.confluence_urls:
            confluence_chunks = await asyncio.to_thread(scrape_confluence, url, req.team_name)
            chunks.extend(confluence_chunks)
            print(f"got {len(confluence_chunks)} chunks from confluence {url}")

    if req.notion_urls:
        for url in req.notion_urls:
            notion_chunks = await asyncio.to_thread(scrape_notion, url, req.team_name)
            chunks.extend(notion_chunks)
            print(f"got {len(notion_chunks)} chunks from notion {url}")

    if req.discord_channel_ids:
        from discord_bot.bot import bot
        for channel_id in req.discord_channel_ids:
            discord_chunks = await fetch_channel_chunks(bot, channel_id, req.team_name)
            chunks.extend(discord_chunks)
            print(f"got {len(discord_chunks)} chunks from discord channel {channel_id}")

    if chunks:
        # stamp each chunk with hash
        for c in chunks:
            c.content_hash = hashlib.md5(c.content.encode()).hexdigest()

        existing = await db.get_existing_hashes(req.team_name)
        new_hashes = {c.content_hash for c in chunks}

        # del chunks that no longer exist
        stale_ids = [chunk_id for h, chunk_id in existing.items() if h not in new_hashes]
        await db.delete_chunks_by_ids(stale_ids)
        if stale_ids:
            print(f"deleted {len(stale_ids)} stale chunks")
        
        new_chunks = [c for c in chunks if c.content_hash not in existing]
        if new_chunks:
            new_chunks = await asyncio.to_thread(embed_chunks, new_chunks)
            await db.insert_chunks(new_chunks)
        print(f"inserted {len(new_chunks)} new chunks, skipped {len(chunks) - len(new_chunks)} unchanged")

        ctx = await asyncio.to_thread(extract_team_context, req.team_name, chunks)
        await db.upsert_team_context(ctx)
        print(f"team context: {ctx}")

    return {"status": "ok", "team": req.team_name, "chunks_inserted": len(new_chunks) if chunks else 0, "context": ctx if chunks else None}


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
