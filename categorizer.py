"""Heuristic multi-tag assignment from titles, URLs, and hostnames."""

from __future__ import annotations

import re

TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "geocities": ("geocities",),
    "neocities": ("neocities",),
    "brutalist": ("brutalist", "brutalism"),
    "vaporwave": ("vaporwave", "vapor wave", "mallsoft"),
    "y2k": ("y2k",),
    "webcore": ("webcore", "weirdcore"),
    "zine": ("zine", "fanzine"),
    "scan": ("scan", "scanned", "scanner"),
    "collage": ("collage",),
    "analog": ("analog", "analogue", "35mm"),
    "diary": ("diary", "journal"),
    "archive": ("archive", "archives"),
    "tumblr": ("tumblr",),
    "substack": ("substack",),
    "arena": ("are.na",),
    "photography": ("photography", "photographer"),
    "illustration": ("illustration", "illustrator"),
    "fashion": ("fashion",),
    "vintage": ("vintage", "retro"),
    "cyber": ("cyberpunk", "cyber"),
    "gothic": ("gothic", "goth"),
    "cottage": ("cottagecore", "cottage"),
}


def _has_keyword(blob: str, keyword: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, blob) is not None


def tag_text(*parts: str | None) -> list[str]:
    blob = " ".join(p or "" for p in parts).lower()
    tags: list[str] = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(_has_keyword(blob, kw) for kw in keywords):
            tags.append(tag)
    return tags or ["Unsorted"]
