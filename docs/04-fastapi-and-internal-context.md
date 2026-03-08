# 04. FastAPI and Internal Context

## FastAPI Composition

File: `main.py`

- Creates app with lifespan manager
- Starts Discord bot task during startup
- Registers rate-limit exception handler
- Includes routers:
  - `/internal` from `internal_context/router.py`
  - `/scraper` from `scraper/run.py`

## Internal Context Router

File: `internal_context/router.py`

### `POST /internal/ingest`

Input model: `IngestRequest`

- `team_name`
- `org_url`
- `urls[]`
- `discord_channel_ids[]`
- `notion_urls[]`
- `confluence_urls[]`

Pipeline:

1. Fetch source content and produce chunks
2. Compute `content_hash` per chunk
3. Compare with existing hashes for incremental update
4. Delete stale chunks no longer present in source set
5. Embed and insert only new chunks
6. Derive team context via extractor
7. Upsert context row into `team_context`

### `GET /internal/context/{team_name}`

Returns stored context row for a team, or 404 if missing.

### `GET /internal/chunks/{team_name}`

Returns all chunks for a team, or 404 if none exist.

## Ingestion Connectors

### GitHub (`ingestion/github.py`)

- Lists repositories in an org
- Collects README, docs markdown files, and open issues
- Excludes forks, archived repos, and pull requests

### Website (`ingestion/website.py`)

- Uses `sitemap.xml` when available
- Falls back to bounded internal crawl
- Strips navigation/boilerplate content

### Notion (`ingestion/notion.py`)

- Parses page ID from URL
- Attempts official API first when token is configured
- Falls back to unofficial `loadPageChunk` endpoint
- Supports child-page traversal

### Confluence (`ingestion/confluence.py`)

- Parses Confluence space URLs
- Paginates pages through REST API
- Extracts text from `body.storage` HTML

### Discord (`ingestion/discord_ingestion.py`)

- Ingests signal messages from channels and threads
- Excludes bot and non-default message types
- Groups messages into chunk payloads

## Chunking, Embedding, Extraction

- `chunking/chunker.py`: paragraph-based chunk assembly
- `embedding/embedder.py`: OpenRouter embedding generation (`text-embedding-3-small`)
- `extraction/extractor.py`: LLM extraction into team context fields (`tech_stack`, `focus_areas`, `blockers`, `needs`)
