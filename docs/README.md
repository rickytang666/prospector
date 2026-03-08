# EngHacks Project Docs

Yo team. This is the full map for this repo, but explained like we are smart Grade 3 chaos goblins building space software.

If you are new, read in this order:

1. `01-system-overview.md`
2. `02-setup-and-env.md`
3. `03-discord-bot.md`
4. `04-fastapi-and-internal-context.md`
5. `05-retrieval-and-ranking.md`
6. `06-scraper-pipeline.md`
7. `07-database-and-migrations.md`
8. `08-testing-and-ops.md`

## What this project is

This repo is one app process that runs:

- A FastAPI backend (`main.py`)
- A Discord bot (started in FastAPI lifespan)
- Internal team context ingestion and extraction
- Retrieval and ranking engine for support candidates
- A scraper pipeline that builds the external entity database

Main objective:

- Team runs Discord commands
- Bot loads their team context from DB
- Bot finds best support orgs and explains matches
- Bot can draft and send outreach email

## Fast mental model

- `discord_bot/`: slash commands and UI
- `internal_context/`: ingest GitHub, website, Notion, Confluence, Discord content
- `retrieval/`: rank entities and fetch context packs
- `scraper/`: build `entities` + embeddings into Supabase
- `storage/`: DB access helpers for team context and memberships
- `migrations/`: SQL schema + RPC functions
- `scripts/`: run helpers and test helpers

## Tiny warning

Do not run `python discord_bot/bot.py` for normal full-stack usage.
Use `uvicorn main:app` so bot + backend live together on same event loop.
