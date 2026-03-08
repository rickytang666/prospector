# 07. Database and Migrations

## Table Domains

### Team Context Domain

- `chunks`
- `team_context`
- `teams`
- `user_teams`

### External Entity Domain

- `entities`
- `entity_documents`
- `affinity_evidence`
- `contact_routes`
- `entity_embeddings`

## Migration Files

### `migrations/001_create_chunks.sql`

Creates chunk storage with pgvector support and relevant indexes.

### `migrations/002_create_team_context.sql`

Creates one context row per `team_name` with extracted fields.

### `migrations/003_add_content_hash.sql`

Adds `content_hash` for incremental deduplication.

### `migrations/004_teams_and_user_teams.sql`

Introduces server team registry and user membership mapping.

### `migrations/005_user_teams_multiple.sql`

Extends membership model to allow multiple teams per user and active-team selection.

### `migrations/002_entity_embeddings_1536.sql`

Aligns entity embedding vector dimension to 1536.

### `migrations/003_match_entities_rpc.sql`

Defines semantic retrieval RPC `match_entities_for_team`.

## Recommended Migration Sequence

1. `001_create_chunks.sql`
2. `002_create_team_context.sql`
3. `003_add_content_hash.sql`
4. `004_teams_and_user_teams.sql`
5. `005_user_teams_multiple.sql`
6. `scraper/schema.sql` (if entity tables are not yet provisioned)
7. `002_entity_embeddings_1536.sql` (if dimension mismatch exists)
8. `003_match_entities_rpc.sql`

## Operational Notes

- Retrieval code expects 1536-dimensional embeddings
- RPC output may vary in shape; `retrieval/db_retrieval.py` handles normalization
- `storage/db.py` performs asynchronous Supabase operations through thread offloading
