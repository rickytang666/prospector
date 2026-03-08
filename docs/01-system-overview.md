# 01. System Overview

## Purpose

This project provides a Discord-first workflow for engineering teams to:

- Ingest and maintain team-specific context from internal sources
- Retrieve and rank external support candidates
- Generate match explanations and outreach drafts

## Runtime Architecture

The application runs as a single process when started via `uvicorn main:app`.

- `main.py` starts FastAPI
- FastAPI lifespan starts the Discord bot task (`start_bot()`)
- Bot commands call backend modules directly within the same process

This avoids network hop overhead between bot and backend logic.

## Primary Subsystems

### Discord Bot (`discord_bot/`)

- Slash commands and command routing
- Per-user/team cache management
- Embed/view rendering
- Chat, explanation, and email interactions

### Internal Context Pipeline (`internal_context/`)

- Source ingestion (GitHub, website, Notion, Confluence, Discord)
- Text chunking and embeddings
- Team context extraction with LLM
- Persistence into Supabase tables via `storage/db.py`

### Retrieval Layer (`retrieval/`)

- Candidate ranking APIs used by commands
- LLM-first ranking path with deterministic fallback
- Context pack assembly (external entity matches + internal chunks)

### Scraper Pipeline (`scraper/`)

- Entity discovery and collection from multiple data sources
- Content scraping and enrichment
- Structured entity persistence and embedding generation

### Persistence Layer (`storage/` + `migrations/`)

- Team context, chunks, team registry, and user-team membership
- External entity tables and vector retrieval RPC function

## User Flow Summary

1. Administrator registers and ingests a team with `/setup-team`
2. User joins and selects active team with `/configure-team` and `/set-active-team`
3. User runs `/analyze-team`, `/find-support`, `/chat`, and `/explain-match`
4. Retrieval combines team context with external candidates
5. User may generate and send outreach emails via `/sample_email` and `/send_email`
