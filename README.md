# good-form

Local visual curator: reverse-search seed images, grow a Yahoo-style directory of niche blogs, scrape candidates, and zip what you keep.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put a `SERPAPI_API_KEY` in `.env` for Google Lens discovery. If it is missing or over quota, Discover and Visual Hop fall back to DuckDuckGo HTML search (optional `BRAVE_SEARCH_API_KEY` is tried first).

Drop reference rasters (jpg/png/webp) in `seed_images/`.

## Run

```bash
uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

- **Discover New Sources** — Lens (or text fallback) from seed images
- **Mine Blogrolls** — follow `/links`, blogrolls, and webring-ish outbound links
- **Scrape Active Feeds** — RSS first, then homepage images; 400px shortest edge, no extreme banners
- **Visual Hop** — Lens (or text hop) on scraped-but-not-saved images from dud domains, one hop
- **Download Selected / All** — zip originals and increment Hall of Fame counts

## Tests

```bash
pytest
```
