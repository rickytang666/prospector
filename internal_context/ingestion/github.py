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


def list_repos(org: str) -> list[str]:
    """get all non-fork, non-archived repo names in the org"""
    repos = []
    page = 1
    while True:
        res = httpx.get(
            f"https://api.github.com/orgs/{org}/repos",
            headers=HEADERS,
            params={"per_page": 100, "page": page},
        )
        if res.status_code != 200:
            print(f"failed to list repos for {org}: {res.status_code}")
            break
        data = res.json()
        if not data:
            break
        for repo in data:
            if not repo["fork"] and not repo["archived"]:
                repos.append(repo["name"])
        page += 1
    print(f"found {len(repos)} repos in {org}")
    return repos


def scrape_github(org_url: str, team_name: str) -> list[Chunk]:
    org = parse_org(org_url)
    print(f"scraping github org: {org}")

    repos = list_repos(org)
    chunks = []

    # TODO

    return chunks
