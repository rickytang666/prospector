RANKING_WEIGHTS = {"semantic":0.88,"tag_overlap":0.08,"support_fit":0.02,"waterloo_affinity":0.02}
RANKING_WEIGHTS_PROVIDERS = {"semantic":0.88,"tag_overlap":0.08,"support_fit":0.02,"waterloo_affinity":0.02}
RANKING_WEIGHTS_SPONSORS = {"semantic":0.85,"tag_overlap":0.08,"support_fit":0.02,"waterloo_affinity":0.05}
EMBEDDING_MODEL = EMBEDDING_MODEL = "openai/text-embedding-3-small"

DEFAULT_K = 5
OVER_RETRIEVE_FACTOR = 2

ALLOW_LOCAL_EMBED_FALLBACK = True
LOCAL_DIM = 96
# db retrieval config (person4 embeddings path)
SUPABASE_RPC_MATCH_FN = "match_entities_for_team"
SUPABASE_RPC_MATCH_CHUNKS_FN = "match_internal_chunks_for_team"
LOW_CONFIDENCE_TOP1 = 0.28
MEDIUM_CONFIDENCE_TOP1 = 0.40
MIN_RESULT_SCORE = 0.12
