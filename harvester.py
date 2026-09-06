"""RSS/Atom auto-discovery and blogroll / webring expansion."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import feedparser
from bs4 import BeautifulSoup

import db
import jobs
from config import MINE_DOMAIN_CAP
from net import fetch
from policy import accept_url
from sources import ingest_hit

FEED_PATHS = ("/feed", "/rss", "/atom.xml", "/index.xml")
ROLL_PATHS = ("/links", "/blogroll", "/blogroll.html")
WEBRING_WORDS = (
    "friends",
    "neighbours",
    "neighbors",
    "blogroll",
    "webring",
    "links",
    "ring",
)


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme:
        return url
    return f"{parsed.scheme}://{parsed.netloc}"


def discover_feed(
    sample_url: str | None,
    domain: str,
    log=None,
    fetch_fn=fetch,
) -> str | None:
    bases = []
    if sample_url:
        bases.append(sample_url)
    bases.append(f"https://{domain}/")
    bases.append(f"http://{domain}/")
    seen: set[str] = set()
    for base in bases:
        if not base or base in seen:
            continue
        seen.add(base)
        html_resp = fetch_fn(base, log=log)
        if html_resp is not None and html_resp.text:
            soup = BeautifulSoup(html_resp.text, "lxml")
            for link in soup.find_all("link"):
                rel = " ".join(link.get("rel") or []).lower()
                typ = (link.get("type") or "").lower()
                href = link.get("href")
                if href and "alternate" in rel and ("rss" in typ or "atom" in typ):
                    feed_url = urljoin(str(html_resp.url), href)
                    if _feed_works(feed_url, fetch_fn=fetch_fn, log=log):
                        return feed_url
        origin = _origin(base)
        for path in FEED_PATHS:
            feed_url = urljoin(origin + "/", path.lstrip("/"))
            if _feed_works(feed_url, fetch_fn=fetch_fn, log=log):
                return feed_url
    return None


def _feed_works(url: str, fetch_fn=fetch, log=None) -> bool:
    response = fetch_fn(url, log=log)
    if response is None or not response.content:
        return False
    parsed = feedparser.parse(response.content)
    return bool(parsed.entries)


def run_discover_feeds(job_id: int, fetch_fn=fetch) -> None:
    db.init_db()
    sources = db.list_enabled_sources()
    found = 0
    for source in sources:
        if source.get("feed_url"):
            continue
        log = lambda line, s=source: jobs.log(job_id, f"{s['domain']}: {line}")
        feed = discover_feed(source.get("sample_url"), source["domain"], log=log, fetch_fn=fetch_fn)
        if feed:
            db.set_feed_url(int(source["id"]), feed)
            found += 1
            jobs.log(job_id, f"feed {source['domain']} -> {feed}")
    jobs.log(job_id, f"Feeds found: {found}", status=f"Feeds found: {found}")


def _collect_hrefs(html: str, page_url: str, homepage: bool) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    pairs: list[tuple[str, str]] = []

    def add(anchor) -> None:
        href = anchor.get("href")
        if not href:
            return
        url = urljoin(page_url, href)
        text = anchor.get_text(" ", strip=True)
        pairs.append((url, text))

    if homepage:
        for footer in soup.find_all("footer"):
            for anchor in footer.find_all("a", href=True):
                add(anchor)
        for anchor in soup.find_all("a", href=True):
            text = (anchor.get_text(" ", strip=True) or "").lower()
            href = (anchor.get("href") or "").lower()
            blob = f"{text} {href}"
            if any(word in blob for word in WEBRING_WORDS):
                add(anchor)
    else:
        for anchor in soup.find_all("a", href=True):
            add(anchor)
    return pairs


def run_mine(job_id: int, fetch_fn=fetch, cap: int | None = None) -> None:
    db.init_db()
    limit = cap if cap is not None else MINE_DOMAIN_CAP
    added = 0
    for source in db.list_enabled_sources():
        if added >= limit:
            break
        domain = source["domain"]
        sample = source.get("sample_url") or f"https://{domain}/"
        pages = [sample]
        origin = _origin(sample)
        for path in ROLL_PATHS:
            pages.append(urljoin(origin + "/", path.lstrip("/")))
        seen_pages: set[str] = set()
        for page in pages:
            if added >= limit:
                break
            if page in seen_pages:
                continue
            seen_pages.add(page)
            response = fetch_fn(page, log=lambda line: jobs.log(job_id, line))
            if response is None or not response.text:
                continue
            homepage = page.rstrip("/") == sample.rstrip("/") or urlparse(page).path in ("", "/")
            for url, text in _collect_hrefs(response.text, str(response.url), homepage=homepage):
                if added >= limit:
                    break
                host = accept_url(url)
                if not host or host == domain:
                    continue
                before = db.get_source_by_domain(host)
                source_id = ingest_hit(
                    url,
                    text or host,
                    from_source_id=int(source["id"]),
                    via_type="link",
                    via_url=str(response.url),
                )
                if source_id and before is None:
                    added += 1
                    jobs.log(job_id, f"mined {host} from {domain}")
    jobs.log(job_id, f"Mine Blogrolls added {added} source(s)", status=f"Mine Blogrolls added {added} source(s)")
