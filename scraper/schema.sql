-- entities table (main one)
create table entities (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    entity_type text not null default 'provider',
    canonical_url text,
    summary text,
    tags text[] default '{}',
    support_types text[] default '{}',
    source_urls text[] default '{}',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- raw scraped docs per entity
create table entity_documents (
    id uuid primary key default gen_random_uuid(),
    entity_id uuid references entities(id) on delete cascade,
    url text not null,
    title text,
    raw_text text,
    fetched_at timestamptz
);

-- waterloo affinity evidence
create table affinity_evidence (
    id uuid primary key default gen_random_uuid(),
    entity_id uuid references entities(id) on delete cascade,
    type text not null,
    text text not null,
    source_url text
);

-- contact info
create table contact_routes (
    id uuid primary key default gen_random_uuid(),
    entity_id uuid references entities(id) on delete cascade,
    type text not null,
    value text not null
);

-- for person 3 (embeddings/ranking)
-- enable pgvector: create extension if not exists vector;
create table entity_embeddings (
    id uuid primary key default gen_random_uuid(),
    entity_id uuid references entities(id) on delete cascade unique,
    embedding vector(768),
    model text,
    created_at timestamptz default now()
);

-- indexes
create index idx_entities_type on entities(entity_type);
create index idx_entities_tags on entities using gin(tags);
create index idx_affinity_entity on affinity_evidence(entity_id);
create index idx_docs_entity on entity_documents(entity_id);
create index idx_embeddings_entity on entity_embeddings(entity_id);
