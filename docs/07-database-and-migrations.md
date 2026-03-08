# 07 - Database And Migrations

## DB zones

You got two table families.

### Team context family

- `chunks`
- `team_context`
- `teams`
- `user_teams`

### External entity family

- `entities`
- `entity_documents`
- `affinity_evidence`
- `contact_routes`
- `entity_embeddings`

## Migration files

### `001_create_chunks.sql`

Creates `chunks` with vector(1536) embedding and ivfflat index.

### `002_create_team_context.sql`

Creates `team_context` keyed by unique `team_name`.

### `003_add_content_hash.sql`

Adds `content_hash` for dedupe and incremental updates.

### `004_teams_and_user_teams.sql`

Creates team registry and user membership tables.

### `005_user_teams_multiple.sql`

Allows multiple team memberships per user and adds `is_active` field.

### `003_match_entities_rpc.sql`

Creates RPC `match_entities_for_team` for vector similarity retrieval.

### `002_entity_embeddings_1536.sql`

Rebuilds embedding column to 1536 if old dimension mismatches.

## Team context row shape

Stored by extractor/upsert code:

- `team_name`
- `tech_stack[]`
- `focus_areas[]`
- `blockers[]`
- `needs[]`
- `raw_llm_output`

`storage/db.py` maps this into bot runtime shape, including:

- `active_blockers`
- `inferred_support_needs`
- `context_summary`
- plus repo fields from `teams`

## Membership semantics

`user_teams` logic in `storage/db.py`:

- user can belong to many teams in guild
- one row should be active per user-guild
- `set_active_team` flips booleans
- `get_user_team` picks active first, fallback first row

## Suggested migration order

1. `001_create_chunks.sql`
2. `002_create_team_context.sql`
3. `003_add_content_hash.sql`
4. `004_teams_and_user_teams.sql`
5. `005_user_teams_multiple.sql`
6. scraper schema objects (`scraper/schema.sql`) if missing
7. `002_entity_embeddings_1536.sql` if needed
8. `003_match_entities_rpc.sql`

## RPC compatibility notes

- Embedding model in code uses `text-embedding-3-small`
- Dimension must be 1536 in both chunks and entity embeddings
- If RPC returns odd row shapes, normalization in `retrieval/db_retrieval.py` tries to recover
