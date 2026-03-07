import httpx
import time
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from bs4 import BeautifulSoup

load_dotenv()

data_dir = Path("data")
out_file = data_dir / "companies.json"
sources_file = Path(__file__).parent / "sources.json"


def fetch_page(url):
    r = httpx.get(url, timeout=30, follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)" #fake user agent to avoid being blocked
    })
    r.raise_for_status()
    return r.text


# default: send html to gemini and let it figure out the companies
def extract_with_llm(html, source):
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    prompt = f""" Extract all company or organization names and their website URLs from this HTML.
Return ONLY a JSON array like: [{{"name": "...", "url": "..."}}]
If you can't find a direct URL for a company, try to infer it (e.g. "Intel" -> "https://intel.com").
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


# velocity - scrape with bs4
def extract_velocity(html, source):
    soup = BeautifulSoup(html, "html.parser")
    companies = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/company/" not in href:
            continue
        slug = href.rstrip("/").split("/")[-1]
        if slug in seen:
            continue
        seen.add(slug)
        name = slug.replace("-", " ").title()
        companies.append({
            "name": name,
            "url": f"https://velocityincubator.com{href}" if href.startswith("/") else href,
            "source_url": source["url"],
            "source_type": source["type"],
            "team": None,
        })
    return companies


# yc public api
def extract_yc(source):
    all_companies = []
    page = 1
    while True:
        print(f"  page {page}...")
        r = httpx.get("https://api.ycombinator.com/v0.1/companies", params={"page": page}, headers={
            "User-Agent": "Mozilla/5.0"
        }, timeout=30)
        data = r.json()
        batch = data.get("companies", [])
        if not batch:
            break
        for c in batch:
            all_companies.append({
                "name": c.get("name", ""),
                "url": c.get("url"),
                "source_url": source["url"],
                "source_type": source["type"],
                "team": None,
            })
        page += 1
        if page > 5:  # cap it for mvp
            break
        time.sleep(0.5)
    return all_companies


def dedupe(companies):
    seen = {}
    for c in companies:
        key = c["name"].lower().strip()
        if key not in seen:
            seen[key] = c
    return list(seen.values())


def gather():
    data_dir.mkdir(exist_ok=True)

    with open(sources_file) as f:
        sources = json.load(f)

    all_companies = []
    for src in sources:
        print(f"fetching {src['url']}...")

        if src["type"] == "yc_startup":
            companies = extract_yc(src)

        elif src["type"] == "velocity_startup":
            try:
                html = fetch_page(src["url"])
            except Exception as e:
                print(f"  skip: {e}")
                continue
            print(f"  parsing with bs4...")
            companies = extract_velocity(html, src)

        else:
            try:
                html = fetch_page(src["url"])
            except Exception as e:
                print(f"  skip: {e}")
                continue
            print(f"  extracting with LLM...")
            companies = extract_with_llm(html, src)
            time.sleep(2)

        print(f"  found {len(companies)}")
        all_companies.extend(companies)

    deduped = dedupe(all_companies)
    print(f"\ntotal: {len(all_companies)}, after dedup: {len(deduped)}")

    with open(out_file, "w") as f:
        json.dump(deduped, f, indent=2)
    print(f"saved to {out_file}")


if __name__ == "__main__":
    gather()
