from fastapi import FastAPI
from pydantic import BaseModel
from pathlib import Path
import json

from scraper.gather import gather
from scraper.scrape import scrape
from scraper.enrich import enrich
from scraper.db import store, load_entities

#temp, will be endpoint alterc
app = FastAPI(title="scraper pipeline")


class RunParams(BaseModel):
    sources: list[dict] | None = None  # custom sources list, uses default if not provided
    limit: int | None = None  # max companies to process


@app.post("/run")
def run_pipeline(params: RunParams = RunParams()):
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
    store()

    entities = load_entities()
    return {"status": "done", "count": len(entities)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
