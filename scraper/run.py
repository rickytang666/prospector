"""
scraper pipeline endpoint
use as a FastAPI router: app.include_router(router, prefix="/scraper")
or run standalone: python -m scraper.run
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
import os
from dotenv import load_dotenv
from supabase import create_client

from scraper.gather import gather
from scraper.scrape import scrape
from scraper.enrich import enrich

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


def store_to_supabase(entities, raw_dir):
    sb = get_supabase()
    if not sb:
        print("no supabase creds, skipping db store")
        return 0

    count = 0
    for entity in entities:
        # insert main entity
        row = {
            "id": entity["id"],
            "name": entity["name"],
            "entity_type": entity.get("entity_type", "provider"),
            "canonical_url": entity.get("canonical_url"),
            "summary": entity.get("summary"),
            "tags": entity.get("tags", []),
            "support_types": entity.get("support_types", []),
            "source_urls": entity.get("source_urls", []),
        }
        sb.table("entities").upsert(row, on_conflict="id").execute()

        # insert affinity evidence
        for ev in entity.get("waterloo_affinity_evidence", []):
            sb.table("affinity_evidence").insert({
                "entity_id": entity["id"],
                "type": ev["type"],
                "text": ev["text"],
                "source_url": ev.get("source_url", ""),
            }).execute()

        # insert contact routes
        for cr in entity.get("contact_routes", []):
            sb.table("contact_routes").insert({
                "entity_id": entity["id"],
                "type": cr["type"],
                "value": cr["value"],
            }).execute()

        # insert scraped docs
        slug = entity["name"].lower().replace(" ", "_").replace("/", "_").replace(".", "")[:50]
        pages_file = raw_dir / slug / "pages.json"
        if pages_file.exists():
            with open(pages_file) as f:
                pages = json.load(f)
            for page in pages.values():
                sb.table("entity_documents").insert({
                    "entity_id": entity["id"],
                    "url": page.get("url", ""),
                    "title": page.get("title"),
                    "raw_text": page.get("raw_text"),
                    "fetched_at": page.get("fetched_at"),
                }).execute()

        count += 1

    return count


class RunParams(BaseModel):
    sources: list[dict] | None = None  # custom sources list, uses default sources.json if not set
    limit: int | None = None  # max companies to scrape/enrich
    enrich_only: bool = False  # if True, skip gather & scrape (use existing companies.json + raw_pages)


@router.post("/run")
def run_pipeline(
    params: RunParams = RunParams(),
    _auth: None = Depends(require_scraper_secret),
):
    # run full pipeline: gather -> scrape -> enrich -> store (or enrich + store only if enrich_only)
    if not params.enrich_only:
        if params.sources:
            import tempfile
            import scraper.gather as g
            tmp = Path(tempfile.mktemp(suffix=".json"))
            with open(tmp, "w") as f:
                json.dump(params.sources, f)
            g.sources_file = tmp

        gather()
        scrape(limit=params.limit)

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
    parser.add_argument("--limit", type=int, default=None, help="Max companies to process")
    args = parser.parse_args()

    if args.enrich_only:
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
