import re
import httpx
from urllib.parse import urlparse

# ordered by likelihood for sponsorship/university outreach
_PREFIXES = [
    # most direct sponsorship / partnership hits
    "sponsorship", "sponsorships", "sponsors", "sponsor",
    "partnerships", "partnership", "collaborate", "collaboration",
    # academic / university programs
    "university", "universities", "academic", "academia",
    "education", "educational", "students", "student",
    "campus", "research", "programs", "grants", "grant",
    # outreach & community
    "outreach", "community", "relations", "devrel",
    "developer-relations", "developer", "evangelism",
    # business development / corp relations
    "bd", "bizdev", "corporate", "corp", "alliances",
    "sales", "business", "support",
    # general contact fallbacks
    "team", "founders", "founder", "general",
    "info", "contact", "hello", "hi", "hey", "inquiries",
    "enquiries", "media", "pr",
]

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# emails to skip — clearly not the right contact
_SKIP_LOCALS = {"noreply", "no-reply", "donotreply", "support", "newsletter",
                "unsubscribe", "abuse", "postmaster", "privacy", "legal", "press"}

_CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us", "/company/contact"]

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; enghacks-bot/1.0)"}


def _extract_domain(url: str) -> str | None:
    try:
        host = urlparse(url).netloc or urlparse(url).path.split("/")[0]
        host = host.lstrip("www.").split(":")[0]
        return host if "." in host else None
    except Exception:
        return None


def _scrape_emails(url: str) -> list[str]:
    try:
        r = httpx.get(url, timeout=8, follow_redirects=True, headers=_HEADERS)
        if r.status_code != 200:
            return []
        emails = _EMAIL_RE.findall(r.text)
        out = []
        for e in emails:
            local = e.split("@")[0].lower()
            # skip images/fonts/css that regex matches (e.g. "x@2x.png")
            if any(e.lower().endswith(ext) for ext in (".png", ".jpg", ".svg", ".woff", ".css", ".js")):
                continue
            if local in _SKIP_LOCALS:
                continue
            out.append(e.lower())
        return out
    except Exception:
        return []


def _check_mx(domain: str) -> bool:
    try:
        import dns.resolver
        dns.resolver.resolve(domain, "MX", lifetime=5)
        return True
    except Exception:
        return False


def find_email(canonical_url: str) -> tuple[str, bool]:
    """returns (email, is_verified).
    is_verified=True means we found it on their actual site.
    is_verified=False means it's a constructed suggestion (MX-validated domain).
    """
    if not canonical_url:
        return "", False

    base = canonical_url.rstrip("/")
    domain = _extract_domain(canonical_url)

    # step 1: scrape contact/about pages
    for path in _CONTACT_PATHS:
        emails = _scrape_emails(base + path)
        if emails:
            # prefer emails on the company's own domain
            if domain:
                own = [e for e in emails if e.endswith(f"@{domain}")]
                if own:
                    return own[0], True
            return emails[0], True

    # also try scraping the homepage itself
    emails = _scrape_emails(base)
    if emails and domain:
        own = [e for e in emails if e.endswith(f"@{domain}")]
        if own:
            return own[0], True

    # step 2: brute force prefixes — only if domain has valid MX
    if domain and _check_mx(domain):
        for prefix in _PREFIXES:
            return f"{prefix}@{domain}", False  # return first, all have same MX validity

    return "", False
