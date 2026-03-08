-- RPC: vector similarity search over entity_embeddings.
-- Call from client with a pre-computed query embedding (1536-dim, same model as scraper).
-- Requires: vector extension, entities + entity_embeddings + affinity_evidence tables.

create or replace function match_entities_for_team(
  query_embedding vector(1536),
  k int default 10,
  filters jsonb default '{}'
)
returns table (
  entity_id uuid,
  name text,
  entity_type text,
  summary text,
  tags text[],
  support_types text[],
  waterloo_affinity_evidence jsonb,
  semantic_score float
)
language plpgsql
as $$
begin
  return query
  select
    e.id as entity_id,
    e.name,
    e.entity_type,
    e.summary,
    e.tags,
    e.support_types,
    coalesce(
      (select jsonb_agg(jsonb_build_object(
        'type', a.type,
        'text', a.text,
        'source_url', coalesce(a.source_url, '')
      ))
       from affinity_evidence a
       where a.entity_id = e.id),
      '[]'::jsonb
    ) as waterloo_affinity_evidence,
    (1.0 - (ee.embedding <=> query_embedding))::float as semantic_score
  from entities e
  join entity_embeddings ee on ee.entity_id = e.id
  where ee.embedding is not null
  order by ee.embedding <=> query_embedding
  limit least(greatest(k, 1), 100);
end;
$$;
