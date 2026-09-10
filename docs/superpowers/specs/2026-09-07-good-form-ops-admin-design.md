# good-form: ops, admin, and credit-safe engine

Date: 2026-09-07 (corrections applied 2026-09-10)

> **Precedence.** [`docs/emergent/EMERGENT-MASTER-PROMPT.md`](../../emergent/EMERGENT-MASTER-PROMPT.md) outranks this document, which outranks the 2026-09-06 curator spec. Where the master prompt disagrees with anything below, the master prompt wins. Blocks marked **Corrected 2026-09-10** fix errors that were in the original text; they are not new requirements.
>
> **Corpus note.** The ~235 seeds are an export from the owner's own Instagram research account. Their filenames are meaningless (`2019-03-15_10-22-33_UTC.jpg`, `IMG_4821.jpg`), which breaks the filename-derived text fallback, and the corpus subject matter is not the aesthetic vocabulary hardcoded in `categorizer.py`. The master prompt replaces both with a notes sidecar and a corpus-derived, admin-approved vocabulary. It also treats the 15–20 Lens budget as a per-run budget with resumable rounds rather than a claim that the corpus is near-duplicate heavy, because 235 curated posts are mostly distinct.

This spec is a **delta** on [2026-09-06-good-form-curator-design.md](./2026-09-06-good-form-curator-design.md). Unchanged rules still apply: domain policy, categorizer vocabulary, download accounting, Hall of Fame (`downloads_count > 0`), dud nodes, hop depth 1, SerpApi circuit-break to Brave then DuckDuckGo, polite `User-Agent`, and “job error only when Lens and fallback both produce nothing.”

This spec **overrides** the 2026-09-06 Discover loop (one Lens call per seed file), scrape HTML-as-peer, hop cap of 5, scrape source cap of 30, “no background jobs,” “no embeddings” (pHash is allowed; CLIP is not), and “restyle only a simple 1998-ish skin.” Header/footer chrome is specified verbatim below. The directory body stays a Yahoo-style table directory.

## Purpose

A single-user FastAPI curator that grows a Yahoo-style directory of niche aesthetic blogs from seed images, then reviews candidates in a keyboard Hot-or-Not grid. SerpApi Google Lens is expensive. The engine spends **15–20 Lens uploads** on a ~235-image seed dump by clustering to medoids, keeps a zero-credit RSS “micro-zine,” resurrects dead Lens hits via the Internet Archive CDX API (2004–2014), and optionally mirrors seeds and saved originals to Google Drive so a dead laptop disk does not erase the gallery.

Admin is **ungated**. There are no user accounts.

## Stack locks

- Database: **SQLite** (`data/goodform.db`). Not MongoDB.
- Engine: existing Python modules stay the source of truth: `policy.py`, `fallback.py`, `sources.py`, `harvester.py`, `scraper.py`, `jobs.py`, `db.py`, `categorizer.py`, `net.py`, `config.py`.
- UI: **React** Web 1.0 skin talking to FastAPI JSON. Jinja templates may remain; if `templates/index.html` exists it must carry the same banner/badge DOM and classes.
- Auth: none. No Clerk, no Emergent Auth, no signup.
- Clustering compute: **Python on the FastAPI host**, never in the browser.

## Non-goals

CLIP / LLM tagging / embeddings; Playwright; scraping Google or Yandex Lens HTML; hop depth greater than 1; autonomous Lens or hop expansion loops (weekly RSS `digest` is allowed); Stripe; MongoDB; Expo/mobile; committing `seed_images/` or `.env`; rewriting the 468×60 banner into a Tailwind hero.

## Locked defaults

Admin may raise caps. Caps always exist.

| Key | Default |
| --- | --- |
| `cluster_k_min` | 15 |
| `cluster_k_max` | 20 |
| Near-dup merge when N ≤ 20 | pHash Hamming ≤ 6 |
| Lens uploads per Discover | min(cluster count, 20) |
| Visual matches ingested per cluster (post-policy) | 12 |
| Fallback queries per Discover | 6 |
| Hop depth | 1 |
| Hop medoid images | 3 |
| Mine new domains | 40 |
| Scrape sources per job | 20 |
| Passing images per source (HTML last-resort) | 10 |
| Passing images per feed (manual scrape) | 10 |
| Digest images per feed | 3 |
| Scrape pHash drop | Hamming **< 5** (4 drops, 5 keeps) |
| Probation strikes | 3 |
| Wayback years | 2004–2014 inclusive |
| CDX / snapshot rate | ≤ 1 request/second |
| Image short edge | ≥ 400px |
| Aspect | 1:3 through 3:1 |
| SerpApi JPEG cap | 500KB |
| Request timeout | 12s |
| Delay | 0.35s |
| Grid list limit | 400 |
| `account.json` cache | 300s |
| Hall of Fame rows | 50 |
| User-Agent | `good-form/1.0 (local curator; +http://127.0.0.1:8000)` |

## Layout additions

| Path | Role |
| --- | --- |
| `cluster.py` | pHash + HSV histogram, k-medoids / agglomerative, medoid pick |
| `wayback.py` | Dead/parked probe, CDX, snapshot URL |
| `digest.py` | Weekly latest-N feed harvest (`run_digest`); uses `harvester.discover_feed` |
| `drive.py` | Optional Google Drive OAuth sync |
| `frontend/` | React directory, grid, admin, logs |
| `docs/emergent/EMERGENT-MASTER-PROMPT.md` | Paste target for Emergent |

New env (all optional except existing SerpApi for Lens):

```
SERPAPI_API_KEY=
BRAVE_SEARCH_API_KEY=
GOODFORM_SEED=
GOODFORM_CACHE=
GOODFORM_DB=
GOODFORM_GALLERY=
GOODFORM_DELAY=0.35
GOODFORM_DIGEST_CRON=0
GOOGLE_DRIVE_CLIENT_ID=
GOOGLE_DRIVE_CLIENT_SECRET=
GOOGLE_DRIVE_REFRESH_TOKEN=
GOOGLE_DRIVE_FOLDER_SEEDS=
GOOGLE_DRIVE_FOLDER_GALLERY=
```

`.gitignore` also ignores `gallery/*` (keep `.gitkeep`), Drive token files, and `frontend/node_modules`.

## Data model delta

`sources.status` values: `active` | `error` | `disabled` | `probation`.

Add on `sources` (SQLite `ALTER` if missing):

- `cycles_with_candidates` INTEGER NOT NULL DEFAULT 0
- `cycles_without_save` INTEGER NOT NULL DEFAULT 0
- `wayback_timestamp` TEXT NULL
- `live_url` TEXT NULL (original live URL when `sample_url` is an archive.org snapshot)
- `last_digest_at` TEXT NULL
- `last_cycle_image_ids` TEXT NOT NULL DEFAULT '[]'

Add on `images`:

- `phash` TEXT NULL (hex from `imagehash.phash`)

`jobs.kind` adds `digest`.

`expansion_edges.via_type` adds `wayback`.

New tables:

```sql
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seeds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  path TEXT NOT NULL UNIQUE,
  phash TEXT,
  hist TEXT,
  width INTEGER,
  height INTEGER,
  cluster_id INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seed_clusters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  medoid_seed_id INTEGER,
  member_count INTEGER NOT NULL DEFAULT 0,
  last_lensed_at TEXT,
  FOREIGN KEY (medoid_seed_id) REFERENCES seeds(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS provider_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider TEXT NOT NULL,
  event TEXT NOT NULL,
  status_code INTEGER,
  detail TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_status (
  name TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  last_ok_at TEXT,
  last_error TEXT,
  last_status_code INTEGER,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  circuit_open_until TEXT
);
```

`provider_status.name`: `serpapi` | `brave` | `ddg` | `wayback` | `drive`.
`provider_status.state`: `ok` | `skipped` | `degraded` | `down`.

`settings.value` is JSON or plain text. Secrets stay in `.env`; settings hold caps, recipes, seed/gallery paths, pHash threshold.

Env keys override settings for secrets and for `GOODFORM_SEED` / `GOODFORM_DB` / `GOODFORM_CACHE` when set.

## 1. Centroid cluster seed filter

Module: `cluster.py`. Dependency: `ImageHash` (`import imagehash`).

Seed clustering uses `imagehash.phash(img, hash_size=16)` (256-bit) plus an 8×8×3 HSV histogram stored as JSON on `seeds.hist`. L1-normalise the histogram so its bins sum to `1.0`. Combined distance:

`0.7 * (hamming / 256.0) + 0.3 * (l1 / 2.0)`

`2.0` is the maximum L1 distance between two distributions that each sum to 1.0, so both terms land in `[0, 1]` and the 70/30 weighting is the real weighting. No cloud vision.

> **Corrected 2026-09-10.** This previously read `0.3 * (l1 / 156672.0)` "where `156672 = 8 * 8 * 3 * 255`". That identity is false: `8 * 8 * 3 * 255 = 48960`. Implemented as written, the colour term could contribute at most 9% instead of the intended 30%, making the metric very nearly pure pHash. The normalised form above replaces it and removes the magic constant.

Scrape/digest near-dup gate uses a **different** hash: `imagehash.phash(img)` default `hash_size=8` (64-bit). Hamming **< 5** drops. Do not feed 256-bit cluster hashes into that gate.

Procedure before Discover:

1. List rasters in the configured seed root (jpg/jpeg/png/webp). Empty folder: job message, no crash, no Lens.
2. Hash each file; upsert `seeds`.
3. If count ≤ 20: one cluster per file except merge pairs with pHash Hamming ≤ 6.
4. If count > 20: **average-linkage agglomerative**, merging the closest pair until the cluster count equals `clamp(18, 15, 20)`. Update distances by Lance-Williams average linkage, `d(ab, c) = (|a|*d(a,c) + |b|*d(b,c)) / (|a| + |b|)`. Break ties by scanning the upper triangle in ascending index order and taking the first strict minimum, so repeated runs give identical clusters. This replaces the earlier "agglomerative clustering or k-medoids … prefer K=18 when the dendrogram allows it", which was nondeterministic and did not guarantee landing in the band.
5. Medoid = member with minimum sum of combined distances to other members. Tie-break: larger `min(width,height)`, then lower `seeds.id`.
6. Record `member_count` and `mean_intra_distance` per cluster. A cluster is **tight** when `mean_intra_distance <= 0.15`, otherwise **loose**. A loose cluster's medoid does not meaningfully represent its members, and the admin cluster cards must say so rather than implying the corpus was compressed losslessly.
6. Discover Lenses **only medoids**, compressed with the existing ≤500KB JPEG path. Never more than 20 Lens uploads in one job.
7. After the first Lens failure (401/402/403/429/5xx/timeout/JSON error), the rest of that job is text fallback only.

Per medoid: ingest at most 12 `visual_matches` that pass `policy.accept_url`. Deduplicate hosts across the whole job before insert.

Hop: cluster unsaved cached hop candidates the same way; Lens at most 3 medoids; depth 1; do not scrape or hop newly inserted domains in the same job.

Admin shows cluster cards (member filenames, medoid marked, estimated Lens calls). Dry-run Discover shows clusters and would-be hosts without inserts.

## 2. Inverted feed funnel and micro-zine

HTML scrape is last resort.

On **new source insert** (including inserts that happen during Discover — this overrides 2026-09-06 “do not probe feeds during Discover”) and on **Mine**: discover feed (`<link rel="alternate" type="application/rss+xml|atom+xml">`, then `/feed`, `/rss`, `/atom.xml`, `/index.xml`, Feedburner hrefs). One polite delayed GET per new host. Store the first `feedparser`-valid URL. Discover still does not scrape images.

**Scrape:** if `feed_url` works, harvest only from the feed (latest 10 passing images). Homepage `<img>` / srcset only when there is no feed or the feed is empty/broken; log `html fallback`.

**Digest** (`POST /jobs/digest`, kind `digest`): every enabled source with a working feed, latest **3** images that pass raster gates and the pHash gate. Zero SerpApi. Set `last_digest_at`.

Cron: when `GOODFORM_DIGEST_CRON=1`, run digest weekly Monday 09:00 local. Always also callable by hand. This is not a Lens/hop loop.

## 3. Keyboard Hot-or-Not and domain probation

When the review grid is focused (not when a text input is focused):

- **J** / ArrowDown: next cell
- **K** / ArrowUp: previous cell
- **Space**: toggle select on the current cell
- **Enter**: zip the current selection (`POST /api/download`)

Hint row: `J/K move  SPACE mark  ENTER zip`. Current cell: 3px inset black focus ring.

Probation is judged **between** jobs so the Hot-or-Not pass can happen after scrape/digest finishes.

Store on each source (reuse `last_digest_at` plus a JSON settings-or-column `last_cycle_image_ids` text, default `[]`): the image ids created for that source in the last scrape/digest.

- **Only a manual scrape records or scores cycles. Digest never strikes and never writes a cycle list.**
- At **end** of a scrape: for each source that inserted ≥1 new image, set `last_cycle_image_ids` to those ids, set `last_cycle_at`, and `cycles_with_candidates += 1`. Do not strike yet.
- At **start** of the next scrape: a source's cycle is **scoreable only when the user has actually reviewed since it was recorded**, that is `settings.last_download_at > sources.last_cycle_at`, where `last_download_at` is written by `db.record_downloads`.
  - Not scoreable: leave the list intact, touch no counter.
  - Scoreable and every listed image still has `saved_count = 0`: `cycles_without_save += 1`.
  - Scoreable and any has `saved_count > 0`: `cycles_without_save = 0`.
  - Clear `last_cycle_image_ids` after scoring; the job about to run writes a new list at the end.
- When `cycles_without_save` reaches 3: `status='probation'`, `enabled=0`, log it. Probation sources are skipped by scrape/digest.
- If a source produced raster-passing candidates but every one was dropped by the pHash gate, log `0 new / n dup` and treat the cycle as producing no candidates, so it earns no strike.
- Counters start at 0. No retroactive strikes on images that existed before this feature. Admin restore: counters 0, `last_cycle_image_ids='[]'`, `status='active'`, `enabled=1`.
- Add columns `last_cycle_image_ids TEXT NOT NULL DEFAULT '[]'` and `last_cycle_at TEXT`.

> **Corrected 2026-09-10.** The original rule scored at the start of the next scrape *or digest* with no evidence the user had reviewed anything. Two consequences: running two scrapes back to back handed out a free strike, and with `GOODFORM_DIGEST_CRON=1` three unattended Monday digests set every source to `probation, enabled=0` — which then starved the digest that caused it. Requiring a download between cycles makes "the user still has to Hot-or-Not" an enforced precondition rather than an assumption.

## 4. Wayback Machine necromancer (core ingest)

After policy accepts a Lens or fallback URL, **probe** live using a new `net.probe`, **not** `net.fetch`. `net.fetch` returns `None` for 403, 404 and connection errors alike and discards the status code, so a probe built on it cannot tell a dead host from one that is merely blocking us, and every transient failure would be "resurrected" from a 2008 snapshot. `net.probe` returns `state`, `status_code`, `final_url` and `text_head`:

- `dead` — NXDOMAIN, connection error, timeout, HTTP 404/410/450, or a parked page
- `blocked` — HTTP 403 or 429; the host is alive and does not want us, so do **not** resurrect it
- `alive` — anything else that returned a body
- `unknown` — unclassifiable; treat as `alive` and do not resurrect

Parked: title or body contains (case-insensitive) `domain is for sale`, `buy this domain`, `parked free`, `godaddy.com/domainsearch`, `sedo.com`, `hugedomains`, `this domain may be for sale`.

**Budget.** Deduplicate candidate **hosts** for the job and probe once per host, not once per URL, caching results for the job's lifetime. Cap at 60 probes and 25 CDX lookups per job and log when the budget is reached. 20 medoids × 12 matches is 240 candidate URLs; unbudgeted, at a 0.35s delay with 12s timeouts, a single Discover would run for the better part of an hour inside a daemon thread with no cancel.

Then CDX, rate-limited to **≥ 1 second per archive.org request** by a limiter dedicated to archive.org and separate from the global delay:

`GET https://web.archive.org/cdx/search/cdx?url={url}&output=json&from=2004&to=2014&filter=statuscode:200&collapse=digest&limit=5`

Use a 2004–2014 snapshot. Do not fall back to a 2015–present snapshot. If none: log `no archive 2004-2014`, do not insert a dead parked host.

Fetch `https://web.archive.org/web/{timestamp}id_/{original}` when possible. Set `sample_url` to the archived URL, `live_url` to the original, `wayback_timestamp` to the CDX timestamp. `expansion_edges.via_type='wayback'`.

**Identity.** `sources.domain` is always `accept_url(original_url)`. Only `sample_url` holds the snapshot URL. Give `ingest_hit` keyword-only `live_url` and `wayback_timestamp` parameters, and add `web.archive.org` and `archive.org` to `policy.BLOCKED_SUFFIXES` so a snapshot URL can never become a source through any other code path.

> **Added 2026-09-10.** The original text said where to store the snapshot but never where the domain comes from, and the obvious reading is fatal. Verified against the current `policy.py`: `accept_url("https://web.archive.org/web/20080512id_/http://cool.blog.example/page")` returns `web.archive.org`, and `is_blacklisted("web.archive.org")` is `False`. Because `sources.domain` is UNIQUE, every resurrected site would have collapsed into a single row named `web.archive.org`.

Scrape/Mine against the snapshot when live is dead. Resolve archived image URLs. Blacklist still applies (no Pinterest-via-Wayback), and it is applied to the **original** host.

UA as above. On HTTP 429: log, mark Wayback `degraded`, skip remaining CDX for that job. Status light: `wayback`.

## 5. Seed root and optional Google Drive

Directory tools expose **Seed root** (default `./seed_images`) and **Gallery root** (default `./gallery`). Clustering reads the seed root on the FastAPI host.

Google Drive is optional OAuth to the curator’s Google account (not app-user login). Scope `https://www.googleapis.com/auth/drive.file`. Create or use folders `good-form/seeds` and `good-form/gallery`. Admin: Connect, Sync seeds down, Push gallery up.

On sync: download rasters into seed root, recluster. On zip or single save: copy originals to `gallery/{domain}/{filename}` and upload to Drive gallery if connected. Optional db copy to Drive `good-form/data/goodform.db`.

Missing Drive creds: `drive` state `skipped`. App runs.

`drive.py` imports `googleapiclient` and `google_auth_oauthlib` **lazily, inside the functions that use them**, and those packages live in a separate `requirements-drive.txt`. A module-level import makes the whole app fail to boot when the libraries are absent, which contradicts "App runs." Missing libraries and missing credentials both resolve to `skipped`.

Do not commit seeds. Do not cluster inside Drive.

## 6. Scrape pHash gate

After raster gates, before `scraped_cache` write and before `INSERT` into `images`: `imagehash.phash(pil_image)` with default `hash_size=8`.

Load existing `images.phash` once per job. If any Hamming distance **< 5**, drop, log `phash dup hamming={n} of image {id}`. Distance 5 keeps; 4 drops.

Store hex on kept rows. Rows with NULL phash cannot match. Same gate on digest. URL uniqueness remains; this catches reblogs.

Do not use the 15–20 seed clusterer here.

## 7. OPML export

Directory header control `[Export OPML]` → `GET /api/directory.opml`.

Content-Type `text/x-opml+xml`, `Content-Disposition: attachment; filename="good-form-directory.opml"`.

OPML 2.0. `head/title` = `good-form`. One `outline` per source with a non-empty `feed_url`: `text` and `title` = source title or domain, `type="rss"`, `xmlUrl` = feed, `htmlUrl` = `sample_url` or `https://{domain}/`.

Default: `enabled=1` and `status` in (`active`, `error`). `?all=1` includes probation/disabled (`category` = status). Empty directory: valid OPML, empty body, HTTP 200.

## 8. Chrome (verbatim)

Header/footer only. Directory listing: Times/Georgia, `#0000ee` / `#551a8b` links, table layout, `#ffffcc` sidebar, Hall of Fame, “you are here”.

Banner width 468px, min-height 60px. Height may grow so credit lines are not clipped. Classes and CSS must match the blocks in `docs/emergent/EMERGENT-MASTER-PROMPT.md` (copy, do not paraphrase).

Inside `.banner-content`, immediately under the marquee:

- `.banner-credits` color `#ffff00`: `[ {remaining}/{plan} SERP CREDITS REMAINING ]` from `GET https://serpapi.com/account.json?api_key=` using `searches_per_month` (plan) and `this_month_usage`. `remaining = max(0, searches_per_month - this_month_usage)`. Cache 300s. This endpoint is not a Lens search. Missing key or failure: `[ SERPAPI SKIPPED ]` and `Lens today: {n}` from local job logs / a `lens_uploads_today` counter.
- `.banner-domains` color `#ffff00`: `[ {n} DOMAINS IN DIRECTORY ]` = `COUNT(*)` on `sources`.

Do not call `account.json` per grid image.

Footer below the grid: 88×31 badges FASTAPI POWERED, SERPAPI INSIDE, HTML 4.01 VALID, 1024x768 BEST VIEW, plus optional `WAYBACK OK` or `WAYBACK DOWN` from `provider_status`. Same 88×31 family. No modern footer.

## Search recipes (admin-editable)

Default templates (max 6 queries built): `{term} personal blog`, `{term} zine archive`, `site:tumblr.com {term}`, plus minus string `-pinterest -etsy -shutterstock -amazon -reddit`.

Provider order: Lens → Brave (if keyed) → DDG HTML. Unchecking Brave in admin is the only way DDG runs while a Brave key exists.

Skip a host for the rest of a job after two HTTP 403s.

## Admin (`/admin`, ungated)

Webmaster-tools page (nested tables, not SaaS cards):

- Search recipes, minus terms, site: biases, match caps, provider checkboxes
- Engine caps table (all locked defaults above)
- Policy: blacklist suffixes, exact blocks, whitelist hosts, categorizer keywords (start from current `policy.py` / `categorizer.py`)
- Seed root, gallery root, Drive connect/sync, cluster preview, dry-run Discover
- Probation list + restore
- Manual add URL (through `accept_url` + categorizer)
- Bulk enable/disable, retag
- Settings export/import JSON (no secrets)
- Status lights: SerpApi, Brave, DDG, Wayback, Drive
- Credit ledger: Lens uploads this job, Lens today, account remaining

OPML stays on the **directory** header.

## Logging

`/logs`: job history (kind, status, started, finished, message) and click-through full log. No auto-redirect that discards the log.

`/working/{id}`: live tail while `running`. On `done` or `error`, stay on a log view (or `/logs/{id}`) with a link home. Do not bounce to `/` in 2 seconds.

`provider_events` append-only for serpapi, brave, ddg, wayback, drive, including `account.json` fetch.

## Directory body

H2 per tag; sources may appear in multiple groups; `Unsorted` last. Enable checkbox → `POST /api/sources/{id}/enabled`. Show feed badge, wayback badge, `[probation]`. Source detail: tags, sample/feed/live/wayback, edges in/out, images.

Empty copy: no seeds / no sources / no images.

## Downloads and gallery

Existing zip and single-file increment rules unchanged. After a successful save, copy cached originals into gallery root `{domain}/{filename}` and Drive if connected.

## Errors

403/404 on scrape/harvest: skip, log, continue. Repeated live failures: `status=error` (not probation). Job-level `error` only when Discover/Hop cannot search at all (Lens and fallback both empty).

## Tests (no live network)

Keep existing pytest. Add:

- Cluster: 235 synthetic near-dup groups collapse to K in 15–20; medoid is min-distance member
- N=10 distinct seeds → 10 Lens candidates except Hamming ≤ 6 merges
- Discover mocks Lens only for medoids
- pHash gate: identical raster, two URLs → second dropped; Hamming 5 kept, 4 dropped
- Digest keeps 3 passing images per feed
- Probation after three harvests with unsaved cycle images, scored at the start of the next job; restore clears
- CDX mock + parked HTML → `via_type=wayback`; no 2024 snapshot when 2004–2014 empty
- OPML: outlines only for sources with `feed_url`; empty → 200
- `account.json` mock drives remaining/plan badge payload
- SerpApi 429 still switches the rest of Discover to fallback
- Zip increments unchanged

## Run

```
uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

Frontend: Vite dev proxy or FastAPI serving the React build at `/`.
