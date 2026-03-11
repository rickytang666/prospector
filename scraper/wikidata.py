import httpx
import time
import json
from pathlib import Path
from urllib.parse import quote

WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "enghacks-scraper/1.0 (https://github.com/rickytang666/enghacks)"}

# (vertical, wikipedia_category) — canada-heavy, engineering-focused
CATEGORIES = [
    # canadian companies (high priority — waterloo teams mostly reach out to cdn companies)
    ("canada_tech", "Technology companies of Canada"),
    ("canada_engineering", "Engineering companies of Canada"),
    ("canada_aerospace", "Aerospace companies of Canada"),
    ("canada_automotive", "Automotive companies of Canada"),
    ("canada_robotics", "Robotics companies of Canada"),
    ("canada_software", "Software companies of Canada"),
    ("canada_defense", "Defence companies of Canada"),

    # north american industry leaders
    ("aerospace", "Aerospace companies of the United States"),
    ("defense", "Defense companies of the United States"),
    ("semiconductors", "Semiconductor companies"),
    ("robotics", "Robotics companies"),
    ("autonomous_vehicles", "Autonomous vehicle companies"),
    ("electric_vehicles", "Electric vehicle manufacturers"),
    ("lidar", "Lidar"),
    ("eda_tools", "Electronic design automation companies"),
    ("industrial_automation", "Industrial automation companies"),
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


def fetch_wikipedia_extracts(companies_file: Path):
    """fetch intro paragraphs from wikipedia API for wikidata_vertical companies.
    batches 50 at a time, very fast (~10 api calls for 500 companies)."""
    if not companies_file.exists():
        print("no companies.json found")
        return

    with open(companies_file) as f:
        companies = json.load(f)

    # only wikidata companies that don't have an extract yet
    to_fetch = [c for c in companies if c.get("source_type") == "wikidata_vertical" and not c.get("wikipedia_extract")]
    if not to_fetch:
        print("all wikidata companies already have extracts")
        return

    print(f"fetching wikipedia extracts for {len(to_fetch)} companies...")

    # title → company dict for fast lookup
    title_map = {c["name"]: c for c in to_fetch}

    batch_size = 50
    titles = list(title_map.keys())
    updated = 0

    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        params = {
            "action": "query",
            "prop": "extracts",
            "exintro": True,
            "exsentences": 3,
            "explaintext": True,  # plain text, no html tags
            "titles": "|".join(batch),
            "format": "json",
        }

        try:
            r = httpx.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()
            pages = data.get("query", {}).get("pages", {})

            for page_data in pages.values():
                title = page_data.get("title", "")
                extract = (page_data.get("extract") or "").strip()
                if extract and title in title_map:
                    title_map[title]["wikipedia_extract"] = extract
                    updated += 1

            print(f"  batch {i // batch_size + 1}/{(len(titles) - 1) // batch_size + 1}: got {len(pages)} pages")
        except Exception as e:
            print(f"  batch {i // batch_size + 1} failed: {e}")

        time.sleep(0.5)

    with open(companies_file, "w") as f:
        json.dump(companies, f, indent=2)

    print(f"updated {updated} wikipedia extracts")


def _title_matches(query: str, title: str) -> bool:
    """loose check — returned title should relate to the company name."""
    q = query.lower().strip()
    t = title.lower().strip()
    # title contains company name or company name contains title words
    if q in t or t in q:
        return True
    # at least half the query words appear in the title
    words = [w for w in q.split() if len(w) > 2]
    if not words:
        return False
    hits = sum(1 for w in words if w in t)
    return hits / len(words) >= 0.5


def search_wikipedia_extracts(companies_file: Path):
    """for companies with no wikipedia_extract and no scraped content,
    search wikipedia by name and pull the intro extract if a good match is found.
    free, no llm — upgrades template summaries for major companies."""
    if not companies_file.exists():
        print("no companies.json found")
        return

    with open(companies_file) as f:
        companies = json.load(f)

    raw_dir = Path("data/raw_pages")

    def _has_scraped_text(name: str) -> bool:
        slug = name.lower().replace(" ", "_").replace("/", "_").replace(".", "")[:50]
        pages_file = raw_dir / slug / "pages.json"
        if not pages_file.exists():
            return False
        with open(pages_file) as f:
            pages = json.load(f)
        return any(p.get("raw_text") for p in pages.values())

    # candidates: no extract yet, no scraped text
    candidates = [
        c for c in companies
        if not c.get("wikipedia_extract") and not _has_scraped_text(c["name"])
    ]
    print(f"searching wikipedia for {len(candidates)} companies with no content...")

    updated = 0
    for i, company in enumerate(candidates):
        name = company["name"]
        try:
            # step 1: opensearch to find best matching article title
            r = httpx.get(WIKI_API, params={
                "action": "opensearch",
                "search": name,
                "limit": 1,
                "format": "json",
            }, headers=HEADERS, timeout=10)
            r.raise_for_status()
            data = r.json()
            titles = data[1] if len(data) > 1 else []
            if not titles:
                continue
            title = titles[0]

            if not _title_matches(name, title):
                # print(f"  skip {name!r} -> {title!r} (no match)")
                continue

            # step 2: fetch the intro extract for that title
            r2 = httpx.get(WIKI_API, params={
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "exsentences": 3,
                "explaintext": True,
                "titles": title,
                "format": "json",
            }, headers=HEADERS, timeout=10)
            r2.raise_for_status()
            pages = r2.json().get("query", {}).get("pages", {})
            extract = next((p.get("extract", "").strip() for p in pages.values()), "")

            if extract:
                company["wikipedia_extract"] = extract
                updated += 1
                print(f"  [{i+1}/{len(candidates)}] {name} -> {title!r} ({len(extract)} chars)")

            time.sleep(0.2)  # be polite

        except Exception as e:
            print(f"  [{i+1}/{len(candidates)}] {name} failed: {e}")

    with open(companies_file, "w") as f:
        json.dump(companies, f, indent=2)
    print(f"\nupdated {updated}/{len(candidates)} companies with wikipedia search extracts")


if __name__ == "__main__":
    import sys
    out = Path("data/companies.json")
    if "--extracts" in sys.argv:
        fetch_wikipedia_extracts(out)
    elif "--search" in sys.argv:
        search_wikipedia_extracts(out)
    elif "--test" in sys.argv:
        category = CATEGORIES[0][1]
        print(f"testing category: '{category}'")
        titles = query_category(category)
        print(f"got {len(titles)} titles:")
        for t in titles[:15]:
            print(f"  {t}")
    else:
        gather_wikidata(out)
