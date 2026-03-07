import re
import httpx
from internal_context.models import Chunk
from internal_context.chunking.chunker import chunk_text


def parse_page_id(url: str) -> str | None:
    url = url.split("?")[0].rstrip("/")
    segment = url.split("/")[-1]
    raw = segment.replace("-", "")
    match = re.search(r"[0-9a-f]{32}$", raw, re.IGNORECASE)
    if not match:
        return None
    hex_id = match.group(0)
    return f"{hex_id[:8]}-{hex_id[8:12]}-{hex_id[12:16]}-{hex_id[16:20]}-{hex_id[20:]}"


def load_page_chunk(page_id: str) -> dict | None:
    try:
        res = httpx.post(
            "https://www.notion.so/api/v3/loadPageChunk",
            json={
                "pageId": page_id,
                "limit": 100,
                "cursor": {"stack": []},
                "chunkNumber": 0,
                "verticalColumns": False,
            },
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if res.status_code != 200:
            print(f"notion api returned {res.status_code} for page {page_id}")
            return None
        return res.json()
    except Exception as e:
        print(f"failed to fetch notion page {page_id}: {e}")
        return None

def scrape_notion(page_url: str, team_name: str) -> list[Chunk]:
    page_id = parse_page_id(page_url)
    if not page_id:
        print(f"couldn't parse notion page id from {page_url}")
        return []

    print(f"fetching notion page {page_id}")
    data = load_page_chunk(page_id)
    if not data:
        return []

    text = extract_text(data.get("recordMap", {}).get("block", {}))
    if not text.strip():
        print(f"no text extracted from notion page {page_id}")
        return []

    return chunk_text(text, team_name, "notion", page_url)
