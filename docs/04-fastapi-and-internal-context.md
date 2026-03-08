# 04 - FastAPI And Internal Context

## FastAPI app

File: `main.py`

- Builds `FastAPI(lifespan=lifespan)`
- Starts Discord bot in lifespan task
- Registers limiter + limit error handler
- Includes routers:
  - `/internal` -> `internal_context/router.py`
  - `/scraper` -> `scraper/run.py`

## Internal context API

Router: `internal_context/router.py`

### `POST /internal/ingest`

Body model (`IngestRequest`):

- `team_name: str`
- `org_url: str`
- `urls: list[str]`
- `discord_channel_ids: list[int]`
- `notion_urls: list[str]`
- `confluence_urls: list[str]`

Pipeline:

1. Collect chunks from enabled sources
2. Generate `content_hash` per chunk
3. Compare against existing hashes in DB
4. Delete stale chunk ids
5. Embed and insert only new chunks
6. Run `extract_team_context`
7. Upsert result into `team_context`

### `GET /internal/context/{team_name}`

Returns stored context row for team.
404 if missing.

### `GET /internal/chunks/{team_name}`

Returns all chunks for team.
404 if none.

## Ingestion source modules

### GitHub (`ingestion/github.py`)

- Parses org from URL
- Lists non-fork, non-archived repos
- Pulls:
  - README
  - open issues (not PRs)
  - markdown files under `docs/`

Chunk source types:

- `github_readme`
- `github_issue`

### Website (`ingestion/website.py`)

- Uses sitemap when possible
- Falls back to crawler up to 50 pages
- Removes noisy tags and short lines
- Chunks text with source type `website`

### Notion (`ingestion/notion.py`)

- Parses page ID from URL
- Tries official Notion API first when token exists
- Falls back to unofficial `loadPageChunk` API
- Recurses into child pages up to limit
- Chunks as source type `notion`

### Confluence (`ingestion/confluence.py`)

- Parses `.../wiki/spaces/{SPACEKEY}` URL
- Uses Confluence REST pagination to list pages
- Fetches `body.storage` HTML and extracts text
- Chunks as source type `confluence`

### Discord ingestion (`ingestion/discord_ingestion.py`)

- Pulls signal messages from channels and threads
- Keeps messages with code/links/attachments or long text
- Groups into chunk blobs by target word size

## Chunking and embedding

- `chunking/chunker.py`:
  - Paragraph-based batching
  - Default target around 400 words

- `embedding/embedder.py`:
  - OpenRouter embeddings
  - Model: `openai/text-embedding-3-small`
  - Batch size: 100

## Context extraction

`extraction/extractor.py`:

- Prioritizes `github_readme`, `website`, `notion`
- Samples rest randomly
- Uses capped chunk count and truncated content
- LLM returns strict JSON fields:
  - `tech_stack`
  - `focus_areas`
  - `blockers`
  - `needs`
- Stored as `team_context` row
