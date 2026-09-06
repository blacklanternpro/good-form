"""Host normalization, aggregator blacklist, and whitelist ranking."""

from __future__ import annotations

from urllib.parse import urlparse

# Suffix match: host == suffix or host.endswith("." + suffix).
# Do not put tumblr.com here — subdomains are favored; only the apex is blocked.
BLOCKED_SUFFIXES: tuple[str, ...] = (
    "pinterest.com",
    "pinterest.co.uk",
    "pinimg.com",
    "amazon.com",
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.ca",
    "amazon.co.jp",
    "amazon.es",
    "amazon.it",
    "amazon.com.au",
    "amzn.to",
    "ebay.com",
    "ebay.co.uk",
    "shutterstock.com",
    "gettyimages.com",
    "gettyimages.co.uk",
    "etsy.com",
    "reddit.com",
    "redd.it",
    "instagram.com",
    "facebook.com",
    "fb.com",
    "fbcdn.net",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "t.co",
    "youtube.com",
    "youtu.be",
    "google.com",
    "googleusercontent.com",
    "gstatic.com",
    "googleapis.com",
    "wikipedia.org",
    "wikimedia.org",
    "unsplash.com",
    "adobe.com",
    "adobestock.com",
    "alamy.com",
    "flickr.com",
    "staticflickr.com",
    "nytimes.com",
    "cnn.com",
    "bbc.com",
    "bbc.co.uk",
    "theguardian.com",
    "reuters.com",
    "washingtonpost.com",
    "foxnews.com",
    "msn.com",
    "yahoo.com",
    "yimg.com",
)

EXACT_BLOCKED = frozenset({"tumblr.com"})


def normalize_host(url_or_host: str | None) -> str | None:
    if not url_or_host:
        return None
    raw = url_or_host.strip()
    if not raw:
        return None
    if "://" not in raw and "/" not in raw and " " not in raw:
        host = raw
    else:
        if "://" not in raw:
            raw = "http://" + raw
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https"):
            return None
        host = parsed.hostname or ""
    host = host.lower().removeprefix("www.")
    if not host or "." not in host:
        return None
    return host


def is_blacklisted(host: str | None) -> bool:
    if not host:
        return True
    h = host.lower().removeprefix("www.")
    if h in EXACT_BLOCKED:
        return True
    for suffix in BLOCKED_SUFFIXES:
        if h == suffix or h.endswith("." + suffix):
            return True
    return False


def whitelist_bias(host: str | None) -> int:
    """Higher scores are preferred when ranking newly discovered peers."""
    if not host:
        return 0
    h = host.lower().removeprefix("www.")
    if h.endswith(".tumblr.com") and h != "tumblr.com":
        return 3
    if h == "are.na" or h.endswith(".are.na"):
        return 3
    if h.endswith(".neocities.org"):
        return 3
    if h.endswith(".substack.com") or h == "substack.com":
        return 2
    if h.endswith(".github.io"):
        return 2
    return 0


def accept_url(url: str | None) -> str | None:
    """Return the normalized host if this URL may be stored as a source."""
    host = normalize_host(url)
    if not host or is_blacklisted(host):
        return None
    return host
