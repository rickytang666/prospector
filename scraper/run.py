"""
scraper pipeline endpoint
use as a FastAPI router: app.include_router(router, prefix="/scraper")
or run standalone: python -m scraper.run
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from rate_limit import limiter
from pathlib import Path
import json
import os
import shutil
from dotenv import load_dotenv
from supabase import create_client

from scraper.gather import gather, gather_seeds, gather_from_teams, discover_teams, find_sponsor_pages
from scraper.wikidata import fetch_wikipedia_extracts, search_wikipedia_extracts
from scraper.scrape import scrape
from scraper.enrich import enrich, fast_enrich
from scraper.embedding import embed_entity, EMBEDDING_MODEL, get_embedding_error_hint

load_dotenv()

router = APIRouter()
data_dir = Path("data")

SCRAPER_SECRET = os.environ.get("SCRAPER_SECRET")


def require_scraper_secret(x_scraper_secret: str | None = Header(None, alias="X-Scraper-Secret")):
    """Require X-Scraper-Secret header to match SCRAPER_SECRET. Use for cron/trigger-only access."""
    if not SCRAPER_SECRET:
        raise HTTPException(status_code=500, detail="SCRAPER_SECRET not configured")
    if not x_scraper_secret or x_scraper_secret != SCRAPER_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Scraper-Secret")


def is_valid_entity(entity: dict) -> bool:
    """Return False if entity is empty or invalid and should not be stored."""
    if not isinstance(entity, dict):
        return False
    name = entity.get("name")
    if not name or not isinstance(name, str):
        return False
    if not name.strip():
        return False
    # require at least one meaningful field beyond name (avoid junk rows)
    if entity.get("summary") and str(entity["summary"]).strip():
        return True
    tags = entity.get("tags")
    if isinstance(tags, list) and len(tags) > 0:
        return True
    support_types = entity.get("support_types")
    if isinstance(support_types, list) and len(support_types) > 0:
        return True
    evidence = entity.get("waterloo_affinity_evidence")
    if isinstance(evidence, list) and len(evidence) > 0:
        return True
    routes = entity.get("contact_routes")
    if isinstance(routes, list) and len(routes) > 0:
        return True
    if entity.get("canonical_url") and str(entity["canonical_url"]).strip():
        return True
    return False


def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def store_to_supabase(entities, raw_dir, batch_size=100):
    sb = get_supabase()
    if not sb:
        print("no supabase creds, skipping db store")
        return 0

    # batch upsert entities (100 per request instead of 1652 individual requests)
    entity_rows = [
        {
            "id": e["id"],
            "name": e["name"],
            "entity_type": e.get("entity_type", "provider"),
            "canonical_url": e.get("canonical_url"),
            "summary": e.get("summary"),
            "tags": e.get("tags", []),
            "support_types": e.get("support_types", []),
            "source_urls": e.get("source_urls", []),
        }
        for e in entities
    ]
    for i, batch in enumerate(_chunks(entity_rows, batch_size)):
        sb.table("entities").upsert(batch, on_conflict="id").execute()
        print(f"  entities: {min((i+1)*batch_size, len(entity_rows))}/{len(entity_rows)}")

    # batch affinity evidence
    affinity_rows = []
    for e in entities:
        for ev in e.get("waterloo_affinity_evidence", []):
            affinity_rows.append({
                "entity_id": e["id"],
                "type": ev["type"],
                "text": ev["text"],
                "source_url": ev.get("source_url", ""),
            })
    for batch in _chunks(affinity_rows, batch_size):
        sb.table("affinity_evidence").upsert(batch).execute()
    print(f"  affinity_evidence: {len(affinity_rows)} rows")

    # skip entity_documents — not used by rag retrieval, just bloat
    # skip contact_routes — empty for all entities right now

    count = len(entities)

    return count


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("/", "_").replace(".", "")[:50]


def run_embeddings_only(limit: int | None = None) -> dict:
    """
    Generate and store embeddings for entities that don't have one yet.
    Reads from Supabase (entities table), skips rows that already exist in entity_embeddings.
    Returns {"embedded": n, "skipped": m, "failed": k}.
    """
    sb = get_supabase()
    if not sb:
        return {"embedded": 0, "skipped": 0, "failed": 0, "error": "no supabase creds"}

    def _fetch_all(table, columns):
        """paginate through supabase (default cap is 1000 rows)."""
        results = []
        page_size = 1000
        offset = 0
        while True:
            r = sb.table(table).select(columns).range(offset, offset + page_size - 1).execute()
            batch = (r.data or []) if hasattr(r, "data") else []
            results.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return results

    rows = _fetch_all("entities", "id, name, summary, tags, support_types")
    if limit:
        rows = rows[:limit]
    print(f"fetched {len(rows)} entities from supabase")

    existing = {str(x["entity_id"]) for x in _fetch_all("entity_embeddings", "entity_id") if x.get("entity_id")}

    embedded = 0
    failed = 0
    skipped = 0
    first_upsert_error: str | None = None
    for row in rows:
        eid = str(row.get("id") or "")
        if not eid:
            continue
        if eid in existing:
            skipped += 1
            continue
        entity = {
            "id": eid,
            "name": row.get("name") or "",
            "summary": row.get("summary") or "",
            "tags": row.get("tags") or [],
            "support_types": row.get("support_types") or [],
        }
        emb = embed_entity(entity)
        if emb is None:
            failed += 1
            continue
        try:
            sb.table("entity_embeddings").upsert({
                "entity_id": eid,
                "embedding": emb,
                "model": EMBEDDING_MODEL,
            }, on_conflict="entity_id").execute()
            embedded += 1
        except Exception as ex:
            failed += 1
            if first_upsert_error is None:
                first_upsert_error = str(ex)

    out = {"embedded": embedded, "skipped": skipped, "failed": failed}
    if failed > 0 and embedded == 0:
        hint = get_embedding_error_hint()
        out["error"] = hint or first_upsert_error or "embed or upsert failed"
    return out


def _dedupe_companies(companies: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for c in companies:
        key = (c.get("name") or "").strip().lower()
        if key and key not in seen:
            seen[key] = c
    return list(seen.values())


def _dedupe_entities(entities: list[dict]) -> list[dict]:
    by_name: dict[str, dict] = {}
    for e in entities:
        if not isinstance(e, dict):
            continue
        name = (e.get("name") or "").strip().lower()
        if not name:
            continue
        existing = by_name.get(name)
        if existing is None:
            by_name[name] = e
            continue

        def score(x: dict) -> int:
            s = len(str(x.get("summary") or ""))
            s += len(x.get("tags") or []) * 2
            s += len(x.get("support_types") or []) * 2
            s += len(x.get("waterloo_affinity_evidence") or []) * 2
            s += len(x.get("contact_routes") or [])
            return s
        if score(e) > score(existing):
            by_name[name] = e
    return list(by_name.values())


def run_cleanup(companies: bool = True, entities: bool = True, raw_pages: bool = True) -> dict:
    stats = {"companies_removed": 0, "entities_removed": 0, "raw_pages_removed": 0}

    companies_file = data_dir / "companies.json"
    entities_file = data_dir / "entities.json"
    raw_dir = data_dir / "raw_pages"

    if companies and companies_file.exists():
        with open(companies_file) as f:
            data = json.load(f)
        if isinstance(data, list):
            before = len(data)
            deduped = _dedupe_companies(data)
            with open(companies_file, "w") as f:
                json.dump(deduped, f, indent=2)
            stats["companies_removed"] = before - len(deduped)

    if entities and entities_file.exists():
        with open(entities_file) as f:
            data = json.load(f)
        if isinstance(data, list):
            before = len(data)
            deduped = _dedupe_entities(data)
            with open(entities_file, "w") as f:
                json.dump(deduped, f, indent=2)
            stats["entities_removed"] = before - len(deduped)

    if raw_pages and raw_dir.exists():
        companies_list = []
        if companies_file.exists():
            with open(companies_file) as f:
                companies_list = json.load(f)
        if isinstance(companies_list, list):
            valid_slugs = {_slug(c.get("name") or "") for c in companies_list if c.get("name")}
        else:
            valid_slugs = set()
        removed = 0
        if valid_slugs: 
            for path in list(raw_dir.iterdir()):
                if path.is_dir() and path.name not in valid_slugs:
                    shutil.rmtree(path, ignore_errors=True)
                    removed += 1
        stats["raw_pages_removed"] = removed

    return stats


class CleanupParams(BaseModel):
    companies: bool = True
    entities: bool = True
    raw_pages: bool = True


# clean up
@router.post("/cleanup")
@limiter.limit("10/minute")
def cleanup(
    request: Request,
    params: CleanupParams = CleanupParams(),
    _auth: None = Depends(require_scraper_secret),
):

    stats = run_cleanup(
        companies=params.companies,
        entities=params.entities,
        raw_pages=params.raw_pages,
    )
    return {"status": "done", **stats}


class RunParams(BaseModel):
    sources: list[dict] | None = None
    limit: int | None = None
    enrich_only: bool = False
    embeddings_only: bool = False  # only generate embeddings for existing entities in DB (skip gather/scrape/enrich/store)


@router.post("/run")
@limiter.limit("10/minute")
def run_pipeline(
    request: Request,
    params: RunParams = RunParams(),
    _auth: None = Depends(require_scraper_secret),
):
    if params.embeddings_only:
        out = run_embeddings_only(limit=params.limit)
        return {"status": "done", **out}

    # run full pipeline: gather -> scrape -> enrich -> store (or enrich + store only if enrich_only)
    if not params.enrich_only:
        if params.sources:
            import tempfile
            import scraper.gather as g
            tmp = Path(tempfile.mktemp(suffix=".json"))
            with open(tmp, "w") as f:
                json.dump(params.sources, f)
            g.sources_file = tmp

        discover_teams()
        find_sponsor_pages()
        gather_from_teams()
        gather_seeds()
        from scraper.wikidata import gather_wikidata
        gather_wikidata(data_dir / "companies.json")
        fetch_wikipedia_extracts(data_dir / "companies.json")
        gather()
        scrape(limit=params.limit)
        search_wikipedia_extracts(data_dir / "companies.json")

    enrich(limit=params.limit)

    entities_file = data_dir / "entities.json"
    entities = json.load(open(entities_file)) if entities_file.exists() else []
    valid_entities = [e for e in entities if is_valid_entity(e)]
    skipped = len(entities) - len(valid_entities)
    if skipped:
        print(f"Skipped {skipped} empty/invalid entities")

    raw_dir = data_dir / "raw_pages"
    stored = store_to_supabase(valid_entities, raw_dir)

    return {
        "status": "done",
        "count": len(entities),
        "valid": len(valid_entities),
        "skipped": skipped,
        "stored_to_db": stored,
    }


# standalone mode
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scraper pipeline")
    parser.add_argument("--enrich-only", action="store_true", help="Skip gather & scrape; only run enrich and store to DB")
    parser.add_argument("--fast-enrich", action="store_true", help="No LLM — build entities from scraped text directly, then store to DB")
    parser.add_argument("--embeddings-only", action="store_true", help="Only generate embeddings for existing entities in DB (no gather/scrape/enrich)")
    parser.add_argument("--limit", type=int, default=None, help="Max companies to process")
    args = parser.parse_args()

    if args.embeddings_only:
        out = run_embeddings_only(limit=args.limit)
        print(f"Embeddings: {out['embedded']} embedded, {out['skipped']} already had, {out['failed']} failed.")
        if out.get("error"):
            print(f"Reason: {out['error']}")
    elif args.fast_enrich:
        fast_enrich(limit=args.limit)
        entities_file = data_dir / "entities.json"
        entities = json.load(open(entities_file)) if entities_file.exists() else []
        valid_entities = [e for e in entities if is_valid_entity(e)]
        skipped = len(entities) - len(valid_entities)
        if skipped:
            print(f"Skipped {skipped} empty/invalid entities")
        raw_dir = data_dir / "raw_pages"
        stored = store_to_supabase(valid_entities, raw_dir)
        print(f"Done. {len(entities)} entities ({len(valid_entities)} valid), {stored} stored to DB.")
    elif args.enrich_only:
        enrich(limit=args.limit)
        entities_file = data_dir / "entities.json"
        entities = json.load(open(entities_file)) if entities_file.exists() else []
        valid_entities = [e for e in entities if is_valid_entity(e)]
        skipped = len(entities) - len(valid_entities)
        if skipped:
            print(f"Skipped {skipped} empty/invalid entities")
        raw_dir = data_dir / "raw_pages"
        stored = store_to_supabase(valid_entities, raw_dir)
        print(f"Done. {len(entities)} entities ({len(valid_entities)} valid), {stored} stored to DB.")
    else:
        from fastapi import FastAPI
        import uvicorn
        app = FastAPI(title="scraper pipeline")
        app.include_router(router)
        uvicorn.run(app, host="0.0.0.0", port=8000)
