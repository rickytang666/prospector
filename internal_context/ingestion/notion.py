import re
import httpx
from config import NOTION_TOKEN
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

BLOCK_TYPES = {
    "text", "header", "sub_header", "sub_sub_header",
    "bulleted_list", "numbered_list", "toggle",
    "quote", "code", "callout",
}

OFFICIAL_TEXT_TYPES = {
    "paragraph", "heading_1", "heading_2", "heading_3",
    "bulleted_list_item", "numbered_list_item", "toggle",
    "quote", "code", "callout",
}


def fetch_official(page_id: str) -> str | None:
    """use official api"""
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
    }
    lines = []
    next_cursor = None

    while True:
        params = {"page_size": 100}
        if next_cursor:
            params["start_cursor"] = next_cursor

        try:
            res = httpx.get(
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                headers=headers,
                params=params,
                timeout=15,
            )
        except Exception as e:
            print(f"official notion request failed: {e}")
            return None

        if res.status_code == 401:
            print("notion token invalid or page not shared with integration")
            return None
        if res.status_code != 200:
            print(f"official notion api returned {res.status_code}")
            return None

        data = res.json()
        for block in data.get("results", []):
            btype = block.get("type")
            if btype not in OFFICIAL_TEXT_TYPES:
                continue
            rich_text = block.get(btype, {}).get("rich_text", [])
            text = "".join(rt.get("plain_text", "") for rt in rich_text)
            if text.strip():
                lines.append(text.strip())

        if not data.get("has_more"):
            break
        next_cursor = data.get("next_cursor")

    return "\n".join(lines) if lines else None


def extract_text_unofficial(blocks: dict) -> str:
    """parse blocks from loadPageChunk response"""
    lines = []
    for block_id, block in blocks.items():
        value = block.get("value", {})
        if value.get("type") not in BLOCK_TYPES:
            continue
        # [[text, annotations], ...] in properties.title
        title = value.get("properties", {}).get("title", [])
        text = "".join(segment[0] for segment in title if isinstance(segment, list))
        if text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


def scrape_notion(page_url: str, team_name: str) -> list[Chunk]:
    page_id = parse_page_id(page_url)
    if not page_id:
        print(f"couldn't parse notion page id from {page_url}")
        return []

    print(f"fetching notion page {page_id}")
    text = None

    # try official api first if token is available
    if NOTION_TOKEN:
        print("trying official notion api...")
        text = fetch_official(page_id)
        if text:
            print("got text from official api")

    # fall back to unofficial
    if not text:
        print("falling back to unofficial notion api...")
        data = load_page_chunk(page_id)
        if data:
            text = extract_text_unofficial(data.get("recordMap", {}).get("block", {}))

    if not text or not text.strip():
        print(f"no text extracted from notion page {page_id}")
        return []

    return chunk_text(text, team_name, "notion", page_url)
