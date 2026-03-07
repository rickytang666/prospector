CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    team_name   text NOT NULL,
    source_type text NOT NULL,
    source_url  text,
    content     text NOT NULL,
    embedding   vector(1536),   -- text-embedding-3-small
    created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chunks_team_name_idx ON chunks (team_name);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
