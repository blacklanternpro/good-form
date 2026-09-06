"""Runtime configuration. Paths and keys are read from the environment so tests can isolate data."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

USER_AGENT = "good-form/0.1 (local curator; +http://127.0.0.1:8000)"
REQUEST_TIMEOUT = 12
SERPAPI_MAX_BYTES = 500 * 1024
MIN_SHORT_EDGE = 400
MAX_ASPECT = 3.0
MINE_DOMAIN_CAP = 40
SCRAPE_SOURCE_CAP = 30
HOP_IMAGE_CAP = 5
GRID_LIMIT = 400
SERPAPI_IMAGE_URL = "https://serpapi.com/image"
SERPAPI_SEARCH_URL = "https://serpapi.com/search"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
DDG_HTML_URL = "https://html.duckduckgo.com/html/"


def seed_dir() -> Path:
    return Path(os.environ.get("GOODFORM_SEED", str(ROOT / "seed_images")))


def cache_dir() -> Path:
    return Path(os.environ.get("GOODFORM_CACHE", str(ROOT / "scraped_cache")))


def db_path() -> Path:
    return Path(os.environ.get("GOODFORM_DB", str(ROOT / "data" / "goodform.db")))


def request_delay() -> float:
    return float(os.environ.get("GOODFORM_DELAY", "0.35"))


def serpapi_key() -> str:
    return os.environ.get("SERPAPI_API_KEY", "").strip()


def brave_key() -> str:
    return os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
