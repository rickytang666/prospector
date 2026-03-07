"""
db storage layer
right now just saves to json. swap in supabase later
"""
import json
from pathlib import Path

data_dir = Path("data")
entities_file = data_dir / "entities.json"


def load_entities():
    if not entities_file.exists():
        return []
    with open(entities_file) as f:
        return json.load(f)


def save_entities(entities):
    data_dir.mkdir(exist_ok=True)
    with open(entities_file, "w") as f:
        json.dump(entities, f, indent=2)
    print(f"saved {len(entities)} entities to {entities_file}")


def store_to_supabase(entities):
    # TODO: connect to supabase and insert entities
    # from supabase import create_client
    # client = create_client(url, key)
    # for entity in entities:
    #     client.table("entities").upsert(entity).execute()
    print(f"[placeholder] would store {len(entities)} entities to supabase")
    print("using local json for now")
    save_entities(entities)


def store():
    entities = load_entities()
    if not entities:
        print("no entities to store, run enrich first")
        return
    store_to_supabase(entities)
