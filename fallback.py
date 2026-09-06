"""Text-search fallback when SerpApi Google Lens is unavailable.

Provider order: Brave Search (if keyed) then DuckDuckGo HTML.
This is not reverse-image search.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from config import BRAVE_SEARCH_URL, DDG_HTML_URL, REQUEST_TIMEOUT, USER_AGENT, brave_key
from policy import accept_url

QUERY_MINUS = "-pinterest -etsy -shutterstock -amazon -reddit"
QUERY_TEMPLATES = (
    "{term} personal blog",
    "{term} zine archive",
    "site:tumblr.com {term}",
)


class FallbackError(Exception):
    """Both web providers failed or returned nothing usable."""


def tokenize_filename(name: str) -> list[str]:
    stem = Path(name).stem
    parts = re.split(r"[^a-zA-Z0-9]+", stem)
    return [p.lower() for p in parts if len(p) > 2]


def build_queries(tokens: list[str], tags: list[str], extra: list[str] | None = None) -> list[str]:
    terms: list[str] = []
    for tag in tags:
        if tag and tag != "Unsorted" and tag not in terms:
            terms.append(tag)
    for token in list(tokens) + list(extra or []):
        cleaned = token.lower().strip()
        if len(cleaned) > 2 and cleaned not in terms and cleaned != "unsorted":
            terms.append(cleaned)
    terms = terms[:8]
    queries: list[str] = []
    seen: set[str] = set()
    for term in terms[:5]:
        for template in QUERY_TEMPLATES:
            query = f"{template.format(term=term)} {QUERY_MINUS}"
            if query not in seen:
                seen.add(query)
                queries.append(query)
    return queries[:12]


def unwrap_ddg_href(href: str | None) -> str | None:
    if not href:
        return None
    parsed = urlparse(href)
    query = parse_qs(parsed.query)
    if "uddg" in query:
        return unquote(query["uddg"][0])
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return None


def parse_ddg_html(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    hits: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a.result__a"):
        url = unwrap_ddg_href(anchor.get("href"))
        title = anchor.get_text(" ", strip=True)
        if not url or url in seen:
            continue
        snippet = ""
        parent = anchor.find_parent("div", class_="result")
        if parent:
            snip_el = parent.select_one(".result__snippet")
            if snip_el:
                snippet = snip_el.get_text(" ", strip=True)
        seen.add(url)
        hits.append({"title": title or url, "url": url, "snippet": snippet})
    return hits


def brave_search(query: str) -> list[dict[str, str]]:
    key = brave_key()
    if not key:
        return []
    response = requests.get(
        BRAVE_SEARCH_URL,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": key,
            "User-Agent": USER_AGENT,
        },
        params={"q": query, "count": 20},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    results = (payload.get("web") or {}).get("results") or []
    hits: list[dict[str, str]] = []
    for item in results:
        url = item.get("url") or ""
        if not url:
            continue
        hits.append(
            {
                "title": item.get("title") or url,
                "url": url,
                "snippet": item.get("description") or "",
            }
        )
    return hits


def ddg_search(query: str, fetch_html=None) -> list[dict[str, str]]:
    if fetch_html is None:
        response = requests.post(
            DDG_HTML_URL,
            data={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        html = response.text
    else:
        html = fetch_html(query)
    return parse_ddg_html(html)


def search_web(query: str, *, brave_fn=None, ddg_fn=None) -> list[dict[str, str]]:
    """Brave if keyed and successful, else DuckDuckGo HTML."""
    brave_fn = brave_fn or brave_search
    ddg_fn = ddg_fn or ddg_search
    if brave_key():
        try:
            hits = brave_fn(query)
            if hits:
                return hits
        except Exception:
            pass
    return ddg_fn(query)


def filter_hits(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    kept: list[dict[str, str]] = []
    seen_hosts: set[str] = set()
    for hit in hits:
        url = hit.get("url") or ""
        host = accept_url(url)
        if not host or host in seen_hosts:
            continue
        seen_hosts.add(host)
        kept.append({**hit, "host": host})
    kept.sort(key=lambda h: (0 if _bias(h["host"]) else 1, h["host"]))
    return kept


def _bias(host: str) -> int:
    from policy import whitelist_bias

    return whitelist_bias(host)


def tokenize_path(url: str) -> list[str]:
    path = urlparse(url).path
    parts = re.split(r"[^a-zA-Z0-9]+", path)
    return [p.lower() for p in parts if len(p) > 2]
