import httpx
from bs4 import BeautifulSoup


def fetch_page(url: str) -> str:
    res = httpx.get(url, follow_redirects=True, timeout=10)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    for tag in soup(["nav", "footer", "header", "script", "style"]):
        tag.decompose()

    return soup.get_text(separator="\n", strip=True)
