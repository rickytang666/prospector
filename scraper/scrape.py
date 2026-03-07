import httpx
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import trafilatura

data_dir = Path("data")
companies_file = data_dir / "companies.json"
raw_dir = data_dir / "raw_pages"


def slug(name):
    return name.lower().replace(" ", "_").replace("/", "_").replace(".", "")[:50]


def scrape_url(url):
    try:
        r = httpx.get(url, timeout=20, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        r.raise_for_status()
        text = trafilatura.extract(r.text) or ""
        return r.text, text
    except Exception as e:
        print(f"    failed: {e}")
        return None, ""


def scrape():
    with open(companies_file) as f:
        companies = json.load(f)

    raw_dir.mkdir(parents=True, exist_ok=True)

    for i, company in enumerate(companies):
        name = company["name"]
        url = company.get("url")
        if not url:
            print(f"[{i+1}/{len(companies)}] {name} - no url, skipping")
            continue

        company_dir = raw_dir / slug(name)
        if company_dir.exists():
            print(f"[{i+1}/{len(companies)}] {name} - already scraped")
            continue

        print(f"[{i+1}/{len(companies)}] {name} - {url}")
        company_dir.mkdir(parents=True, exist_ok=True)

        pages = {}
        for path in ["", "/about", "/contact"]:
            target = url.rstrip("/") + path
            print(f"    {target}")
            raw_html, clean_text = scrape_url(target)
            if clean_text:
                pages[path or "/"] = {
                    "url": target,
                    "title": name + (f" - {path}" if path else ""),
                    "raw_text": clean_text,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            time.sleep(0.5)

        with open(company_dir / "pages.json", "w") as f:
            json.dump(pages, f, indent=2)

        meta = {**company, "pages_scraped": len(pages)}
        with open(company_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)

    print("done")


if __name__ == "__main__":
    scrape()
