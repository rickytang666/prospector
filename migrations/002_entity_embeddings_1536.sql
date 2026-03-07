-- Align entity_embeddings with retrieval (openai/text-embedding-3-small = 1536 dims).
-- Run this if your entity_embeddings.embedding is still vector(768).
-- Existing 768-dim rows cannot be cast to 1536; we drop the column and re-add it.

ALTER TABLE entity_embeddings DROP COLUMN IF EXISTS embedding;
ALTER TABLE entity_embeddings ADD COLUMN embedding vector(1536);
