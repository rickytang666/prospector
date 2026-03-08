# 06. Scraper Pipeline

## Objective

The scraper pipeline builds and maintains the external entity corpus used by retrieval.

## Main Orchestration

File: `scraper/run.py`

### Router Endpoints

- `POST /scraper/run`
- `POST /scraper/cleanup`

Both are protected with `X-Scraper-Secret` and `SCRAPER_SECRET`.

### CLI Modes

- Full run: `python -m scraper.run`
- Enrich only: `python -m scraper.run --enrich-only`
- Fast enrich: `python -m scraper.run --fast-enrich`
- Embeddings only: `python -m scraper.run --embeddings-only`

## Stage 1: Gather (`scraper/gather.py`)

Sources include:

- Waterloo design team discovery and sponsor page extraction
- Static source list (`sources.json`)
- Seed entities (`seeds.json`)
- Wikipedia category ingestion (`wikidata.py`)

Output: `data/companies.json`

## Stage 2: Scrape (`scraper/scrape.py`)

- Fetches canonical pages and selected internal links
- Uses source-specific handling for Velocity and YC profiles
- Stores raw extraction payloads in `data/raw_pages/<slug>/pages.json`

## Stage 3: Enrich (`scraper/enrich.py`)

- Uses Gemini to extract structured fields:
  - `summary`, `tags`, `support_types`, contact route hints
- Adds waterloo affinity evidence from source metadata
- Writes normalized entities to `data/entities.json`

`fast_enrich` mode generates coarse entities without LLM extraction.

## Stage 4: Store (`scraper/run.py`)

Persists entities and related records into Supabase:

- `entities`
- `affinity_evidence`
- `contact_routes`
- `entity_documents`
- `entity_embeddings`

Embeddings are generated with model compatibility aligned to retrieval (`text-embedding-3-small`, 1536 dims).

## Cleanup and Maintenance

`run_cleanup` supports deduplication and stale raw-page removal for:

- `companies.json`
- `entities.json`
- `data/raw_pages/*`
