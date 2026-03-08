# 02. Setup and Environment

## Prerequisites

- Python 3.10 or newer
- Virtual environment support
- Supabase project with pgvector enabled
- Valid API credentials for required integrations

## Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r discord_bot/requirements.txt
pip install -r scraper/requirements.txt
```

## Environment Variables

Create `.env` from `.env.example`.

### Core Runtime

- `DISCORD_TOKEN`
- `GUILD_ID`
- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `GITHUB_TOKEN`

### Email Support

- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`

### Optional Ingestion Sources

- `NOTION_TOKEN`
- `CONFLUENCE_EMAIL`
- `CONFLUENCE_API_TOKEN`

### Scraper Router Protection

- `SCRAPER_SECRET`

## Start the Full Stack

Preferred:

```bash
uvicorn main:app
```

Alternative helper script:

```bash
bash scripts/run_app.sh
```

## Bot-Only Startup

```bash
python discord_bot/bot.py
```

This mode skips FastAPI router startup and should only be used for isolated bot debugging.

## Rate Limiting

A shared SlowAPI limiter is defined in `rate_limit.py` and attached in `main.py`.
Router-level limits include:

- `/internal/ingest`: `15/minute`
- `/scraper/run`: `10/minute`
- `/scraper/cleanup`: `10/minute`
