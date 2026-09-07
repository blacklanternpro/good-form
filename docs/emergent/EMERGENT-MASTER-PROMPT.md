# EMERGENT MASTER PROMPT — paste this entire file

**How to start:** Attach GitHub repo `blacklanternpro/good-form` branch `main`. Build a **full-stack web app**. Agent: E1 (or E3 if you want to spend more). Budget: spend it. Read `docs/superpowers/specs/2026-09-06-good-form-curator-design.md` and `docs/superpowers/specs/2026-09-07-good-form-ops-admin-design.md` before writing code. Those files win over your defaults.

**One sentence:** Extend this existing FastAPI + SQLite visual curator into a credit-safe archival engine with centroid Lens (15–20 calls, not 235), RSS micro-zine, Wayback resurrection, Hot-or-Not grid, ungated admin, OPML export, Drive backup, and a verbatim 1998 468×60 / 88×31 chrome.

---

## You are extending an existing repo

This is not a greenfield SaaS. The Python engine already works.

**Keep and extend:** `server.py`, `sources.py`, `harvester.py`, `scraper.py`, `db.py`, `jobs.py`, `categorizer.py`, `policy.py`, `fallback.py`, `config.py`, `net.py`, `tests/`.

**Add:** `cluster.py`, `wayback.py`, `drive.py`, React UI (`frontend/`), settings/status/OPML/seed APIs, schema migrations.

**Stack you will use:** FastAPI + SQLite + React (Web 1.0 CSS). Jinja may remain; if `templates/index.html` stays, it gets the same banner DOM.

**Stack you will not introduce:** MongoDB, Clerk, Emergent Auth, Stripe, Tailwind utility soup on the banner, Expo, CLIP, LangChain, Playwright.

Secrets stay in `.env`: `SERPAPI_API_KEY`, optional `BRAVE_SEARCH_API_KEY`, optional Google Drive OAuth fields. Do not commit `.env` or seed images.

---

## What the user does

1. Points a **seed root** (or uploads / syncs ~235 jpg/png/webp files, ~50MB) in ungated `/admin`.
2. Sees clusters (target 15–20 medoids) and estimated Lens calls, then **Discover New Sources**.
3. Dead Lens URLs come back as 2004–2014 Wayback snapshots instead of vanishing.
4. **Mine Blogrolls**, then **Scrape** (RSS first) or weekly **digest** (latest 3 images per feed, zero SerpApi).
5. Reviews the grid with **J/K/Space/Enter**, zips keepers, Hall of Fame updates.
6. Exports **OPML** into NetNewsWire / Thunderbird / Feedly.
7. Optional: Connect Google Drive so seeds + gallery survive a dead HDD.
8. Watches `/logs` and provider lights (SerpApi, Brave, DDG, Wayback, Drive) to see what is down.

---

## Hard locks (completion criteria)

- SQLite file database. One `data/goodform.db`.
- Discover Lenses **medoids only**. For 235 near-duplicate-heavy seeds, Lens uploads ∈ [15, 20]. Never one Lens call per file when N > 20.
- First SerpApi 401/402/403/429/5xx/timeout/JSON error in a job: remainder of that job is Brave-if-keyed else DuckDuckGo HTML. Do not keep retrying Lens.
- Hop depth is **1**. Hop cap default **3** medoid images.
- Scrape HTML is last resort. Feeds win. Digest = 3 images/feed.
- pHash Hamming **< 5** drops a scrape before cache and before INSERT. Hamming 5 keeps.
- Wayback is **in `ingest_hit`**, not a later plugin. CDX `from=2004&to=2014` only.
- Admin has **no login**.
- Banner and 88×31 strip use the HTML/CSS blocks below **verbatim** (class names, colors, marquee). Height of the banner may grow past 60px so credit text fits. Width stays 468px.
- Existing pytest stays green. New tests mock all network.

---

## Locked numeric defaults

cluster_k_min=15, cluster_k_max=20, near-dup Hamming≤6 when N≤20, max 12 visual matches per cluster after policy, max 6 fallback queries, hop cap 3, mine 40, scrape 20 sources, 10 images/source (HTML) or 10/feed (scrape) or 3/feed (digest), pHash drop if Hamming<5, probation at 3 strikes, Wayback 2004–2014, CDX ≤1 req/s, short edge ≥400px, aspect 1:3–3:1, SerpApi JPEG ≤500KB, timeout 12s, delay 0.35s, grid 400, account.json cache 300s, Hall of Fame 50.

Admin can raise caps. There is always a cap.

User-Agent: `good-form/1.0 (local curator; +http://127.0.0.1:8000)`

---

## Schema (migrate; do not drop existing tables)

`sources.status`: `active` | `error` | `disabled` | `probation`.

Add columns on `sources`: `cycles_with_candidates INTEGER NOT NULL DEFAULT 0`, `cycles_without_save INTEGER NOT NULL DEFAULT 0`, `wayback_timestamp TEXT`, `live_url TEXT`, `last_digest_at TEXT`, `last_cycle_image_ids TEXT NOT NULL DEFAULT '[]'`.

Add `images.phash TEXT`.

`jobs.kind` includes `digest`. `expansion_edges.via_type` includes `wayback`.

Create `settings(key, value, updated_at)`, `seeds(id, filename, path UNIQUE, phash, hist, width, height, cluster_id, created_at)`, `seed_clusters(id, medoid_seed_id, member_count, last_lensed_at)`, `provider_events(id, provider, event, status_code, detail, created_at)`, `provider_status(name PK, state, last_ok_at, last_error, last_status_code, consecutive_failures, circuit_open_until)`.

Providers: `serpapi`, `brave`, `ddg`, `wayback`, `drive`. States: `ok`, `skipped`, `degraded`, `down`.

Preserve: unique `sources.domain`, unique `images.image_url`, zip increments `saved_count` and `downloads_count` in one transaction, Hall of Fame = `downloads_count > 0`.

---

## Engine behavior

### Centroid clustering (`cluster.py`)

`pip` dependency `ImageHash`. `import imagehash`.

`imagehash.phash(img, hash_size=16)` (256-bit) + 8×8×3 HSV histogram. Distance = `0.7 * (hamming / 256.0) + 0.3 * (l1 / 156672.0)` where `156672 = 8*8*3*255`. No embeddings.

Empty seed root → Discover logs “No images in seed_images/” and finishes done, not error.

N≤20: Lens each file except merge Hamming≤6. N>20: cluster to K in [15,20], Lens **medoids only** (min sum-distance member; tie-break larger short edge). Compress with existing Pillow path to ≤500KB JPEG.

Hop candidates: same clusterer, max 3 medoids, prefer `downloads_count=0`, then Hall of Fame tag overlap, then larger short edge, `hopped_at` IS NULL, `saved_count=0`, parent enabled.

### Ingest + Wayback (`wayback.py`, called from ingest)

Policy `accept_url` first (keep `policy.py` blacklist/whitelist). Then HEAD/GET live URL.

Dead: NXDOMAIN, connect fail, timeout, 404/410/450, or parked phrases: `domain is for sale`, `buy this domain`, `parked free`, `godaddy.com/domainsearch`, `sedo.com`, `hugedomains`, `this domain may be for sale`.

Then: `GET https://web.archive.org/cdx/search/cdx?url={url}&output=json&from=2004&to=2014&filter=statuscode:200&collapse=digest&limit=5`

Pick a 2004–2014 snapshot. If none, log `no archive 2004-2014` and **do not insert** a dead parked host. Do not use a 2024 snapshot.

Fetch `https://web.archive.org/web/{timestamp}id_/{original}`. Store `sample_url`=archive URL, `live_url`=original, `wayback_timestamp`. Edge `via_type=wayback`. Scrape archived pages when live is dead. Still blacklist Pinterest et al even on archive.org.

Wayback 429: mark `degraded`, skip further CDX that job, log.

### Fallback

Unchanged order: Brave JSON if key works, else DDG HTML (`fallback.py`). Max 6 queries. Templates: `{term} personal blog`, `{term} zine archive`, `site:tumblr.com {term}` plus `-pinterest -etsy -shutterstock -amazon -reddit`. Working/log message names the provider (e.g. `SerpApi unavailable (429); discovering via DuckDuckGo`).

Missing `SERPAPI_API_KEY`: skip Lens immediately, log it, fallback.

### Feeds, scrape, digest

On insert (including Discover inserts) and on Mine: discover RSS/Atom (`rel=alternate`, `/feed`, `/rss`, `/atom.xml`, `/index.xml`, Feedburner). One polite GET per new host. Discover still does not scrape images.

Scrape: feed if it works; HTML homepage only as `html fallback`. Caps: 20 sources, 10 passing images.

`POST /jobs/digest`: latest 3 passing images per enabled feed. Zero SerpApi. `GOODFORM_DIGEST_CRON=1` → weekly Monday 09:00 local. Also always a button.

### pHash scrape gate

After 400px/aspect raster pass, before cache write and before INSERT: `imagehash.phash(img)` default `hash_size=8` (64-bit). Compare to all stored `images.phash` (load once per job). Hamming < 5 → drop, log `phash dup hamming={n} of image {id}`. Persist hex on kept rows. Same gate on digest. Do not use the 256-bit cluster hash here.

### Probation

After scrape/digest **ends**: sources that inserted ≥1 new image get `last_cycle_image_ids` set to those ids and `cycles_with_candidates += 1`. No strike yet (user still has to Hot-or-Not).

At the **start** of the next scrape/digest: for each source with a non-empty `last_cycle_image_ids`, if every listed image still has `saved_count = 0`, `cycles_without_save += 1`; if any was saved, `cycles_without_save = 0`. Then clear the list. At 3: `status=probation`, `enabled=0`. Admin restore clears counters and the list. No retroactive strikes.

### Drive (optional)

OAuth scope `https://www.googleapis.com/auth/drive.file`. Folders `good-form/seeds` and `good-form/gallery`. Sync seeds down into seed root then recluster. On save/zip, copy to `gallery/{domain}/` and upload. Optional `goodform.db` backup to `good-form/data/`. Missing creds → `drive=skipped`. App runs.

### Credits badge data

`GET https://serpapi.com/account.json?api_key=` cache 300s. `remaining = max(0, searches_per_month - this_month_usage)`, `plan = searches_per_month`. Local `Lens today` counter from jobs. Domain count = `SELECT COUNT(*) FROM sources`. Never call account.json per image.

---

## HTTP surface (additions; keep existing job POSTs and zip)

- `GET /` directory + grid chrome
- `GET /admin` ungated control room
- `GET /logs` and `GET /logs/{id}` full job log (no 2s bounce home)
- `GET /working/{id}` live tail while running; on finish show log + link home
- `POST /jobs/digest`
- `GET /api/status` providers, remaining/plan, lens today, domain count, seed/cluster counts
- `GET/PUT /api/settings`
- `GET /api/directory.opml` (`?all=1` includes probation/disabled)
- `POST /api/seeds` multipart upload; `DELETE /api/seeds/{id}`; `POST /api/seeds/recluster`
- `POST /api/sources` manual URL; existing enabled toggle
- `POST /api/sources/{id}/restore` probation restore
- `POST /api/discover/dry-run`
- Drive connect/sync endpoints as needed
- Existing: `POST /jobs/discover|mine|scrape|hop`, `POST /api/download`, `GET /api/images/{id}/file`, `GET /media/{id}`

OPML 2.0: `head/title=good-form`; outlines with `type="rss"`, `xmlUrl`, `htmlUrl`, `text`/`title`. Default: enabled sources with `feed_url` and status active/error. Empty → HTTP 200 empty body outlines.

---

## UI

**Directory body:** Yahoo category directory. H2 per tag, `Unsorted` last, enable checkboxes, feed/wayback/probation badges, Hall of Fame sidebar `[rank] domain — N saved`. Times/Georgia, default blue/purple links, `#ffffcc` sidebar, tables, “you are here”. Source detail page.

**Grid:** thumbnails, WxH, domain link, select, single download. Filters: tag, domain, min short edge. Hint: `J/K move  SPACE mark  ENTER zip`. Focus ring 3px inset black. Header actions: Discover, Mine Blogrolls, Scrape Active Feeds, Visual Hop, Digest, Select All / Deselect All, Download Selected, Download All, **Export OPML**.

**Admin:** 1999 webmaster tools (nested tables, `[*]` / `[DOWN]` text, not pill chips). Recipes, caps, policy lists (seed from current `policy.py` / `categorizer.py`), seed path, Drive, clusters, dry-run, probation restore, settings JSON import/export (no secrets).

**Logs:** history table + full scrollback.

---

## VERBATIM CHROME — copy these blocks

Put this at the top of the directory page header. React must emit the same tags and class names. Do not convert this into a modern hero.

```html
<div class="web1-banner-wrapper">
  <div class="web1-banner">
    <div class="banner-grid-overlay"></div>
    <div class="banner-content">
      <span class="banner-sub">[ SYSTEM :: GOOD-FORM v1.0 ]</span>
      <h1 class="banner-title"><marquee scrollamount="3">*** GOOD-FORM ARCHIVAL ENGINE ***</marquee></h1>
      <span class="banner-credits">[ {remaining}/{plan} SERP CREDITS REMAINING ]</span>
      <span class="banner-domains">[ {n} DOMAINS IN DIRECTORY ]</span>
      <span class="banner-tagline">AUTOMATED AESTHETIC RESEARCH &amp; BLOGROLL HARVESTER</span>
    </div>
  </div>
</div>
```

If SerpApi is missing or `account.json` failed, `banner-credits` text is `[ SERPAPI SKIPPED ] Lens today: {n}` instead of remaining/plan.

```css
.web1-banner-wrapper {
  display: flex;
  justify-content: center;
  margin: 10px 0 15px 0;
}

.web1-banner {
  width: 468px;
  min-height: 60px;
  height: auto;
  background: linear-gradient(180deg, #000080 0%, #000033 100%);
  border: 3px outset #c0c0c0;
  position: relative;
  box-shadow: 2px 2px 0px #000;
  box-sizing: border-box;
  overflow: hidden;
  font-family: "Courier New", Courier, monospace;
}

.banner-grid-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: repeating-linear-gradient(
    0deg,
    rgba(0, 0, 0, 0.25),
    rgba(0, 0, 0, 0.25) 1px,
    transparent 1px,
    transparent 2px
  );
  pointer-events: none;
}

.banner-content {
  position: relative;
  z-index: 2;
  color: #00ff00;
  text-align: center;
  padding: 4px 6px;
}

.banner-sub {
  font-size: 9px;
  color: #ffff00;
  letter-spacing: 1px;
  display: block;
}

.banner-title {
  margin: 2px 0;
  font-size: 13px;
  color: #ffffff;
  text-shadow: 1px 1px #ff0000;
}

.banner-credits,
.banner-domains {
  font-size: 8px;
  color: #ffff00;
  display: block;
  letter-spacing: 1px;
}

.banner-tagline {
  font-size: 8px;
  color: #00ffff;
  text-transform: uppercase;
}
```

Footer **below the review grid**:

```html
<div class="button-strip">
  <span class="retro-badge badge-blue"><b class="bg-black">FASTAPI</b>POWERED</span>
  <span class="retro-badge badge-orange"><b class="bg-dark">SERPAPI</b>INSIDE</span>
  <span class="retro-badge badge-green"><b class="bg-black">HTML 4.01</b>VALID</span>
  <span class="retro-badge badge-purple"><b class="bg-dark">1024x768</b>BEST VIEW</span>
  <span class="retro-badge badge-green"><b class="bg-black">WAYBACK</b>OK</span>
</div>
```

The fifth badge reads `WAYBACK` / `OK` or `DOWN` from `provider_status` (`badge-green` when ok, `badge-orange` when down/degraded). Keep 88×31.

```css
.button-strip {
  display: flex;
  gap: 6px;
  justify-content: center;
  margin-top: 20px;
  flex-wrap: wrap;
}

.retro-badge {
  display: inline-flex;
  width: 88px;
  height: 31px;
  border: 2px outset #ffffff;
  font-family: Arial, sans-serif;
  font-size: 8px;
  font-weight: bold;
  align-items: center;
  justify-content: center;
  text-align: center;
  box-sizing: border-box;
  cursor: default;
  user-select: none;
}

.retro-badge b { display: block; padding: 1px 2px; font-size: 7px; }
.badge-blue { background: #0000AA; color: #FFF; }
.badge-orange { background: #FF5500; color: #FFF; }
.badge-green { background: #008800; color: #FFF; }
.badge-purple { background: #5500AA; color: #FFF; }
.bg-black { background: #000; color: #00FF00; }
.bg-dark { background: #222; color: #FFFF00; }
```

If you keep `templates/index.html` / `static/style.css`, paste the same markup and CSS there too.

---

## Build order (do not skip; each step has a done check)

1. **SQLite migrate** — settings, seeds, seed_clusters, provider_events, provider_status, images.phash, source probation/wayback/`last_cycle_image_ids` columns. Done when `init_db()` on a fresh DB creates them and an old DB ALTERs without destroying rows.
2. **cluster.py + Discover/Hop** — medoid Lens only, K 15–20, hop cap 3, circuit-break fallback. Done when a folder of 30 near-duplicate images yields ≤20 Lens mock calls.
3. **wayback.py in ingest** — parked/dead → CDX 2004–2014 → snapshot fields + `via_type=wayback`. Done when mocked 404 + CDX JSON inserts an archive `sample_url`.
4. **Feed-first scrape + digest.py job** — HTML last resort; digest 3/feed; weekly cron flag. Done when a source with `feed_url` never hits homepage `<img>` in scrape tests.
5. **pHash gate** — Hamming < 5 drops before cache. Done when two URLs same raster → one row.
6. **Status + logs + account.json** — `/api/status`, `/logs`, 300s cache. Done when mocked account.json returns remaining/plan and missing key shows SERPAPI SKIPPED.
7. **React directory + OPML + grid keys + probation** — J/K/Space/Enter, Export OPML, 3-strike demote. Done when OPML TestClient returns `xmlUrl` outlines and a keyboard handler exists.
8. **Admin + seed root + Drive skipped path** — ungated `/admin`, path field, Drive `skipped` without creds. Done when PUT settings persists caps.
9. **Verbatim chrome** — banner marquee + credits + 88×31 strip in the running UI. Done when those class names exist in the DOM/CSS, not a Tailwind hero.
10. **pytest** — list below all pass; no live SerpApi/Brave/DDG/archive.org/Drive.
11. **Self-check** the “you are not done if” list. Fix until every line is false.

Dependencies to add: `ImageHash`, `google-api-python-client`, `google-auth-oauthlib`, `apscheduler` (or equivalent) for digest cron. Keep Pillow, feedparser, requests, beautifulsoup4, lxml.

---

## Tests you must add (all mocked)

- Cluster K in 15–20 on a large near-dup set; medoid is min combined distance
- N=10 distinct seeds → 10 Lens candidates except Hamming≤6 merges
- Discover Lens mock called only for medoids
- Identical Pillow raster, two URLs → second scrape dropped; Hamming 5 kept, 4 dropped
- Digest keeps 3 passing images per feed
- Three harvest cycles with no saves on that cycle's new images, scored at the **start** of the next job → probation + enabled=0; restore clears
- CDX mock + parked HTML → wayback edge; empty 2004–2014 → no insert of parked host
- OPML 200 with/without outlines; `?all=1` includes probation
- account.json mock → remaining/plan on `/api/status`
- SerpApi 429 → rest of Discover uses fallback
- Existing zip increment + Hall of Fame tests still pass

---

## You are not done if

- Discover still uploads every seed file to SerpApi when N>20
- MongoDB, Clerk, Stripe, or a login screen appeared
- Wayback is a stub, a TODO, or a separate optional job
- Scrape writes cache before the pHash gate
- There is no `GET /api/directory.opml`
- The grid has checkboxes only and no J/K/Space/Enter
- `/working/{id}` still hard-redirects home in 2s and `/logs` does not exist
- The 468×60 banner is missing `<marquee>` or was restyled into a card/hero
- The 88×31 strip is missing or uses different dimensions
- Credit line never reads remaining/plan or SERPAPI SKIPPED
- Digest job is missing
- Drive is required to boot
- Tests hit live network
- Hop depth > 1 or hop cap default still 5 with no clustering
- HTML scrape runs even when `feed_url` works

---

## Appendix — follow-up pastes if you stop early

**A. Skin fidelity:** Restore the verbatim banner/badge HTML and CSS. Do not use Tailwind on `.web1-banner`. Keep Times directory tables.

**B. OPML:** `GET /api/directory.opml` must import into Feedly/NetNewsWire (rss outlines with xmlUrl).

**C. Drive OAuth:** localhost redirect, drive.file scope, skipped state without secrets.

**D. Wayback 429:** one backoff, mark degraded, finish ingest of already-probed URLs.

**E. Credit cache:** account.json at most once per 300s; banner reads `/api/status`.

**F. Dry-run:** `POST /api/discover/dry-run` returns clusters + would-be hosts, zero inserts, zero Lens.

**G. Hop clustering:** unsaved dud images grouped; max 3 Lens hops.

Work until phase 11. Prefer finishing the engine before polishing copy.
