ALTER TABLE chunks ADD COLUMN IF NOT EXISTS content_hash text;

CREATE INDEX IF NOT EXISTS chunks_content_hash_idx ON chunks (team_name, content_hash);
