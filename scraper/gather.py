import httpx
import time
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()

data_dir = Path("data")
out_file = data_dir / "companies.json"
sources_file = Path(__file__).parent / "sources.json"
seeds_file = Path(__file__).parent / "seeds.json"
teams_file = data_dir / "teams.json"

SDC_BASE = "https://uwaterloo.ca"
SDC_DIR_URL = f"{SDC_BASE}/sedra-student-design-centre/catalogs/directory-teams/category/all-student-design-teams"


def discover_teams():
    """scrape sdc directory for all waterloo design teams"""
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


def find_sponsor_pages():
    """for each team, find their sponsor page url using heuristic scoring only."""
    if not teams_file.exists():
        print("no teams.json found, run discover first")
        return []

    with open(teams_file) as f:
        teams = json.load(f)

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
            print(f"  skipping uw subdomain")
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
        scored = [(score, link_url, text) for link_url, text in links if (score := _score_link(link_url, text)) > 0]
        scored.sort(reverse=True)

        if scored:
            best_score, best_url, best_text = scored[0]
            print(f"  heuristic match (score={best_score}): {best_url}")
            results.append({"name": name, "website_url": url, "sponsor_page_url": best_url, "found": True, "reason": "heuristic"})
        else:
            # no sponsor page found — will fall back to homepage in gather_from_teams
            print(f"  no sponsor page found")
            results.append({"name": name, "website_url": url, "sponsor_page_url": None, "found": False, "reason": "not_found"})

        _save_sponsor_pages(results)
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


# text that definitely isn't a company name
_SKIP_TEXTS = {
    "", "home", "about", "contact", "careers", "login", "sign up", "signup",
    "register", "privacy", "terms", "team", "news", "blog", "events", "gallery",
    "donate", "visit", "click here", "learn more", "read more", "website", "more",
    "facebook", "twitter", "instagram", "linkedin", "youtube", "discord", "x",
    "apply", "join", "get started", "explore", "back", "next", "previous",
}


def extract_sponsors_bs4(html: str, source: dict) -> list[dict]:
    """extract sponsor company names and urls from html using bs4 only.
    two-pass: image links first (logo grids), then text external links."""
    soup = BeautifulSoup(html, "html.parser")
    base_url = source.get("url", "")
    base_domain = urlparse(base_url).netloc
    team = source.get("team")
    src_type = source.get("type", "design_team_sponsor")

    companies = []
    seen_hrefs = set()

    # pass 1: linked images (sponsor logo grids — most common format)
    for a in soup.find_all("a", href=True):
        img = a.find("img")
        if not img:
            continue
        href = a["href"].strip()
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        if not href.startswith("http"):
            continue
        if urlparse(href).netloc == base_domain:
            continue
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        alt = img.get("alt", "").strip()
        img_src = img.get("src", "").strip()
        # alt text first, fall back to filename
        name = alt or img_src.split("/")[-1].split(".")[0].replace("-", " ").replace("_", " ").title()
        name = name.strip()
        if not name or len(name) < 2:
            continue

        companies.append({
            "name": name,
            "url": href,
            "source_url": source["url"],
            "source_type": src_type,
            "team": team,
        })

    # pass 2: text-based external links (for pages that list sponsors as links, not logos)
    # only run if we didn't find many from pass 1
    if len(companies) < 3:
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.startswith("http"):
                href = urljoin(base_url, href)
            if not href.startswith("http"):
                continue
            if urlparse(href).netloc == base_domain:
                continue
            if href in seen_hrefs:
                continue

            text = a.get_text(strip=True)
            if not text or text.lower() in _SKIP_TEXTS:
                continue
            # company names are short — skip long strings (sentences, descriptions)
            if len(text) > 60 or len(text.split()) > 6:
                continue
            # skip obvious nav/social patterns
            if any(x in href.lower() for x in ["/privacy", "/terms", "/careers", "/login", "/signin"]):
                continue

            seen_hrefs.add(href)
            companies.append({
                "name": text,
                "url": href,
                "source_url": source["url"],
                "source_type": src_type,
                "team": team,
            })

    return companies


teams_scraped_file = data_dir / "teams_scraped.txt"


def _load_scraped() -> set:
    if not teams_scraped_file.exists():
        return set()
    return set(teams_scraped_file.read_text().splitlines())


def _mark_scraped(name: str):
    with open(teams_scraped_file, "a") as f:
        f.write(name + "\n")


def gather_from_teams():
    """scrape each team's sponsor page and extract companies with bs4 (no llm)."""
    if not sponsor_pages_file.exists():
        print("no team_sponsor_pages.json found, run find_sponsors first")
        return

    with open(sponsor_pages_file) as f:
        teams = json.load(f)

    scraped = _load_scraped()

    existing = []
    if out_file.exists():
        with open(out_file) as f:
            existing = json.load(f)
    all_companies = list(existing)

    to_do = [t for t in teams if t["name"] not in scraped]
    print(f"{len(to_do)} teams to scrape, {len(scraped)} already done")

    for i, team in enumerate(to_do):
        name = team["name"]

        if team.get("found") and team.get("sponsor_page_url"):
            url = team["sponsor_page_url"]
            label = "sponsor page"
        elif team.get("website_url"):
            url = team["website_url"]
            label = "homepage (no sponsor page)"
        else:
            print(f"[{i+1}/{len(to_do)}] {name} - no url, skipping")
            _mark_scraped(name)
            continue

        print(f"[{i+1}/{len(to_do)}] {name} ({label})")

        try:
            html = fetch_page(url)
        except Exception as e:
            print(f"  fetch failed: {e}")
            _mark_scraped(name)
            continue

        # skip SPA shells with no content
        plain_text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
        if len(plain_text) < 300:
            print(f"  very little text ({len(plain_text)} chars), likely SPA — skipping")
            _mark_scraped(name)
            continue

        src = {"url": url, "type": "design_team_sponsor", "team": name}
        companies = extract_sponsors_bs4(html, src)
        print(f"  extracted {len(companies)} companies")

        all_companies.extend(companies)
        _mark_scraped(name)
        with open(out_file, "w") as f:
            json.dump(all_companies, f, indent=2)

        time.sleep(1)

    deduped = dedupe(all_companies)
    print(f"\ntotal: {len(all_companies)}, after dedup: {len(deduped)}")
    with open(out_file, "w") as f:
        json.dump(deduped, f, indent=2)
    print(f"saved to {out_file}")


def gather_seeds():
    """inject hardcoded seeds from seeds.json"""
    data_dir.mkdir(exist_ok=True)

    with open(seeds_file) as f:
        seeds = json.load(f)

    existing = []
    if out_file.exists():
        with open(out_file) as f:
            existing = json.load(f)

    existing_names = {c["name"].lower().strip() for c in existing}

    added = 0
    for s in seeds:
        if s["name"].lower().strip() in existing_names:
            print(f"  skip (already exists): {s['name']}")
            continue
        existing.append({
            "name": s["name"],
            "url": s["url"],
            "source_url": s["url"],
            "source_type": "hardcoded_seed",
            "vertical": s.get("vertical"),
            "team": None,
        })
        added += 1
        print(f"  added: {s['name']}")

    with open(out_file, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"\nadded {added} seeds ({len(seeds) - added} already existed)")


def dedupe(companies):
    seen = {}
    for c in companies:
        key = c["name"].lower().strip()
        if not key:
            continue
        if key not in seen:
            entry = dict(c)
            if c.get("source_type") == "design_team_sponsor" and c.get("team"):
                entry["source_teams"] = [{"team": c["team"], "source_url": c.get("source_url", "")}]
            seen[key] = entry
        else:
            # merge sponsor teams
            if c.get("source_type") == "design_team_sponsor" and c.get("team"):
                existing = seen[key].setdefault("source_teams", [])
                known = {t["team"] for t in existing}
                if c["team"] not in known:
                    existing.append({"team": c["team"], "source_url": c.get("source_url", "")})
    return list(seen.values())


# velocity - scrape with bs4
def extract_velocity(html, source):
    soup = BeautifulSoup(html, "html.parser")
    companies = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/company/" not in href:
            continue
        company_slug = href.rstrip("/").split("/")[-1]
        if company_slug in seen:
            continue
        seen.add(company_slug)
        # try to get the real name from the link text or nearby heading
        name = a.get_text(strip=True) or company_slug.replace("-", " ").title()
        if not name or len(name) < 2:
            name = company_slug.replace("-", " ").title()
        companies.append({
            "name": name,
            "url": f"https://velocityincubator.com{href}" if href.startswith("/") else href,
            "source_url": source["url"],
            "source_type": source["type"],
            "team": None,
        })
    return companies


def gather():
    data_dir.mkdir(exist_ok=True)

    with open(sources_file) as f:
        sources = json.load(f)

    all_companies = []
    if out_file.exists():
        with open(out_file) as f:
            all_companies = json.load(f)
        print(f"loaded {len(all_companies)} existing companies")

    for src in sources:
        print(f"fetching {src['url']}...")

        if src["type"] == "velocity_startup":
            try:
                html = fetch_page(src["url"])
            except Exception as e:
                print(f"  skip: {e}")
                continue
            print(f"  parsing velocity with bs4...")
            companies = extract_velocity(html, src)

        else:
            # engineering competition sponsors and similar — bs4 extraction
            try:
                html = fetch_page(src["url"])
            except Exception as e:
                print(f"  skip: {e}")
                continue
            print(f"  extracting sponsors with bs4...")
            companies = extract_sponsors_bs4(html, src)
            time.sleep(1)

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
    if cmd == "all":
        discover_teams()
        find_sponsor_pages()
        gather_from_teams()
        gather_seeds()
        from scraper.wikidata import gather_wikidata, fetch_wikipedia_extracts
        gather_wikidata(out_file)
        fetch_wikipedia_extracts(out_file)
        gather()
    elif cmd == "discover":
        discover_teams()
    elif cmd == "find_sponsors":
        find_sponsor_pages()
    elif cmd == "scrape_teams":
        gather_from_teams()
    elif cmd == "seeds":
        gather_seeds()
    elif cmd == "wikidata":
        from scraper.wikidata import gather_wikidata
        gather_wikidata(out_file)
    elif cmd == "wiki_extracts":
        from scraper.wikidata import fetch_wikipedia_extracts
        fetch_wikipedia_extracts(out_file)
    elif cmd == "reset_team" and len(sys.argv) > 2:
        team_name = " ".join(sys.argv[2:]).lower()
        if teams_scraped_file.exists():
            lines = teams_scraped_file.read_text().splitlines()
            kept = [l for l in lines if l.lower() != team_name]
            removed = len(lines) - len(kept)
            teams_scraped_file.write_text("\n".join(kept) + ("\n" if kept else ""))
            print(f"removed {removed} entry(s) for '{team_name}'")
    else:
        gather()
