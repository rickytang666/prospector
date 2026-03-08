import httpx
import time
import json
from pathlib import Path
from urllib.parse import quote

# wikipedia category API
WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "enghacks-scraper/1.0 (https://github.com/rickytang666/enghacks)"}

# (vertical_name, wikipedia_category_name)
CATEGORIES = [
    ("electric_vehicles", "Electric vehicle manufacturers"),
    ("aerospace", "Aerospace manufacturers of the United States"),
    ("aerospace", "Aerospace companies of Canada"),
    ("spaceflight", "Space launch vehicle manufacturers"),
    ("semiconductors", "Semiconductor companies"),
    ("robotics", "Robotics companies"),
    ("autonomous_vehicles", "Autonomous vehicle companies"),
    ("lidar", "Lidar"),
]


def query_category(category: str) -> list[str]:
    """get all article titles in a wikipedia category, handling pagination."""
    titles = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmlimit": 500,
        "cmtype": "page",
        "format": "json",
    }

    while True:
        r = httpx.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()

        batch = data.get("query", {}).get("categorymembers", [])
        titles.extend(p["title"] for p in batch)

        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
        time.sleep(0.3)

    return titles


def wiki_url(title: str) -> str:
    return f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"


def gather_wikidata(out_file: Path):
    existing = []
    if out_file.exists():
        with open(out_file) as f:
            existing = json.load(f)

    existing_names = {c["name"].lower().strip() for c in existing}
    all_companies = list(existing)
    total_added = 0

    for vertical, category in CATEGORIES:
        print(f"querying wikipedia category: '{category}'...")
        try:
            titles = query_category(category)
        except Exception as e:
            print(f"  failed: {e}")
            time.sleep(3)
            continue

        new = []
        for title in titles:
            key = title.lower().strip()
            if key in existing_names:
                continue
            existing_names.add(key)
            new.append({
                "name": title,
                "url": wiki_url(title),
                "source_url": f"https://en.wikipedia.org/wiki/Category:{category.replace(' ', '_')}",
                "source_type": "wikidata_vertical",
                "vertical": vertical,
                "team": None,
            })

        print(f"  got {len(titles)} titles, {len(new)} new")
        all_companies.extend(new)
        total_added += len(new)

        with open(out_file, "w") as f:
            json.dump(all_companies, f, indent=2)

        time.sleep(1)

    print(f"\nadded {total_added} companies from wikipedia categories")


if __name__ == "__main__":
    import sys
    out = Path("data/companies.json")
    if "--test" in sys.argv:
        category = CATEGORIES[0][1]
        print(f"testing category: '{category}'")
        titles = query_category(category)
        print(f"got {len(titles)} titles:")
        for t in titles[:15]:
            print(f"  {t}")
    else:
        gather_wikidata(out)
