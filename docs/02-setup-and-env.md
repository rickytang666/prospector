# 02 - Setup And Env

## Requirements

- Python 3.10+
- A working virtual environment
- Supabase project with pgvector extension
- API keys for Discord, Gemini, OpenRouter, GitHub

## Install deps

From repo root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r discord_bot/requirements.txt
pip install -r scraper/requirements.txt
```

## Environment variables

Use `.env.example` as template.

Required for most flows:

- `DISCORD_TOKEN`
- `GUILD_ID`
- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `GITHUB_TOKEN`

Email feature:

- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`

Optional ingestion:

- `NOTION_TOKEN`
- `CONFLUENCE_EMAIL`
- `CONFLUENCE_API_TOKEN`

Scraper endpoint auth:

- `SCRAPER_SECRET`

## Start the app

Correct way:

```bash
uvicorn main:app --reload
```

Helper script:

```bash
bash scripts/run_app.sh
```

Wrong for integrated mode:

```bash
python discord_bot/bot.py
```

That starts bot only and skips FastAPI routers.

## Rate limiting

- SlowAPI limiter is configured globally in `rate_limit.py`
- Applied in routers like:
  - `/internal/ingest`: `15/minute`
  - `/scraper/run`: `10/minute`
  - `/scraper/cleanup`: `10/minute`

## Sanity check checklist

1. `uvicorn main:app` starts without env errors
2. Bot logs show cogs loaded and slash command sync done
3. `/internal/context/{team}` returns JSON after ingestion
4. `/find-support` returns ranked candidates, not empty errors
