"""
scraper pipeline endpoint
use as a FastAPI router: app.include_router(router, prefix="/scraper")
or run standalone: python -m scraper.run
"""
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from pathlib import Path
import json

from scraper.gather import gather
from scraper.scrape import scrape
from scraper.enrich import enrich

router = APIRouter()
data_dir = Path("data")


class RunParams(BaseModel):
    sources: list[dict] | None = None  # custom sources list, uses default sources.json if not set
    limit: int | None = None  # max companies to scrape/enrich


@router.post("/run")
def run_pipeline(params: RunParams = RunParams()):
    """run full pipeline: gather -> scrape -> enrich"""
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
    return {"status": "done", "count": len(entities)}


# standalone mode
if __name__ == "__main__":
    import uvicorn
    app = FastAPI(title="scraper pipeline")
    app.include_router(router)
    uvicorn.run(app, host="0.0.0.0", port=8000)
