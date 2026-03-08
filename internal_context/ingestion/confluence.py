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
