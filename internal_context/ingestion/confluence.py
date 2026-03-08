import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from config import CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN
from internal_context.models import Chunk
from internal_context.chunking.chunker import chunk_text


def parse_space_url(url: str) -> tuple[str, str] | tuple[None, None]:
    # https://team.atlassian.net/wiki/spaces/SPACEKEY
    parsed = urlparse(url.rstrip("/"))
    parts = parsed.path.split("/")
    try:
        idx = parts.index("spaces")
        space_key = parts[idx + 1]
        base = f"{parsed.scheme}://{parsed.netloc}"
        return base, space_key
    except (ValueError, IndexError):
        return None, None


def get_all_pages(base: str, space_key: str) -> list[dict]:
    """paginate through all pages in a space"""
    auth = (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN)
    pages = []
    start = 0
    limit = 50

    while True:
        res = httpx.get(
            f"{base}/wiki/rest/api/content",
            auth=auth,
            params={"spaceKey": space_key, "type": "page", "limit": limit, "start": start},
            timeout=15,
        )
        if res.status_code != 200:
            print(f"confluence api returned {res.status_code} for space {space_key}")
            break

        data = res.json()
        results = data.get("results", [])
        for p in results:
            pages.append({
                "id": p["id"],
                "title": p["title"],
                "webui": p.get("_links", {}).get("webui", ""),
            })

        if len(results) < limit:
            break
        start += limit

    print(f"found {len(pages)} pages in confluence space {space_key}")
    return pages

def fetch_page_text(base: str, page_id: str) -> str | None:
    auth = (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN)
    res = httpx.get(
        f"{base}/wiki/rest/api/content/{page_id}",
        auth=auth,
        params={"expand": "body.storage"},
        timeout=15,
    )
    if res.status_code != 200:
        print(f"failed to fetch confluence page {page_id}: {res.status_code}")
        return None

    html = res.json().get("body", {}).get("storage", {}).get("value", "")
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["ac:structured-macro", "ac:parameter"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    lines = [l for l in text.splitlines() if len(l.split()) > 3]
    return "\n".join(lines)


def scrape_confluence(space_url: str, team_name: str) -> list[Chunk]:
    base, space_key = parse_space_url(space_url)
    if not base or not space_key:
        print(f"couldn't parse confluence space url: {space_url}")
        return []

    print(f"scraping confluence space {space_key} at {base}")
    pages = get_all_pages(base, space_key)
    chunks = []

    for page in pages:
        text = fetch_page_text(base, page["id"])
        if not text or not text.strip():
            continue
        page_url = f"{base}/wiki{page['webui']}" if page["webui"] else space_url
        chunks.extend(chunk_text(text, team_name, "confluence", page_url))

    print(f"got {len(chunks)} chunks from confluence space {space_key}")
    return chunks