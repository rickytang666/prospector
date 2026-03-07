import httpx
from bs4 import BeautifulSoup


def fetch_page(url: str) -> str:
    res = httpx.get(url, follow_redirects=True, timeout=10)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "lxml")
    for tag in soup(["nav", "footer", "header", "script", "style"]):
        tag.decompose()

    return soup.get_text(separator="\n", strip=True)


def get_sitemap_urls(root: str) -> list[str]:
    """try to grab all urls from sitemap.xml, returns empty list if not found"""
    root = root.rstrip("/")
    try:
        res = httpx.get(f"{root}/sitemap.xml", follow_redirects=True, timeout=10)
        if res.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(res.text, features="xml")
    urls = [loc.text.strip() for loc in soup.find_all("loc")]
    # filter to same domain only
    return [u for u in urls if u.startswith(root)]
