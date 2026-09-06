"""Image harvest from feeds or homepages, with visual filters and disk cache."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError

import db
import jobs
from config import MAX_ASPECT, MIN_SHORT_EDGE, SCRAPE_SOURCE_CAP, cache_dir
from net import fetch

REJECT_URL_PARTS = (
    "doubleclick.net",
    "googlesyndication",
    "googleadservices",
    "googletagmanager",
    "google-analytics",
    "scorecardresearch",
    "facebook.com/tr",
    "adsystem",
    "adnxs.com",
    "quantserve",
    "/pixel",
    "spacer.gif",
    "tracking.gif",
    "1x1",
)


def url_is_rejected(url: str | None) -> bool:
    if not url:
        return True
    lowered = url.lower().strip()
    if lowered.startswith("data:"):
        return True
    parsed = urlparse(lowered)
    path = parsed.path or ""
    if path.endswith(".svg") or lowered.endswith(".svg"):
        return True
    if any(part in lowered for part in REJECT_URL_PARTS):
        return True
    return False


def largest_srcset(srcset: str | None) -> str | None:
    if not srcset:
        return None
    best_url = None
    best_w = -1
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        url = bits[0]
        width = 0
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                width = int(bits[1][:-1])
            except ValueError:
                width = 0
        elif len(bits) > 1 and bits[1].endswith("x"):
            try:
                width = int(float(bits[1][:-1]) * 1000)
            except ValueError:
                width = 0
        if width >= best_w:
            best_w = width
            best_url = url
    return best_url


def extract_img_urls(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    found: list[tuple[str, str]] = []
    for img in soup.find_all("img"):
        src = largest_srcset(img.get("srcset")) or img.get("src")
        if not src:
            continue
        url = urljoin(base_url, src)
        if not url_is_rejected(url):
            found.append((url, base_url))
    return found


def images_from_feed(parsed, fallback_origin: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for entry in parsed.entries:
        origin = entry.get("link") or fallback_origin
        for media in entry.get("media_content") or []:
            url = media.get("url")
            if url and not url_is_rejected(url):
                found.append((url, origin))
        for enclosure in entry.get("enclosures") or []:
            href = enclosure.get("href") or enclosure.get("url")
            typ = enclosure.get("type") or ""
            if href and (typ.startswith("image") or not typ) and not url_is_rejected(href):
                found.append((href, origin))
        html_bits = [entry.get("summary") or ""]
        for content in entry.get("content") or []:
            html_bits.append(content.get("value") or "")
        found.extend(extract_img_urls("".join(html_bits), origin))
    return found


def image_passes_bytes(data: bytes, hint_name: str = "image.jpg") -> tuple[bool, int, int]:
    if hint_name.lower().endswith(".svg") or data[:80].lstrip().startswith(b"<svg"):
        return False, 0, 0
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
    except (UnidentifiedImageError, OSError):
        return False, 0, 0
    if min(width, height) < MIN_SHORT_EDGE:
        return False, width, height
    if height == 0 or width == 0:
        return False, width, height
    ratio = width / height
    if ratio > MAX_ASPECT or ratio < (1 / MAX_ASPECT):
        return False, width, height
    return True, width, height


def _ext_for(url: str, content_type: str | None) -> str:
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    if content_type:
        mapping = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        return mapping.get(content_type.split(";")[0].strip(), ".jpg")
    return ".jpg"


def _digest(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def cache_image(domain: str, image_url: str, data: bytes, content_type: str | None) -> Path:
    ext = _ext_for(image_url, content_type)
    path = db.cache_path_for(domain, _digest(image_url), ext)
    path.write_bytes(data)
    return path


def harvest_source(source: dict, log=None, fetch_fn=fetch) -> int:
    added = 0
    pairs: list[tuple[str, str]] = []
    feed_url = source.get("feed_url")
    sample = source.get("sample_url") or f"https://{source['domain']}/"
    if feed_url:
        response = fetch_fn(feed_url, log=log)
        if response is not None and response.content:
            parsed = feedparser.parse(response.content)
            pairs.extend(images_from_feed(parsed, sample))
    if not pairs:
        response = fetch_fn(sample, log=log)
        if response is not None and response.text:
            pairs.extend(extract_img_urls(response.text, str(response.url)))
    seen: set[str] = set()
    for image_url, origin in pairs:
        if image_url in seen:
            continue
        seen.add(image_url)
        if db.get_image_by_url(image_url):
            continue
        response = fetch_fn(image_url, log=log)
        if response is None:
            continue
        data = response.content
        if not data:
            continue
        ok, width, height = image_passes_bytes(data, urlparse(image_url).path)
        if not ok:
            if log:
                log(f"rejected {image_url} ({width}x{height})")
            continue
        path = cache_image(source["domain"], image_url, data, response.headers.get("Content-Type"))
        image_id = db.insert_image(
            int(source["id"]),
            image_url,
            str(path),
            width,
            height,
            origin,
        )
        if image_id:
            added += 1
    return added


def run_scrape(job_id: int, fetch_fn=fetch, cap: int | None = None) -> None:
    db.init_db()
    cache_dir().mkdir(parents=True, exist_ok=True)
    limit = cap if cap is not None else SCRAPE_SOURCE_CAP
    total = 0
    # Prefer discovering feeds first so structured media wins.
    from harvester import discover_feed

    count = 0
    for source in db.list_enabled_sources():
        if count >= limit:
            break
        count += 1
        if not source.get("feed_url"):
            feed = discover_feed(
                source.get("sample_url"),
                source["domain"],
                log=lambda line, d=source["domain"]: jobs.log(job_id, f"{d}: {line}"),
                fetch_fn=fetch_fn,
            )
            if feed:
                db.set_feed_url(int(source["id"]), feed)
                source = {**source, "feed_url": feed}
        added = harvest_source(
            source,
            log=lambda line, d=source["domain"]: jobs.log(job_id, f"{d}: {line}"),
            fetch_fn=fetch_fn,
        )
        total += added
        jobs.log(job_id, f"{source['domain']}: cached {added} image(s)")
    jobs.log(job_id, f"Scrape cached {total} image(s)", status=f"Scrape cached {total} image(s)")
