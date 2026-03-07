#misc scraping
import httpx
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# smart crawl imports
import os
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
from google import genai

load_dotenv()

import trafilatura

data_dir = Path("data")
companies_file = data_dir / "companies.json"
raw_dir = data_dir / "raw_pages"

MAX_PAGES = 5


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


# smart scraping -> look for other links 
def get_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc
    links = []
    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, a["href"])
        if urlparse(full).netloc == base_domain and full != base_url:
            links.append(full)
    return list(set(links))


def pick_best_links(links, company_name):
    if not links:
        return []
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    prompt = f"""From {company_name}'s website, pick links most likely to have useful info about what the company does, their products, team, or mission.
Return a JSON array of the best URLs (max 4). Skip privacy policy, terms, login, careers, etc.

Links:
{json.dumps(links[:50])}"""

    try:
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return json.loads(resp.text)[:4]
    except:
        return links[:3]


def smart_crawl(url, company_name):
    pages = {}
    raw_html, text = scrape_url(url)
    if not raw_html:
        return pages

    if text:
        pages["/"] = {
            "url": url,
            "title": company_name,
            "raw_text": text,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    links = get_links(raw_html, url)
    best = pick_best_links(links, company_name)

    for link in best:
        if len(pages) >= MAX_PAGES:
            break
        time.sleep(0.5)
        _, page_text = scrape_url(link)
        if page_text:
            path = urlparse(link).path or link
            pages[path] = {
                "url": link,
                "title": f"{company_name} - {path}",
                "raw_text": page_text,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

    return pages


# hybrid approach - smart crawl and profile handlers (velocity/yc vs design team)
def scrape(limit=None):
    with open(companies_file) as f:
        companies = json.load(f)
    if limit:
        companies = companies[:limit]

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
        src_type = company.get("source_type", "")

        if src_type == "velocity_startup":
            real_url, profile = scrape_velocity_profile(company)
            if profile:
                pages["velocity_profile"] = profile
            if real_url:
                print(f"    real site: {real_url}")
                pages.update(smart_crawl(real_url, name))

        elif src_type == "yc_startup":
            profile = scrape_yc_profile(company)
            if profile:
                pages["yc_profile"] = profile
            pages.update(smart_crawl(url, name))

        else:
            pages.update(smart_crawl(url, name))

        with open(company_dir / "pages.json", "w") as f:
            json.dump(pages, f, indent=2)

        meta = {**company, "pages_scraped": len(pages)}
        with open(company_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)

        print(f"    scraped {len(pages)} pages")
        time.sleep(1)

    print("done")


if __name__ == "__main__":
    scrape()
