import httpx
import time
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
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


sponsor_keywords = {"sponsor", "sponsors", "partner", "partners", "support", "funding", "donor", "supporters"}
sponsor_pages_file = data_dir / "team_sponsor_pages.json"


def _score_link(href: str, text: str) -> int:
    score = 0
    h, t = href.lower(), text.lower()
    for kw in sponsor_keywords:
        if kw in h:
            score += 2
        if kw in t:
            score += 1
    return score


def _get_internal_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, a["href"])
        if urlparse(full).netloc == base_domain and full not in seen:
            seen.add(full)
            links.append((full, a.get_text(strip=True)))
    return links


def _pick_sponsor_page_llm(links: list[tuple[str, str]], team_name: str) -> tuple[str | None, bool]:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    link_list = [{"url": url, "text": text} for url, text in links[:15]]
    prompt = f"""From {team_name}'s website navigation, which URL is most likely their sponsors or partners page?
Return JSON: {{"url": "...", "found": true}}
If none look like a sponsors/partners/supporters page, return {{"url": null, "found": false}}.
Don't guess — only return found:true if you're confident.

Links:
{json.dumps(link_list)}"""

    try:
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        result = json.loads(resp.text)
        return result.get("url"), bool(result.get("found", False))
    except Exception as e:
        print(f"  llm pick failed: {e}")
        return None, False


def find_sponsor_pages():
    """for each team in teams.json, find their sponsor page url."""
    if not teams_file.exists():
        print("no teams.json found, run discover first")
        return []

    with open(teams_file) as f:
        teams = json.load(f)

    # resume
    existing = {}
    if sponsor_pages_file.exists():
        with open(sponsor_pages_file) as f:
            for entry in json.load(f):
                existing[entry["name"]] = entry
        print(f"resuming: {len(existing)} teams already processed")

    results = list(existing.values())

    to_process = [t for t in teams if t["name"] not in existing]
    skipped_no_url = [t for t in to_process if not t.get("website_url")]
    to_process = [t for t in to_process if t.get("website_url")]

    for t in skipped_no_url:
        results.append({"name": t["name"], "website_url": None, "sponsor_page_url": None, "found": False, "reason": "no website"})

    print(f"{len(to_process)} teams to process, {len(skipped_no_url)} skipped (no website)")

    for i, team in enumerate(to_process):
        name = team["name"]
        url = team["website_url"]
        is_uw = team.get("is_uw_subdomain", False)
        print(f"[{i+1}/{len(to_process)}] {name} ({url})")

        if is_uw:
            print(f"  skipping uw subdomain (handle separately)")
            results.append({"name": name, "website_url": url, "sponsor_page_url": None, "found": False, "reason": "uw_subdomain"})
            _save_sponsor_pages(results)
            continue

        try:
            html = fetch_page(url)
        except Exception as e:
            print(f"  failed to fetch homepage: {e}")
            results.append({"name": name, "website_url": url, "sponsor_page_url": None, "found": False, "reason": f"fetch_error: {e}"})
            _save_sponsor_pages(results)
            continue

        links = _get_internal_links(html, url)

        # heuristic: score every link
        scored = [(score, link_url, text) for link_url, text in links if (score := _score_link(link_url, text)) > 0]
        scored.sort(reverse=True)

        if scored:
            best_score, best_url, best_text = scored[0]
            print(f"  heuristic match (score={best_score}): {best_url} [{best_text!r}]")
            results.append({"name": name, "website_url": url, "sponsor_page_url": best_url, "found": True, "reason": "heuristic"})
            _save_sponsor_pages(results)
        else:
            print(f"  no heuristic match, asking llm ({len(links)} links)...")
            sponsor_url, found = _pick_sponsor_page_llm(links, name)
            if found and sponsor_url:
                print(f"  llm picked: {sponsor_url}")
            else:
                print(f"  llm: not found")
            results.append({"name": name, "website_url": url, "sponsor_page_url": sponsor_url, "found": found, "reason": "llm"})
            _save_sponsor_pages(results)
            time.sleep(1)  # rate limit gemini

        time.sleep(0.5)

    found_count = sum(1 for r in results if r["found"])
    print(f"\ndone. {found_count}/{len(results)} teams have a sponsor page")
    return results


def _save_sponsor_pages(results):
    with open(sponsor_pages_file, "w") as f:
        json.dump(results, f, indent=2)


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
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "discover":
        discover_teams()
    elif cmd == "find_sponsors":
        find_sponsor_pages()
    else:
        gather()
