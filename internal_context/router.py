import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from storage import db
from internal_context.ingestion.website import scrape_website
from internal_context.ingestion.github import scrape_github
from internal_context.ingestion.discord_ingestion import fetch_channel_chunks
from internal_context.ingestion.notion import scrape_notion
from internal_context.embedding.embedder import embed_chunks
from internal_context.extraction.extractor import extract_team_context

router = APIRouter()


class IngestRequest(BaseModel):
    team_name: str
    org_url: str
    urls: list[str] = []  # website, docs, wiki — wtv the team has
    discord_channel_ids: list[int] = []  # team picks which channels to ingest
    notion_urls: list[str] = []


@router.post("/ingest")
async def ingest(req: IngestRequest):
    await db.delete_chunks(req.team_name)
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
        chunks = await asyncio.to_thread(embed_chunks, chunks)
        await db.insert_chunks(chunks)
        ctx = await asyncio.to_thread(extract_team_context, req.team_name, chunks)
        await db.upsert_team_context(ctx)
        print(f"team context: {ctx}")

    return {"status": "ok", "team": req.team_name, "chunks_inserted": len(chunks), "context": ctx if chunks else None}


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
