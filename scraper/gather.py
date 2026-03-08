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
teams_file = data_dir / "teams.json"

SDC_BASE = "https://uwaterloo.ca"
SDC_DIR_URL = f"{SDC_BASE}/sedra-student-design-centre/catalogs/directory-teams/category/all-student-design-teams"


def discover_teams():
    """scrape sdc directory"""
    data_dir.mkdir(exist_ok=True)

    existing = {}
    if teams_file.exists():
        with open(teams_file) as f:
            for t in json.load(f):
                existing[t["name"]] = t
        print(f"resuming: {len(existing)} teams already done")

    print(f"fetching SDC directory...")
    html = fetch_page(SDC_DIR_URL)
    soup = BeautifulSoup(html, "html.parser")

    profile_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/catalogs/student-design-teams/" in href:
            name = a.get_text(strip=True)
            if name and name not in existing:
                profile_links.append((name, href))

    # dedup
    seen = set()
    unique = []
    for name, href in profile_links:
        if href not in seen:
            seen.add(href)
            unique.append((name, href))

    print(f"found {len(unique)} teams (+ {len(existing)} already done)")

    teams = list(existing.values())

    for i, (name, profile_path) in enumerate(unique):
        profile_url = SDC_BASE + profile_path if profile_path.startswith("/") else profile_path
        print(f"[{i+1}/{len(unique)}] {name}")

        try:
            profile_html = fetch_page(profile_url)
        except Exception as e:
            print(f"  failed to fetch profile: {e}")
            teams.append({"name": name, "profile_url": profile_url, "website_url": None, "is_uw_subdomain": False})
            _save_teams(teams)
            continue

        profile_soup = BeautifulSoup(profile_html, "html.parser")

        website_url = None
        for tag in profile_soup.find_all(string=re.compile(r"Website", re.I)):
            parent = tag.parent
            a = parent.find("a", href=True)
            if not a:
                # might be in the next sibling
                nxt = parent.find_next_sibling()
                if nxt:
                    a = nxt.find("a", href=True)
            if a:
                website_url = a["href"]
                break

        if not website_url:
            for a in profile_soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and "uwaterloo.ca" not in href:
                    website_url = href
                    break

        is_uw = bool(website_url and "uwaterloo.ca" in website_url)
        if website_url:
            print(f"  -> {website_url}" + (" (uw subdomain)" if is_uw else ""))
        else:
            print(f"  -> no website found")

        teams.append({
            "name": name,
            "profile_url": profile_url,
            "website_url": website_url,
            "is_uw_subdomain": is_uw,
        })
        _save_teams(teams)
        time.sleep(0.5)

    print(f"\ndone. {len(teams)} teams total")
    print(f"  with website: {sum(1 for t in teams if t['website_url'])}")
    print(f"  no website: {sum(1 for t in teams if not t['website_url'])}")
    print(f"  uw subdomains: {sum(1 for t in teams if t['is_uw_subdomain'])}")
    return teams


def _save_teams(teams):
    with open(teams_file, "w") as f:
        json.dump(teams, f, indent=2)


def fetch_page(url):
    r = httpx.get(url, timeout=30, follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    })
    r.raise_for_status()
    return r.text


def extract_with_llm(html, source):
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    page_owner = (source.get("team") or "").strip()
    owner_instruction = ""
    if page_owner:
        owner_instruction = f"\nThis page is from \"{page_owner}\". Do NOT include \"{page_owner}\" or the page owner itself in the list—only list external sponsors or partners."

    prompt = f"""Extract all company or organization names and their website URLs from this HTML.
Return ONLY a JSON array like: [{{"name": "...", "url": "..."}}]
If you can't find a direct URL for a company, try to infer it (e.g. "Intel" -> "https://intel.com").
Only include real companies/orgs that are sponsors or partners listed on the page. Skip navigation links and generic stuff.{owner_instruction}

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
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "discover":
        discover_teams()
    else:
        gather()
