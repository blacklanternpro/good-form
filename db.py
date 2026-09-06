"""SQLite schema and helpers."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config import cache_dir, db_path, seed_dir


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    seed_dir().mkdir(parents=True, exist_ok=True)
    cache_dir().mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL UNIQUE,
                title TEXT,
                sample_url TEXT,
                feed_url TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                enabled INTEGER NOT NULL DEFAULT 1,
                downloads_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_tags (
                source_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (source_id, tag),
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                image_url TEXT NOT NULL UNIQUE,
                cache_path TEXT,
                width INTEGER,
                height INTEGER,
                origin_url TEXT,
                saved_count INTEGER NOT NULL DEFAULT 0,
                hopped_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS expansion_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_source_id INTEGER NOT NULL,
                to_source_id INTEGER NOT NULL,
                via_type TEXT NOT NULL,
                via_url TEXT,
                via_image_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (from_source_id) REFERENCES sources(id) ON DELETE CASCADE,
                FOREIGN KEY (to_source_id) REFERENCES sources(id) ON DELETE CASCADE,
                FOREIGN KEY (via_image_id) REFERENCES images(id) ON DELETE SET NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS expansion_edges_uniq
                ON expansion_edges(
                    from_source_id,
                    to_source_id,
                    via_type,
                    ifnull(via_image_id, 0)
                );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                log TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT
            );
            """
        )


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def insert_source(
    domain: str,
    title: str | None,
    sample_url: str | None,
    status: str = "active",
    feed_url: str | None = None,
) -> int:
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO sources (domain, title, sample_url, feed_url, status, enabled, downloads_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?)
            """,
            (domain, title, sample_url, feed_url, status, ts, ts),
        )
        return int(cur.lastrowid)


def get_source_by_domain(domain: str) -> dict[str, Any] | None:
    with connect() as conn:
        return _row(conn.execute("SELECT * FROM sources WHERE domain = ?", (domain,)).fetchone())


def get_source(source_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        return _row(conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone())


def set_tags(source_id: int, tags: Iterable[str]) -> None:
    unique = list(dict.fromkeys(tags))
    with connect() as conn:
        conn.execute("DELETE FROM source_tags WHERE source_id = ?", (source_id,))
        conn.executemany(
            "INSERT INTO source_tags (source_id, tag) VALUES (?, ?)",
            [(source_id, tag) for tag in unique],
        )


def add_tags(source_id: int, tags: Iterable[str]) -> None:
    with connect() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO source_tags (source_id, tag) VALUES (?, ?)",
            [(source_id, tag) for tag in tags],
        )


def source_tags(source_id: int) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT tag FROM source_tags WHERE source_id = ? ORDER BY tag",
            (source_id,),
        ).fetchall()
        return [r["tag"] for r in rows]


def all_tags() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT tag FROM source_tags ORDER BY tag"
        ).fetchall()
        return [r["tag"] for r in rows]


def list_enabled_sources() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sources WHERE enabled = 1 ORDER BY domain"
        ).fetchall()
        return [dict(r) for r in rows]


def list_sources() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM sources ORDER BY domain").fetchall()
        return [dict(r) for r in rows]


def sources_grouped_by_tag() -> list[tuple[str, list[dict[str, Any]]]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT t.tag, s.*
            FROM source_tags t
            JOIN sources s ON s.id = t.source_id
            ORDER BY CASE WHEN t.tag = 'Unsorted' THEN 1 ELSE 0 END, t.tag, s.domain
            """
        ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for row in rows:
        tag = row["tag"]
        if tag not in grouped:
            grouped[tag] = []
            order.append(tag)
        grouped[tag].append(dict(row))
    return [(tag, grouped[tag]) for tag in order]


def set_enabled(source_id: int, enabled: bool) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE sources SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, now_iso(), source_id),
        )


def set_feed_url(source_id: int, feed_url: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE sources SET feed_url = ?, updated_at = ? WHERE id = ?",
            (feed_url, now_iso(), source_id),
        )


def set_source_status(source_id: int, status: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE sources SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), source_id),
        )


def hall_of_fame(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT domain, downloads_count
            FROM sources
            WHERE downloads_count > 0
            ORDER BY downloads_count DESC, domain ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def hall_of_fame_tags() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT t.tag
            FROM source_tags t
            JOIN sources s ON s.id = t.source_id
            WHERE s.downloads_count > 0
            """
        ).fetchall()
        return [r["tag"] for r in rows]


def insert_image(
    source_id: int,
    image_url: str,
    cache_path: str,
    width: int,
    height: int,
    origin_url: str | None,
) -> int | None:
    ts = now_iso()
    with connect() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO images (source_id, image_url, cache_path, width, height, origin_url, saved_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (source_id, image_url, cache_path, width, height, origin_url, ts),
            )
            return int(cur.lastrowid)
        except sqlite3.IntegrityError:
            return None


def get_image(image_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        return _row(
            conn.execute(
                """
                SELECT images.*, sources.domain
                FROM images JOIN sources ON sources.id = images.source_id
                WHERE images.id = ?
                """,
                (image_id,),
            ).fetchone()
        )


def get_image_by_url(image_url: str) -> dict[str, Any] | None:
    with connect() as conn:
        return _row(conn.execute("SELECT * FROM images WHERE image_url = ?", (image_url,)).fetchone())


def list_images(limit: int = 400) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT images.*, sources.domain
            FROM images JOIN sources ON sources.id = images.source_id
            ORDER BY images.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_hopped(image_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE images SET hopped_at = ? WHERE id = ?",
            (now_iso(), image_id),
        )


def add_edge(
    from_source_id: int,
    to_source_id: int,
    via_type: str,
    via_url: str | None = None,
    via_image_id: int | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO expansion_edges
                (from_source_id, to_source_id, via_type, via_url, via_image_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (from_source_id, to_source_id, via_type, via_url, via_image_id, now_iso()),
        )


def list_edges() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM expansion_edges").fetchall()
        return [dict(r) for r in rows]


def hop_candidates(limit: int, hof_tags: list[str] | None = None) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT images.*, sources.domain, sources.downloads_count AS source_downloads,
                   sources.enabled AS source_enabled
            FROM images
            JOIN sources ON sources.id = images.source_id
            WHERE images.cache_path IS NOT NULL
              AND images.cache_path != ''
              AND images.saved_count = 0
              AND images.hopped_at IS NULL
              AND sources.enabled = 1
            """
        ).fetchall()
    items = [dict(r) for r in rows]
    hof = set(hof_tags or [])

    def short_edge(item: dict[str, Any]) -> int:
        w = int(item.get("width") or 0)
        h = int(item.get("height") or 0)
        return min(w, h) if w and h else 0

    def overlap(item: dict[str, Any]) -> int:
        if not hof:
            return 0
        tags = set(source_tags(int(item["source_id"])))
        return len(tags & hof)

    items.sort(
        key=lambda item: (
            int(item.get("source_downloads") or 0),
            -overlap(item),
            -short_edge(item),
            int(item["id"]),
        )
    )
    return items[:limit]


def record_downloads(image_ids: list[int]) -> int:
    """Increment saved_count and parent downloads_count for each image. Returns count updated."""
    if not image_ids:
        return 0
    updated = 0
    with connect() as conn:
        for image_id in image_ids:
            row = conn.execute(
                "SELECT id, source_id FROM images WHERE id = ?",
                (image_id,),
            ).fetchone()
            if row is None:
                continue
            conn.execute(
                "UPDATE images SET saved_count = saved_count + 1 WHERE id = ?",
                (image_id,),
            )
            conn.execute(
                """
                UPDATE sources
                SET downloads_count = downloads_count + 1, updated_at = ?
                WHERE id = ?
                """,
                (now_iso(), row["source_id"]),
            )
            updated += 1
    return updated


def create_job(kind: str) -> int:
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (kind, status, message, log, started_at)
            VALUES (?, 'running', ?, '', ?)
            """,
            (kind, f"Starting {kind}…", ts),
        )
        return int(cur.lastrowid)


def get_job(job_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        return _row(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def append_job_log(job_id: int, line: str, message: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET log = COALESCE(log, '') || ? || char(10),
                message = COALESCE(?, message)
            WHERE id = ?
            """,
            (line, message or line, job_id),
        )


def finish_job(job_id: int, status: str, message: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, message = COALESCE(?, message), finished_at = ?
            WHERE id = ?
            """,
            (status, message, now_iso(), job_id),
        )


def cache_path_for(domain: str, digest: str, ext: str) -> Path:
    folder = cache_dir() / domain
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{digest}{ext}"
