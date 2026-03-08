# 01 - System Overview

## Big picture

Think of this like a 3-brain robot:

1. Bot brain: Discord slash commands and chat UX
2. Team memory brain: ingest docs and extract team blockers/needs
3. Matchmaker brain: rank companies/labs/providers for support

Everything runs in one Python app process when started via `uvicorn main:app`.

## Runtime flow

### App startup

- `main.py` builds FastAPI app
- FastAPI lifespan runs `asyncio.create_task(start_bot())`
- Bot cogs load in `discord_bot/bot.py`
- FastAPI routers:
  - `/internal/*` from `internal_context/router.py`
  - `/scraper/*` from `scraper/run.py`

### Core user journey

1. Admin runs `/setup-team`
2. Bot ingests team repo/docs and stores chunks + team_context
3. Member runs `/configure-team add` to join team
4. Member runs `/find-support` or `/chat`
5. Retrieval engine ranks candidates using query + team context
6. Bot shows embeds, explanation, and optional email draft

## Folder map with purpose

### `discord_bot/`

- `bot.py`: bot init, cog loading, slash sync, error handling
- `cogs/*.py`: all slash commands
- `ui/embeds.py`: rich result formatting
- `ui/buttons.py`: interactive views and modal logic
- `team_ctx.py`: load cached or DB team context
- `ai.py`: Gemini helper calls for contact lookup and ask expansion

### `internal_context/`

- `ingestion/*`: pull text from GitHub/website/Notion/Confluence/Discord
- `chunking/chunker.py`: split text into chunk objects
- `embedding/embedder.py`: embed chunk text with OpenRouter embedding model
- `extraction/extractor.py`: LLM turns chunks into team summary fields
- `router.py`: `/internal/ingest`, `/internal/context/{team}`, `/internal/chunks/{team}`

### `retrieval/`

- `api.py`: main wrappers used by cogs
- `llm_ranking.py`: LLM-first candidate ranking path from `data/companies.json`
- `ranking.py`: fallback deterministic ranking path
- `context_pack.py`: entity + internal chunk retrieval bundle
- `db_retrieval.py`: normalize Supabase RPC rows
- `internal_retrieval.py`: fetch internal chunks via Supabase RPC
- `models.py`: dataclasses for ranking types

### `scraper/`

- `gather.py`: collect candidate companies from many sources
- `scrape.py`: crawl company pages
- `enrich.py`: LLM structure extraction into entity docs
- `embedding.py`: build vector embeddings for entities
- `run.py`: API endpoint and CLI runner for whole pipeline
- `schema.sql`: DB schema for entity pipeline tables

### `storage/`

- `db.py`: async wrappers over Supabase table operations

### Root files

- `config.py`: env vars
- `rate_limit.py`: shared SlowAPI limiter
- `INTEGRATION.md`: integration notes and command mapping
- `test_rag.py`: simple retrieval smoke test

## Shared data model idea

There are two data worlds:

1. Team-specific internal memory
- Table: `chunks`, `team_context`, `teams`, `user_teams`

2. Global external candidate memory
- Table: `entities`, `entity_embeddings`, `affinity_evidence`, `contact_routes`, `entity_documents`

Bot commands glue both worlds together in real time.
