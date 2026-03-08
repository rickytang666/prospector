# 08 - Testing And Ops

## Quick tests

### Retrieval smoke

```bash
python test_rag.py
```

### Retrieval script with custom query

```bash
python scripts/test_retrieval.py
python scripts/test_retrieval.py "cloud credits for student teams" --k 10
```

### Internal consistency checks

```bash
python -m retrieval.check_all
python -m retrieval.functional_eval
python -m retrieval.functional_rag_eval
```

### Scraper mini test

```bash
python scraper/test_pipeline.py
```

## Run scripts

- `scripts/run_app.sh`
  - clears `__pycache__`
  - starts `uvicorn main:app`

- `scripts/run_bot.sh`
  - starts bot-only mode
  - mainly for bot debugging

## Debug checklist by symptom

### Command says no team context

1. Check user has membership in `user_teams`
2. Check team has row in `teams`
3. Check `team_context` row exists for that `team_name`
4. Run `/analyze-team` to refresh cache

### Retrieval returns fallback local data

- Check `.env` has Supabase keys
- Verify RPC function exists and is callable
- Confirm `entity_embeddings` has rows
- Check metadata fields:
  - `candidate_source`
  - `db_status`
  - `db_error`

### Ingestion inserts 0 chunks

- Validate GitHub org URL and token scope
- Validate source URLs are reachable
- For Notion, page must be shared with integration token
- For Confluence, space URL and API token must be valid

### Email send fails

- Verify Gmail app password, not normal password
- Verify SMTP over 465 with TLS is allowed
- Check `/sample_email` was run so cache has draft

## Security and production hygiene

- Keep `.env` out of git
- Protect `/scraper/run` with strong `SCRAPER_SECRET`
- Apply DB row level permissions per your Supabase policy
- Log and rotate API errors for ingestion and scraper tasks

## Known rough edges

- LLM ranking path depends on `data/companies.json` existing
- Cache key types are mixed in a few code paths
- Some retrieval defaults are semantic-only right now
- Scraper quality depends hard on source HTML quality and LLM extraction stability

## Nice next upgrades

1. Add unit tests for each cog command path with mocked DB and retrieval
2. Add schema validation for `entities.json` before DB write
3. Add observability counters for ingestion duration and retrieval fallback rate
4. Move long-running scraper jobs to a queue worker instead of request thread
