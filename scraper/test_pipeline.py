import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

data_dir = Path("data")
test_dir = Path("data/test")

# make a tiny companies.json with just 3 entries (1 of each type)
def setup_test_data():
    with open(data_dir / "companies.json") as f:
        all_companies = json.load(f)

    test_companies = []
    types_seen = set()
    for c in all_companies:
        t = c.get("source_type", "")
        if t not in types_seen and c.get("url"):
            test_companies.append(c)
            types_seen.add(t)
        if len(test_companies) >= 3:
            break

    test_dir.mkdir(parents=True, exist_ok=True)
    with open(test_dir / "companies.json", "w") as f:
        json.dump(test_companies, f, indent=2)

    print(f"test data: {[c['name'] for c in test_companies]}")
    return test_companies


if __name__ == "__main__":
    import shutil

    print("---- Setup ----")
    companies = setup_test_data()

    import scraper.scrape as scrape_mod
    import scraper.enrich as enrich_mod

    scrape_mod.companies_file = test_dir / "companies.json"
    scrape_mod.raw_dir = test_dir / "raw_pages"
    enrich_mod.companies_file = test_dir / "companies.json"
    enrich_mod.raw_dir = test_dir / "raw_pages"
    enrich_mod.entities_file = test_dir / "entities.json"

    print("\n---- Scraped ----")
    scrape_mod.scrape()

    print("\n---- Enriched ----")
    enrich_mod.enrich()

    print("\n---- Results ----")
    with open(test_dir / "entities.json") as f:
        entities = json.load(f)

    for e in entities:
        print(f"\n--- {e['name']} ---")
        print(f"  summary: {e.get('summary', 'n/a')}")
        print(f"  tags: {e.get('tags', [])}")
        print(f"  support: {e.get('support_types', [])}")
        print(f"  affinity: {[a['text'] for a in e.get('waterloo_affinity_evidence', [])]}")
