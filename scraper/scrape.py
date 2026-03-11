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

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def slug(name):
    return name.lower().replace(" ", "_").replace("/", "_").replace(".", "")[:50]


def scrape_homepage(url: str) -> tuple[str, str]:
    """fetch a page and return (final_url, clean_text)."""
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True, headers=_HEADERS)
        r.raise_for_status()
        text = trafilatura.extract(r.text) or ""
        return str(r.url), text
    except Exception as e:
        print(f"  failed: {e}")
        return url, ""


def resolve_velocity_url(profile_url: str) -> str | None:
    """scrape velocity profile page to find the company's real website url."""
    try:
        r = httpx.get(profile_url, timeout=15, follow_redirects=True, headers=_HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # velocity profile has a "Visit" or "Website" link to the real company
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            href = a["href"]
            if ("visit" in text or "website" in text) and "velocityincubator" not in href and href.startswith("http"):
                return href
        # fallback: first external link that isn't velocity
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "velocityincubator" not in href and "uwaterloo" not in href:
                return href
    except Exception as e:
        print(f"  velocity profile fetch failed: {e}")
    return None


def scrape(limit=None):
    """scrape homepages for non-wikidata companies.
    wikidata companies get their text from wikipedia api extracts instead.
    velocity companies get their real url resolved from the profile page first."""
    with open(companies_file) as f:
        companies = json.load(f)
    if limit:
        companies = companies[:limit]

    raw_dir.mkdir(parents=True, exist_ok=True)

    skipped_wiki = 0
    scraped = 0
    already_done = 0

    for i, company in enumerate(companies):
        name = company["name"]
        url = company.get("url")
        src_type = company.get("source_type", "")

        # wikidata companies use wikipedia extracts — skip
        if src_type == "wikidata_vertical":
            skipped_wiki += 1
            continue

        if not url:
            print(f"[{i+1}/{len(companies)}] {name} - no url, skipping")
            continue

        company_dir = raw_dir / slug(name)
        if company_dir.exists():
            already_done += 1
            continue

        print(f"[{i+1}/{len(companies)}] {name}")
        company_dir.mkdir(parents=True, exist_ok=True)

        # velocity profile pages point to their own site, not company site
        # resolve to real company url first
        if src_type == "velocity_startup" and "velocityincubator.com" in url:
            real_url = resolve_velocity_url(url)
            if real_url:
                print(f"  velocity -> {real_url}")
                url = real_url
            else:
                print(f"  couldn't resolve velocity real url, skipping")
                company_dir.rmdir()
                continue
            time.sleep(0.3)

        final_url, text = scrape_homepage(url)
        pages = {}
        if text:
            pages["homepage"] = {
                "url": final_url,
                "title": name,
                "raw_text": text,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        with open(company_dir / "pages.json", "w") as f:
            json.dump(pages, f, indent=2)

        meta = {**company, "scraped_url": final_url, "pages_scraped": len(pages)}
        with open(company_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)

        scraped += 1
        print(f"  {'got ' + str(len(text)) + ' chars' if text else 'no text'}")
        time.sleep(0.5)

    print(f"\ndone. scraped={scraped}, already_done={already_done}, skipped_wikidata={skipped_wiki}")


if __name__ == "__main__":
    scrape()
