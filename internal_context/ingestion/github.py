import base64
import httpx
from config import GITHUB_TOKEN
from internal_context.models import Chunk
from internal_context.chunking.chunker import chunk_text

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}


def parse_org(org_url: str) -> str:
    # handles trailing slash too
    return org_url.rstrip("/").split("/")[-1]


def scrape_github(org_url: str, team_name: str) -> list[Chunk]:
    org = parse_org(org_url)
    print(f"scraping github org: {org}")

    # TODO
    return []
