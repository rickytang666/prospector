import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


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


def get_all_urls(root: str) -> list[str]:
    """try sitemap first, fall back to crawling"""
    urls = get_sitemap_urls(root)
    if urls:
        return urls
    return crawl(root)


def crawl(root: str, max_pages: int = 50) -> list[str]:
    """crawl internal links starting from root, returns list of discovered urls"""
    root = root.rstrip("/")
    domain = urlparse(root).netloc

    visited = set()
    queue = [root]
    found = []

    while queue and len(found) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            res = httpx.get(url, follow_redirects=True, timeout=10)
            if res.status_code != 200:
                continue
        except Exception:
            continue

        found.append(url)
        soup = BeautifulSoup(res.text, "lxml")

        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            parsed = urlparse(href)
            # same domain, skip anchors and non-http
            if parsed.netloc != domain:
                continue
            if parsed.scheme not in ("http", "https"):
                continue
            clean = href.split("#")[0].rstrip("/")
            if clean not in visited and clean not in queue:
                queue.append(clean)

    # print(f"crawled {len(found)} pages from {root}")
    return found
