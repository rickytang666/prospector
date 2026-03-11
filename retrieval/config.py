# one weight set for all profiles — semantic and support-fit dominate, affinity is a tiebreaker
RANKING_WEIGHTS = {'semantic': 0.65, 'tag_overlap': 0.1, 'support_fit': 0.2, 'waterloo_affinity': 0.05}


EMBEDDING_MODEL = "openai/text-embedding-3-small"

DEFAULT_K = 10
SEMANTIC_CANDIDATE_K = 100   # how many to pull from vector search
SPONSOR_POOL_K = 50          # max team sponsors to include regardless of semantic score
LLM_RERANK_CANDIDATE_K = 20  # pass top N to llm for final ranking + reason generation
LLM_RERANK_MODEL = "google/gemini-2.5-flash-lite"

ALLOW_LOCAL_EMBED_FALLBACK = True
LOCAL_DIM = 96
SUPABASE_RPC_MATCH_FN = "match_entities_for_team"
SUPABASE_RPC_MATCH_CHUNKS_FN = "match_internal_chunks_for_team"
LOW_CONFIDENCE_TOP1 = 0.28
MEDIUM_CONFIDENCE_TOP1 = 0.40
MIN_RESULT_SCORE = 0.12
MIN_SEMANTIC_SCORE = 0.28  # entities below this are semantically irrelevant regardless of affinity
