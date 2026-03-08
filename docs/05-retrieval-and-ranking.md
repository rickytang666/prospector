# 05. Retrieval and Ranking

## API Entry Points

File: `retrieval/api.py`

Primary functions:

- `find_support_dict(...)`
- `find_providers_dict(...)`
- `find_sponsors_dict(...)`
- `retrieve_context_pack_dict(...)`
- `rank_candidates_dict(...)`

These are used directly by Discord cogs.

## Ranking Execution Strategy

`rank_candidates_dict` attempts:

1. LLM ranking path (`retrieval/llm_ranking.py`)
2. Deterministic fallback (`retrieval/ranking.py`) on failure

## LLM Ranking Path

File: `retrieval/llm_ranking.py`

- Loads candidates from `data/companies.json`
- Sends query and team context to OpenRouter chat model
- Parses JSON candidate output
- Maps to `RankedCandidate` format

Returned metadata marks mode as LLM-driven.

## Deterministic Ranking Path

File: `retrieval/ranking.py`

Major steps:

1. Normalize incoming `team_context`
2. Build query and over-retrieve candidate set
3. Pull semantic candidates from Supabase RPC when available
4. Fall back to local mocked entity corpus when DB is unavailable/empty
5. Compute score breakdown components
6. Deduplicate and threshold candidates
7. Return metadata including confidence and DB status

## Score Components

Defined across `retrieval/scoring.py` and ranking logic:

- Semantic similarity
- Tag overlap
- Support fit (team needs vs support types)
- Waterloo affinity

Current configured weights in `retrieval/config.py` are semantic-focused.

## Context Pack Retrieval

File: `retrieval/context_pack.py`

`retrieve_context_pack(...)` returns:

- `entity_matches`
- `internal_chunks`
- `citations`
- `retrieval_meta`

Internal chunk retrieval uses `retrieval/internal_retrieval.py` and an RPC configured by `SUPABASE_RPC_MATCH_CHUNKS_FN`.

## RPC Data Normalization

File: `retrieval/db_retrieval.py`

This module normalizes inconsistent row payload shapes from RPC responses:

- list/string field coercion
- affinity JSON normalization
- semantic score normalization to `[0,1]`

## Configuration

File: `retrieval/config.py`

Notable parameters:

- Ranking weight profiles
- Default and over-retrieve `k`
- Confidence thresholds
- Minimum result score
- RPC function names
- Fallback embedding controls
