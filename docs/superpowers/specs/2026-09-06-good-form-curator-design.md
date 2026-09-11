# good-form: local visual curator

Date: 2026-09-06

> **Precedence — read before implementing anything here.** This is the oldest of the three documents and the lowest in the ladder:
>
> ```
> docs/emergent/EMERGENT-MASTER-PROMPT.md  >  2026-09-07 ops/admin spec  >  this file
> ```
>
> The 2026-09-07 spec already overrides this document's Discover loop (one Lens call per seed file), scrape-HTML-as-peer, hop cap of 5, scrape source cap of 30, "no background jobs", and "no embeddings" (pHash is allowed, CLIP is not). The master prompt additionally overrides "do not probe feeds during Discover" and the scrape cap of 30 (now 20). Treat this file as background and rationale, not as the build order.

## Purpose

A local, single-user FastAPI app that grows a Yahoo-style directory of niche aesthetic blogs and archives. It starts from images in `./seed_images/`, finds sites via SerpApi Google Lens (with a text-search fallback), mines blogrolls, scrapes candidate images into a review grid, and zips selected originals. Domains the user actually saves from appear on a Curator Hall of Fame.

Web 1.0 HTML/CSS is a replaceable skin. Job robustness, SQLite schema, and download accounting are not.

## Non-goals

LLM tagging, Playwright, accounts, remote deploy, committing seed images, restyling beyond a simple 1998-ish skin, autonomous multi-hop crawling, background expansion loops, embedding similarity, rendering the hop graph, scraping Google/Yandex Lens HTML, a second paid reverse-image vendor.

## Layout

| Path | Role |
| --- | --- |
| `server.py` | FastAPI, Jinja2, zip download, toggles, job kickoff |
| `sources.py` | Seed ingest, SerpApi Lens, persist sources, Visual Hop |
| `harvester.py` | RSS/Atom auto-discovery, blogroll/webring crawl |
| `scraper.py` | Image harvest, visual filters, `scraped_cache/` |
| `db.py` | SQLite schema and helpers |
| `jobs.py` | Daemon-thread jobs and status |
| `categorizer.py` | Keyword vocabulary → multi-tags |
| `policy.py` | Registrable host, blacklist, whitelist bias |
| `fallback.py` | Brave (optional) then DuckDuckGo HTML |
| `config.py` | Paths, caps, User-Agent, env |
| `templates/index.html`, `templates/working.html` | Pages |
| `static/app.js`, `static/style.css` | Skin + checkbox/zip JS |
| `./seed_images/`, `./scraped_cache/`, `data/goodform.db` | Data dirs |
| `.env` / `.env.example` | `SERPAPI_API_KEY`, optional `BRAVE_SEARCH_API_KEY` |

Override DB and cache in tests via `GOODFORM_DB` and `GOODFORM_CACHE`.

## Data model

`sources.category` is not a column. Sites belong to many groups via `source_tags`.

- `sources`: `id`, `domain` UNIQUE (host without `www.`, lowercased), `title`, `sample_url`, `feed_url`, `status` (`active` / `error` / `disabled`), `enabled` INTEGER default 1, `downloads_count` INTEGER default 0, `created_at`, `updated_at`
- `source_tags`: `(source_id, tag)` PK
- `images`: `id`, `source_id`, `image_url` UNIQUE, `cache_path`, `width`, `height`, `origin_url`, `saved_count` INTEGER default 0, `hopped_at` nullable, `created_at`
- `expansion_edges`: `id`, `from_source_id`, `to_source_id`, `via_type` (`link` | `image_lens` | `text_search`), `via_url`, `via_image_id`, `created_at`; unique on `(from_source_id, to_source_id, via_type, ifnull(via_image_id, 0))`
- `jobs`: `id`, `kind` (`discover` / `mine` / `scrape` / `hop`), `status` (`running` / `done` / `error`), `message`, `log`, `started_at`, `finished_at`

`downloads_count` is incremented once per image included in a user download (zip or single file). Hall of Fame: `downloads_count > 0`, descending, cap 50.

**Dud node:** `downloads_count = 0`. Cached images on dud nodes are hop bridges.

**Fit** is computed at job time, not stored:

- Strong: source `downloads_count` / image `saved_count`
- Medium: tag overlap with Hall of Fame domains (or, if empty, tags from the current Discover run)
- Weak: whitelist-shaped host
- Never: blacklist

## Domain policy

Blacklist (host equals or is a subdomain of): Pinterest, Amazon, eBay, Shutterstock, Getty, Etsy, Reddit, Instagram, Facebook, TikTok, Twitter/X, YouTube, Google, Wikipedia, Unsplash, Adobe Stock, Alamy, Flickr, plus news: nytimes, cnn, bbc, theguardian, reuters, washingtonpost, foxnews, msn, yahoo.

Whitelist bias (rank higher, still insert other non-blacklisted independents): Tumblr *subdomains* (not `tumblr.com` itself), `substack.com`, `are.na`, `neocities.org`, `github.io`.

Only `http`/`https` URLs. Drop empty hosts.

## Discover (`sources.py`)

1. List raster files in `./seed_images/` (jpg/jpeg/png/webp). Empty folder: job completes with a message, no crash.
2. For each seed: Pillow-compress until ≤ 500KB, `POST https://serpapi.com/image` multipart `image` + `api_key`, then `GET https://serpapi.com/search` with `engine=google_lens`, `image_id`, `type=visual_matches`.
3. Collect `visual_matches[].link` + `title`.
4. Insert new domains; skip duplicates. Do not probe feeds during Discover.
5. Tag via categorizer. Unmatched → `Unsorted`.

SerpApi failure (HTTP 401/402/403/429/5xx, timeout, connection error, JSON `error`): switch the rest of that job to text fallback. Do not keep retrying Lens.

Missing `SERPAPI_API_KEY`: skip Lens and use fallback immediately (log that Lens was skipped).

## Text fallback (`fallback.py`)

Not reverse-image. Provider order: Brave Search JSON if `BRAVE_SEARCH_API_KEY` is set and the call succeeds, else DuckDuckGo HTML at `https://html.duckduckgo.com/html/`. Isolate DDG parsing so markup changes stay in this file. Unwrap `/l/?uddg=` redirects.

Queries from seed filenames (tokenized), existing directory tags, and for hops the dud source title + tags + origin path tokens. Templates include `{tag} personal blog`, `{tag} zine archive`, `site:tumblr.com {tag}`. Subtract obvious aggregator terms in the query when easy (`-pinterest -etsy -shutterstock`).

Hits are `{title, url, snippet}` and go through the same policy + categorizer + insert path. Working-page message must say when fallback is in use (e.g. `SerpApi unavailable (429); discovering via DuckDuckGo`).

If both Lens and fallback fail: job `error` with a visible message. Mine Blogrolls still works independently.

## Categories (`categorizer.py`)

Lowercase keyword match on title + URL + domain. Multi-tag. Vocabulary: geocities, neocities, brutalist, vaporwave, y2k, webcore, zine, scan, collage, analog, diary, archive, tumblr, substack, arena (are.na), photography, illustration, fashion, vintage, cyber, gothic, cottage. If none match: `["Unsorted"]`.

## Harvest (`harvester.py`)

**Feeds:** for each enabled source, try stored `feed_url`, then `<link rel="alternate" type="application/rss+xml|atom+xml">`, then `/feed`, `/rss`, `/atom.xml`, `/index.xml`. Parse with `feedparser`. Store the first working feed. HTTP 403/404: log, continue.

**Mine:** for enabled sources, fetch homepage, `/links`, `/blogroll`, `/blogroll.html`. Collect footer and those page anchors, plus webring-ish copy (`friends`, `neighbours`/`neighbors`, `blogroll`, `webring`, `links`). Insert new non-blacklisted peer domains, tag from link text + URL, write `expansion_edges` `via_type=link`. No SerpApi. Cap 40 new domains per job.

Polite User-Agent, short timeout, small delay between requests.

## Scrape (`scraper.py`)

Enabled sources only, cap 30 sources per job. RSS: `media:content`, `enclosure`, `<img>` in entry HTML. No feed: scrape `sample_url` or homepage `<img>` / largest `srcset`. Skip SVG, `data:`, 1×1, known tracker/ad hosts. Download, open with Pillow: shortest edge ≥ 400px; aspect between 1:3 and 3:1 inclusive; raster only. Cache at `scraped_cache/{domain}/{sha16}.{ext}`. Dedup on `image_url`. `saved_count` starts at 0. Broken fetch: log, continue.

## Visual Hop (job `hop`)

Select up to `HOP_IMAGE_CAP` (5) images with `cache_path`, `saved_count = 0`, `hopped_at` null, parent `enabled`. Prefer dud sources (`downloads_count = 0`), then tag overlap with Hall of Fame (or current Discover tags if HoF empty), then larger shortest edge.

For each: Lens upload + visual matches, insert peers, `expansion_edges` `via_type=image_lens`, set `hopped_at`. Depth 1: do not scrape or hop new domains in the same job.

If Lens is down: text hop from parent title/tags/path, `via_type=text_search`, still set `hopped_at`. 403/404 on a hop fetch: log, continue.

## Jobs and UI

POST `/jobs/{discover|mine|scrape|hop}` inserts a running job, starts a daemon thread, 303 to `/working/{id}`.

`working.html`: message + log, `<meta http-equiv="refresh" content="2">` plus JS reload; redirect home when `done` or `error`.

Index skin: serif, default blue/purple links, borders, tables.

Header: Discover, Mine Blogrolls, Scrape Active Feeds, Visual Hop, Select All / Deselect All, Download Selected (.zip), Download All (.zip).

Sidebar Hall of Fame: `[Rank] domain.com — [N] saved`.

Directory: H2 per tag; a source may appear in multiple groups; enable checkbox persists via `POST /api/sources/{id}/enabled`.

Grid: checkbox, preview from cache, `WxH`, origin domain linked to `origin_url`, single `[Download]`.

Empty copy when no seeds, no sources, or no images. Hop graph is not rendered.

## Downloads

- `POST /api/download` JSON `{ "ids": [int, ...] }` (empty → 400). Zip cached originals (`zipfile`), timestamped filename, `StreamingResponse`. After a successful zip, one SQLite transaction: `images.saved_count += 1` and `sources.downloads_count += 1` per image.
- `GET /api/images/{id}/file?save=1` streams one file and applies the same increments.
- Saving does not remove the grid row; it only makes the image ineligible for Visual Hop.

## Errors and ops

HTTP 403/404 on scrape/harvest: skip + job log. Other HTTP/parse errors: log, continue. Job-level error only when search cannot run at all (Lens and fallback both fail for Discover/Hop).

`.gitignore`: `.env`, `data/*.db`, `scraped_cache/*` (keep `.gitkeep`), `__pycache__/`, `.pytest_cache/`.

Run: `uvicorn server:app --reload --host 127.0.0.1 --port 8000`.

## Tests

No live SerpApi, Brave, or DDG. Cover: blacklist/whitelist, categorizer multi-tag + Unsorted, image gates (synthetic Pillow images), domain dedupe, zip increments, Hall of Fame excludes scrape-only domains, hop sampler (dud, unsaved, not hopped, cap, no recurse), link mine writes edges, fallback query builder, DDG HTML fixture parse, provider order, SerpApi error switches to fallback, download API via FastAPI TestClient.
