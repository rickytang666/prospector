# 05 - Retrieval And Ranking

## Top-level API surface

Main entry: `retrieval/api.py`

Useful functions called by bot:

- `find_support_dict(team_context, query, k=5)`
- `find_providers_dict(team_context, query, k=5)`
- `find_sponsors_dict(team_context, query, message=None, k=5)`
- `retrieve_context_pack_dict(team_context, query, k_entities=5, k_chunks=5)`

## Ranking strategy

`rank_candidates_dict` first tries:

- `llm_ranking.llm_rank_candidates_dict`

If that throws, it falls back to:

- `ranking.rank_candidates` classic phase1 engine

## LLM ranking path

File: `retrieval/llm_ranking.py`

- Loads `data/companies.json`
- Prompts OpenRouter chat model (`google/gemini-2.5-flash-lite`)
- Asks for top-k JSON candidates with reasons
- Maps output into `RankedCandidate` shape

Metadata marks source as `llm_in_memory`.

## Classic ranking path

File: `retrieval/ranking.py`

Flow:

1. Normalize team context object
2. Build query and over-retrieve `k*2`
3. Try Supabase RPC semantic candidates first
4. If DB empty/error, use local mock entities + local embeddings
5. Score each entity
6. Deduplicate by `(name, entity_type)`
7. Filter by `MIN_RESULT_SCORE`
8. Build confidence and metadata

Current default weights in `retrieval/config.py` are semantic-only for all profiles.

## Score components

From `retrieval/scoring.py` and ranking internals:

- semantic similarity
- tag overlap
- support fit (team needs vs entity support types)
- waterloo affinity

Even if some weights are 0 now, fields are still computed and returned.

## Supabase entity RPC

Migration: `migrations/003_match_entities_rpc.sql`

Function:

- `match_entities_for_team(query_embedding vector(1536), k int, filters jsonb)`

Returns per entity:

- id, name, type, summary, tags, support_types
- affinity evidence as JSONB
- `semantic_score`

## Internal chunk retrieval

File: `retrieval/internal_retrieval.py`

- Calls RPC configured by `SUPABASE_RPC_MATCH_CHUNKS_FN`
- Normalizes rows into:
  - `chunk_id`, `text`, `source`, `source_ref`, `semantic_score`

## Context pack for chat/explain

File: `retrieval/context_pack.py`

`retrieve_context_pack` returns:

- `entity_matches`
- `internal_chunks`
- `citations`
- `retrieval_meta`

It can infer chunk filters based on query words, then rerank chunks with:

- semantic score
- query term overlap
- source boosts

## Config knobs

`retrieval/config.py` important settings:

- ranking weights
- default `k`
- over-retrieve factor
- confidence thresholds
- min score cutoff
- RPC function names
- fallback local embedding toggle and dimension
