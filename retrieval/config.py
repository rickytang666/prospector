RANKING_WEIGHTS = {"semantic":0.40,"tag_overlap":0.25,"support_fit":0.20,"waterloo_affinity":0.15}
EMBEDDING_MODEL = EMBEDDING_MODEL = "openai/text-embedding-3-small"

DEFAULT_K = 5
OVER_RETRIEVE_FACTOR = 2

ALLOW_LOCAL_EMBED_FALLBACK = True
LOCAL_DIM = 96
# db retrieval config (person4 embeddings path)
SUPABASE_RPC_MATCH_FN = "match_entities_for_team"
