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

    for repo in repos:
        chunks.extend(fetch_readme(org, repo, team_name))
        chunks.extend(fetch_issues(org, repo, team_name))

    # TODO: docs

    return chunks


def fetch_issues(org: str, repo: str, team_name: str) -> list[Chunk]:
    chunks = []
    page = 1
    while True:
        res = httpx.get(
            f"https://api.github.com/repos/{org}/{repo}/issues",
            headers=HEADERS,
            params={"state": "open", "per_page": 100, "page": page},
        )
        if res.status_code != 200:
            print(f"failed to fetch issues for {org}/{repo}: {res.status_code}")
            break
        data = res.json()
        if not data:
            break
        for issue in data:
            body = issue.get("body") or ""
            if not body.strip():
                continue
            if "pull_request" in issue:
                continue
            chunks.append(Chunk(
                team_name=team_name,
                source_type="github_issue",
                source_url=issue["html_url"],
                content=f"{issue['title']}\n\n{body}",
            ))
        page += 1
    return chunks


def fetch_readme(org: str, repo: str, team_name: str) -> list[Chunk]:
    res = httpx.get(
        f"https://api.github.com/repos/{org}/{repo}/readme",
        headers=HEADERS,
    )
    if res.status_code == 404:
        return []
    if res.status_code != 200:
        print(f"failed to fetch readme for {org}/{repo}: {res.status_code}")
        return []

    data = res.json()
    text = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    url = data["html_url"]
    return chunk_text(text, team_name, "github_readme", url)
