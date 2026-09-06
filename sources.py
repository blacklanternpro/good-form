"""Seed ingest, SerpApi Google Lens discovery, Visual Hop, and insert path."""

from __future__ import annotations

import io
from pathlib import Path

import requests
from PIL import Image

import db
import jobs
from categorizer import tag_text
from config import (
    HOP_IMAGE_CAP,
    SERPAPI_IMAGE_URL,
    SERPAPI_MAX_BYTES,
    SERPAPI_SEARCH_URL,
    REQUEST_TIMEOUT,
    USER_AGENT,
    seed_dir,
    serpapi_key,
)
from fallback import (
    build_queries,
    filter_hits,
    search_web,
    tokenize_filename,
    tokenize_path,
)
from policy import accept_url, whitelist_bias

SEED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class SerpApiError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def list_seed_files(directory: Path | None = None) -> list[Path]:
    folder = directory or seed_dir()
    if not folder.is_dir():
        return []
    files = [
        path
        for path in sorted(folder.iterdir())
        if path.is_file() and path.suffix.lower() in SEED_SUFFIXES
    ]
    return files


def compress_for_serpapi(src: Path) -> bytes:
    with Image.open(src) as original:
        image = original.convert("RGB")
        width, height = image.size
        quality = 85
        while True:
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) <= SERPAPI_MAX_BYTES:
                return data
            if width < 160 and quality <= 35:
                return data
            width = max(1, int(width * 0.8))
            height = max(1, int(height * 0.8))
            image = image.resize((width, height), Image.Resampling.LANCZOS)
            quality = max(35, quality - 10)


def lens_search_bytes(image_bytes: bytes) -> list[dict[str, str]]:
    key = serpapi_key()
    if not key:
        raise SerpApiError("missing SERPAPI_API_KEY", 401)
    upload = requests.post(
        SERPAPI_IMAGE_URL,
        files={"image": ("seed.jpg", image_bytes, "image/jpeg")},
        data={"api_key": key},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    if upload.status_code in (401, 402, 403, 429) or upload.status_code >= 500:
        raise SerpApiError(upload.text[:240], upload.status_code)
    try:
        uploaded = upload.json()
    except ValueError as exc:
        raise SerpApiError("invalid upload response", upload.status_code) from exc
    if uploaded.get("error"):
        raise SerpApiError(str(uploaded["error"]), upload.status_code)
    image_id = uploaded.get("image_id")
    if not image_id:
        raise SerpApiError("upload missing image_id", upload.status_code)
    search = requests.get(
        SERPAPI_SEARCH_URL,
        params={
            "engine": "google_lens",
            "image_id": image_id,
            "type": "visual_matches",
            "api_key": key,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT + 20,
    )
    if search.status_code in (401, 402, 403, 429) or search.status_code >= 500:
        raise SerpApiError(search.text[:240], search.status_code)
    try:
        payload = search.json()
    except ValueError as exc:
        raise SerpApiError("invalid lens response", search.status_code) from exc
    if payload.get("error"):
        raise SerpApiError(str(payload["error"]), search.status_code)
    hits: list[dict[str, str]] = []
    for match in payload.get("visual_matches") or []:
        url = match.get("link") or ""
        if not url:
            continue
        hits.append(
            {
                "title": match.get("title") or match.get("source") or url,
                "url": url,
                "snippet": match.get("source") or "",
            }
        )
    return hits


def ingest_hit(
    url: str,
    title: str | None,
    *,
    from_source_id: int | None = None,
    via_type: str | None = None,
    via_url: str | None = None,
    via_image_id: int | None = None,
) -> int | None:
    host = accept_url(url)
    if not host:
        return None
    existing = db.get_source_by_domain(host)
    if existing:
        source_id = int(existing["id"])
        if from_source_id and via_type:
            db.add_edge(from_source_id, source_id, via_type, via_url=via_url, via_image_id=via_image_id)
        return source_id
    tags = tag_text(title, url, host)
    source_id = db.insert_source(domain=host, title=title or host, sample_url=url)
    db.set_tags(source_id, tags)
    if from_source_id and via_type:
        db.add_edge(from_source_id, source_id, via_type, via_url=via_url, via_image_id=via_image_id)
    return source_id


def ingest_hits(hits: list[dict[str, str]], log=None, **edge_kwargs) -> int:
    ranked = sorted(
        hits,
        key=lambda hit: (
            -whitelist_bias(accept_url(hit.get("url") or "") or ""),
            hit.get("url") or "",
        ),
    )
    inserted = 0
    for hit in ranked:
        url = hit.get("url") or ""
        before = db.get_source_by_domain(accept_url(url) or "")
        source_id = ingest_hit(url, hit.get("title"), **edge_kwargs)
        if source_id and before is None:
            inserted += 1
            if log:
                log(f"added {accept_url(url)}")
    return inserted


def run_discover(
    job_id: int,
    *,
    lens_search=None,
    web_search=None,
    seeds: list[Path] | None = None,
) -> None:
    db.init_db()
    lens_search = lens_search or (lambda data: lens_search_bytes(data))
    web_search = web_search or search_web
    files = seeds if seeds is not None else list_seed_files()
    if not files:
        jobs.log(job_id, "No images in seed_images/", status="No images in seed_images/")
        return

    hits: list[dict[str, str]] = []
    lens_ok = bool(serpapi_key())
    if not lens_ok:
        jobs.log(
            job_id,
            "Lens skipped (no SERPAPI_API_KEY); discovering via text search",
            status="Lens skipped (no SERPAPI_API_KEY); discovering via text search",
        )

    for path in files:
        if not lens_ok:
            break
        try:
            jobs.log(job_id, f"Lens {path.name}")
            payload = compress_for_serpapi(path)
            hits.extend(lens_search(payload))
        except SerpApiError as exc:
            lens_ok = False
            status_bit = exc.status if exc.status is not None else "error"
            jobs.log(
                job_id,
                f"SerpApi unavailable ({status_bit}); discovering via text search",
                status=f"SerpApi unavailable ({status_bit}); discovering via text search",
            )
            jobs.log(job_id, str(exc))
            break

    used_fallback = not lens_ok
    if used_fallback:
        tokens: list[str] = []
        for path in files:
            tokens.extend(tokenize_filename(path.name))
        queries = build_queries(tokens, db.all_tags())
        if not queries:
            queries = build_queries(tokens, ["archive", "zine"])
        web_hits: list[dict[str, str]] = []
        last_error: Exception | None = None
        for query in queries:
            try:
                jobs.log(job_id, f"search {query}")
                web_hits.extend(web_search(query))
            except Exception as exc:
                last_error = exc
                jobs.log(job_id, f"search failed: {exc}")
        filtered = filter_hits(web_hits)
        hits.extend(filtered)
        if not hits:
            detail = f" ({last_error})" if last_error else ""
            db.finish_job(job_id, "error", f"Lens and text fallback found nothing{detail}")
            return

    added = ingest_hits(hits, log=lambda line: jobs.log(job_id, line))
    jobs.log(job_id, f"Discover added {added} source(s)", status=f"Discover added {added} source(s)")


def _text_hop_queries(image: dict) -> list[str]:
    source = db.get_source(int(image["source_id"])) or {}
    tags = db.source_tags(int(image["source_id"]))
    extras = tokenize_path(image.get("origin_url") or source.get("sample_url") or "")
    tokens = tokenize_filename(source.get("title") or source.get("domain") or "")
    return build_queries(tokens, tags, extras)


def run_hop(
    job_id: int,
    *,
    lens_search=None,
    web_search=None,
    cap: int | None = None,
) -> None:
    db.init_db()
    lens_search = lens_search or (lambda data: lens_search_bytes(data))
    web_search = web_search or search_web
    limit = cap if cap is not None else HOP_IMAGE_CAP
    hof_tags = db.hall_of_fame_tags()
    candidates = db.hop_candidates(limit, hof_tags=hof_tags)
    if not candidates:
        jobs.log(job_id, "No unsaved cached images to hop from", status="No unsaved cached images to hop from")
        return

    lens_ok = bool(serpapi_key())
    if not lens_ok:
        jobs.log(
            job_id,
            "Lens skipped (no SERPAPI_API_KEY); text hop",
            status="Lens skipped (no SERPAPI_API_KEY); text hop",
        )

    added_total = 0
    for image in candidates:
        via_type = "image_lens"
        hop_hits: list[dict[str, str]] = []
        cache = Path(image["cache_path"])
        if lens_ok and cache.is_file():
            try:
                jobs.log(job_id, f"Lens hop {image['domain']} #{image['id']}")
                hop_hits = lens_search(compress_for_serpapi(cache))
            except SerpApiError as exc:
                lens_ok = False
                status_bit = exc.status if exc.status is not None else "error"
                jobs.log(
                    job_id,
                    f"SerpApi unavailable ({status_bit}); text hop",
                    status=f"SerpApi unavailable ({status_bit}); text hop",
                )
        if not lens_ok:
            via_type = "text_search"
            queries = _text_hop_queries(image)
            for query in queries:
                try:
                    hop_hits.extend(web_search(query))
                except Exception as exc:
                    jobs.log(job_id, f"text hop search failed: {exc}")
            hop_hits = filter_hits(hop_hits)
        added = ingest_hits(
            hop_hits,
            log=lambda line: jobs.log(job_id, line),
            from_source_id=int(image["source_id"]),
            via_type=via_type,
            via_url=image.get("origin_url"),
            via_image_id=int(image["id"]),
        )
        db.mark_hopped(int(image["id"]))
        added_total += added
        jobs.log(job_id, f"hop via {via_type} added {added} from {image['domain']}")

    jobs.log(
        job_id,
        f"Visual Hop added {added_total} source(s) (depth 1)",
        status=f"Visual Hop added {added_total} source(s) (depth 1)",
    )
