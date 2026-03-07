import httpx
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

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


# scrape velocity profile page, find real company url
def scrape_velocity_profile(company):
    profile_url = company["url"]
    raw_html, profile_text = scrape_url(profile_url)
    if not raw_html:
        return None, {}

    soup = BeautifulSoup(raw_html, "html.parser")
    real_url = None
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        href = a["href"]
        if "visit" in text and "velocityincubator" not in href:
            real_url = href
            break

    profile_data = {
        "url": profile_url,
        "title": f"{company['name']} - Velocity Profile",
        "raw_text": profile_text,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    return real_url, profile_data


# scrape yc profile page for extra info
def scrape_yc_profile(company):
    name_slug = company["name"].lower().replace(" ", "-")
    profile_url = f"https://www.ycombinator.com/companies/{name_slug}"
    _, profile_text = scrape_url(profile_url)
    if not profile_text:
        return {}

    return {
        "url": profile_url,
        "title": f"{company['name']} - YC Profile",
        "raw_text": profile_text,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


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
