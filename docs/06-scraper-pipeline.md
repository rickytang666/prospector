# 06 - Scraper Pipeline

## Purpose

This pipeline builds the external candidate database used by retrieval.

High-level chain:

1. Gather company URLs from many sources
2. Scrape pages
3. Enrich into structured entities
4. Store entities and embeddings in Supabase

## Main entrypoints

### API mode

Router in `scraper/run.py`:

- `POST /scraper/run`
- `POST /scraper/cleanup`

Both require header:

- `X-Scraper-Secret: <SCRAPER_SECRET>`

### CLI mode

```bash
python -m scraper.run
python -m scraper.run --enrich-only
python -m scraper.run --fast-enrich
python -m scraper.run --embeddings-only
```

## Gather stage

File: `scraper/gather.py`

Data source tactics:

- Discover Waterloo student design teams from SDC directory
- Find sponsor pages per team
- Extract sponsor companies from sponsor pages
- Add hardcoded seeds (`seeds.json`)
- Add Wikipedia category companies (`wikidata.py`)
- Parse generic source pages from `sources.json`

Output file:

- `data/companies.json`

## Scrape stage

File: `scraper/scrape.py`

For each company:

- Pull homepage text with trafilatura
- Smart crawl extra internal pages using LLM-picked links
- Special handling:
  - Velocity profile pages
  - YC profile pages

Output folder:

- `data/raw_pages/<slug>/pages.json`

## Enrich stage

File: `scraper/enrich.py`

- Gemini prompt extracts:
  - summary
  - tags
  - support_types
  - contact route hints
- Adds waterloo affinity evidence from source type
- Writes `data/entities.json`
- Supports resume and retry on rate limit

Fast mode (`fast_enrich`) skips LLM and makes rough entities from scraped text only.

## Store stage

`store_to_supabase` in `scraper/run.py` writes:

- `entities`
- `affinity_evidence`
- `contact_routes`
- `entity_documents`
- `entity_embeddings` (when embedding succeeds)

## Embeddings-only mode

`run_embeddings_only`:

- Reads existing `entities` table
- Skips ids already in `entity_embeddings`
- Generates missing vectors only

## Cleanup mode

`run_cleanup` dedupes and prunes:

- companies list
- entities list
- raw page folders with no matching company slug

## Common pipeline files

- `scraper/sources.json`
- `scraper/seeds.json`
- `data/teams.json`
- `data/team_sponsor_pages.json`
- `data/companies.json`
- `data/entities.json`
