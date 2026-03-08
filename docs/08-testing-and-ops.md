# 08. Testing and Operations

## Validation Commands

### Retrieval Smoke Test

```bash
python test_rag.py
```

### Retrieval Script with Optional Query/K

```bash
python scripts/test_retrieval.py
python scripts/test_retrieval.py "cloud credits for student teams" --k 10
```

### Retrieval Internal Checks

```bash
python -m retrieval.check_all
python -m retrieval.functional_eval
python -m retrieval.functional_rag_eval
```

### Scraper Pipeline Test

```bash
python scraper/test_pipeline.py
```

## Runtime Scripts

- `scripts/run_app.sh`: clear cache folders and start FastAPI app
- `scripts/run_bot.sh`: clear bot cache folders and start bot-only process

## Troubleshooting Guide

### Team Context Not Found in Commands

1. Verify user membership exists in `user_teams`
2. Verify team exists in `teams`
3. Verify `team_context` row exists for that team
4. Re-run `/analyze-team` to refresh cache

### Retrieval Falling Back to Local Data

Inspect `retrieval_metadata` for:

- `candidate_source`
- `db_status`
- `db_error`

Then verify:

- Supabase credentials are loaded
- RPC function is deployed
- `entity_embeddings` contains records

### Ingestion Produces No Chunks

- Validate source URLs and credentials
- Confirm GitHub org URL format and token access
- Confirm Notion pages are shared with integration
- Confirm Confluence API credentials are valid

### Email Delivery Fails

- Confirm Gmail app password configuration
- Confirm draft exists in `email_draft_cache` (run `/sample_email` first)
- Inspect SMTP exception details returned by `/send_email`

## Operational Recommendations

- Keep `.env` private and out of version control
- Rotate API credentials periodically
- Protect `/scraper/*` endpoints with strong secrets
- Track ingestion and retrieval errors in central logs
- Consider moving long-running scraper tasks to background workers for production usage
