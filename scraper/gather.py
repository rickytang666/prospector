import httpx
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv()

DATA_DIR = Path("data")
OUT_FILE = DATA_DIR / "companies.json"
SOURCES_FILE = Path(__file__).parent / "sources.json"


def fetch_page(url):
    r = httpx.get(url, timeout=30, follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    })
    r.raise_for_status()
    return r.text


def extract_companies_from_html(html, source):
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    prompt = f"""Extract all company or organization names and their website URLs from this HTML.
Return ONLY a JSON array like: [{{"name": "...", "url": "..."}}]
If you can't find a URL for a company, set url to null.
Only include real companies/orgs, skip navigation links and generic stuff.

HTML:
{html[:50000]}"""

    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )

    try:
        raw = json.loads(resp.text)
    except:
        print(f"  failed to parse LLM response for {source['url']}")
        return []

    companies = []
    for item in raw:
        companies.append({
            "name": item["name"],
            "url": item.get("url"),
            "source_url": source["url"],
            "source_type": source["type"],
            "team": source.get("team"),
        })
    return companies


def dedupe(companies):
    seen = {}
    for c in companies:
        key = c["name"].lower().strip()
        if key not in seen:
            seen[key] = c
    return list(seen.values())


def gather():
    DATA_DIR.mkdir(exist_ok=True)

    with open(SOURCES_FILE) as f:
        sources = json.load(f)

    all_companies = []
    for src in sources:
        print(f"fetching {src['url']}...")
        try:
            html = fetch_page(src["url"])
        except Exception as e:
            print(f"  skip: {e}")
            continue

        print(f"  extracting companies with LLM...")
        companies = extract_companies_from_html(html, src)
        print(f"  found {len(companies)}")
        all_companies.extend(companies)

    deduped = dedupe(all_companies)
    print(f"\ntotal: {len(all_companies)}, after dedup: {len(deduped)}")

    with open(OUT_FILE, "w") as f:
        json.dump(deduped, f, indent=2)
    print(f"saved to {OUT_FILE}")


if __name__ == "__main__":
    gather()
