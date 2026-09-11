# GOOD-FORM MASTER PROMPT v2 — paste this entire file

**How to start:** Attach GitHub repo `blacklanternpro/good-form` branch `main`. Build a **full-stack web app**. Agent: E1 (or E3 if you want to spend more). Budget: spend it.

**One sentence:** Extend this existing FastAPI + SQLite visual curator into a credit-safe archival engine with centroid Lens (15–20 calls per run, not 235), resumable Lens rounds, a corpus-derived taxonomy, RSS micro-zine, Wayback resurrection, Hot-or-Not grid, ungated admin, OPML export, Drive backup, and a verbatim 1998 468×60 / 88×31 chrome.

**Baseline you must not regress:** `python3 -m pytest -q` currently reports **28 passed**. Every phase below ends with that number going up, never down.

---

## 0. Precedence — read this before anything else

There are three documents. They disagree with each other in places. The order is:

```
THIS FILE  >  docs/superpowers/specs/2026-09-07-good-form-ops-admin-design.md
           >  docs/superpowers/specs/2026-09-06-good-form-curator-design.md
           >  your own defaults
```

Read both specs for context and rationale. When a spec contradicts this file, **this file wins and you do not need to ask**. Section 6 lists every known contradiction and error in those specs together with the ruling, so read section 6 before you read the specs.

Do not restate the specs back to the user. Do not write a plan document. Start at phase 1.

---

## 1. Output contract

After **each** of the 11 phases in section 15, emit exactly this block and nothing more verbose:

```
PHASE <n> — <name>
files:      <comma-separated paths you created or modified>
done-check: <the exact command from the phase> -> <PASS|FAIL>
pytest:     <the final summary line, e.g. "34 passed in 1.2s">
notes:      <one line, or "none">
```

If `pytest` is not green, you are not finished with that phase. Fix it before moving on.

---

## 2. Failure protocol

- **Never** write `TODO`, `FIXME`, `pass  # implement later`, `raise NotImplementedError`, a stubbed function, or a placeholder component. If it is in the repo, it works.
- If a hard lock in section 8 is genuinely impossible, **stop**, name the lock ID, explain in two sentences, and continue with the remaining phases. Do not silently substitute something else.
- If you run out of budget, **stop at a phase boundary with pytest green**, and say which phase number you reached. Do not stop mid-phase.
- Do not refactor code that no phase asks you to touch. Do not reformat existing files. Do not upgrade existing pinned dependencies.
- Do not add a feature that is not in this file.

---

## 3. The repo you are extending

This is not a greenfield SaaS. The Python engine already works and has 28 passing tests.

**Keep and extend:** `server.py`, `sources.py`, `harvester.py`, `scraper.py`, `db.py`, `jobs.py`, `categorizer.py`, `policy.py`, `fallback.py`, `config.py`, `net.py`, `tests/`.

**Add:** `cluster.py`, `wayback.py`, `digest.py`, `drive.py`, `seedintake.py`, `vocab.py`, React UI (`frontend/`), settings/status/OPML/seed APIs, schema migrations.

**Stack you will use:** FastAPI + SQLite + React + TypeScript (Web 1.0 CSS). Jinja may remain; if `templates/index.html` stays, it gets the same banner DOM.

**Stack you will not introduce:** MongoDB, Postgres, any ORM, Clerk, Emergent Auth, Stripe, Tailwind on the banner, Expo, CLIP, any embedding model, scikit-learn, faiss, torch, LangChain, Playwright, Celery, Redis.

**Dependencies you will add to `requirements.txt`:** `ImageHash>=4.3.2` only. It brings `numpy` and `scipy` transitively (scipy is its DCT backend) and you may use both. Google Drive libraries go in a **separate** `requirements-drive.txt` (`google-api-python-client`, `google-auth-oauthlib`) and are imported lazily — see HL-19. Do **not** add a scheduler library; see HL-18.

Secrets stay in `.env`: `SERPAPI_API_KEY`, optional `BRAVE_SEARCH_API_KEY`, optional Google Drive OAuth fields. Do not commit `.env`, seed images, or `gallery/`.

---

## 4. About the actual corpus — this changes your defaults

The seed images are ~235 files from the owner's own archive (an Instagram research account he can no longer log into). Two consequences you must design for:

1. **The filenames are meaningless.** They look like `2019-03-15_10-22-33_UTC.jpg`, `123456789_1234567890_n.jpg`, or `IMG_4821.jpg`. This breaks the existing text fallback, which builds its queries out of filename tokens. Verified against the current code:

   ```
   tokenize_filename('2019-03-15_10-22-33_UTC.jpg') -> ['2019', 'utc']
   build_queries(...)[0] -> "2019 personal blog -pinterest -etsy -shutterstock -amazon -reddit"
   ```

   That is the credit-safety net the whole architecture depends on, and on this corpus it currently searches for the string `2019`. Phase 2 fixes it (HL-05, HL-06).

2. **The subject matter is not the categorizer's vocabulary.** `categorizer.py` hardcodes 22 words (geocities, vaporwave, y2k, webcore, zine…). The corpus is not those aesthetics, so every discovered source would land in `Unsorted`, the Yahoo directory would be one flat list, and the Hall-of-Fame tag-overlap ranking that Visual Hop depends on would have nothing to rank on. Phase 2 makes the vocabulary **corpus-derived and admin-approved** instead of hardcoded (HL-06).

The owner will supply notes for *some* images, not all. Everything you build must degrade cleanly from "rich notes" to "no notes at all".

---

## 5. Frozen seams — changing these breaks existing tests

The 28 existing tests bind to these signatures. **Add keyword-only parameters with defaults; never reorder or rename existing positional parameters.**

| Seam | Bound by |
| --- | --- |
| `db.insert_image(source_id, image_url, cache_path, width, height, origin_url)` — six positional args | `test_downloads.py`, `test_discover_and_hop.py`, `test_server.py` |
| `sources.run_discover(job_id, *, lens_search=None, web_search=None, seeds=None)` | `test_discover_and_hop.py` |
| `sources.run_hop(job_id, *, lens_search=None, web_search=None, cap=None)` | `test_discover_and_hop.py` |
| `scraper.run_scrape(job_id, fetch_fn=fetch, cap=None)` | `test_scraper_harvest.py` |
| `harvester.run_mine(job_id, fetch_fn=fetch, cap=None)` | `test_harvester.py` |
| `harvester.discover_feed(sample_url, domain, log=None, fetch_fn=fetch)` | `test_harvester.py`, `scraper.run_scrape` |
| `net.fetch(url, log=None, *, stream=False, timeout=None)` returning `Response | None`, swallowing 403/404 as `None` | `test_scraper_harvest.py` |
| `db.hop_candidates(limit, hof_tags=None)` ordering rules | `test_discover_and_hop.py` |
| `policy.accept_url`, `policy.whitelist_bias`, `categorizer.tag_text` return shapes | `test_policy.py`, `test_categorizer.py` |

Rules:

- `images.phash` is added as **`db.insert_image(..., *, phash: str | None = None)`**.
- You may **add** tests. You may not edit, weaken, delete, or `xfail` an existing assertion. If a lock appears to force an existing test to change, that means you implemented it wrong — re-read this file. If you are certain, stop and report it instead of editing the test.
- `net.fetch` keeps its current behaviour exactly. The Wayback probe uses the **new** `net.probe`, never `net.fetch` (HL-10).

---

## 6. Corrections to the spec documents

Read this table before you read the specs. Each row is a known error in them; the ruling is binding.

| Where | What the spec says | Ruling |
| --- | --- | --- |
| 09-07 §1 distance metric | `0.3 * (l1 / 156672.0)` where `156672 = 8*8*3*255` | **Arithmetically false.** `8*8*3*255 = 48960`. Copied as-is the colour term contributes at most 9% instead of 30%. Use the normalised metric in §11.2 and delete the constant. |
| 09-07 §3 probation | Strikes accrue at the start of the next scrape *or digest* | **Digest never strikes.** Only a manual scrape scores, and only when the user has actually reviewed. See §11.8 and HL-15. |
| 09-07 §4 Wayback | Set `sample_url` to the archive URL | Correct, but the spec never says where the **domain** comes from. `accept_url("https://web.archive.org/web/2008id_/http://x.example/")` returns `web.archive.org`, which is not blacklisted, so every resurrected site would collapse into one row. Domain always comes from the original URL. See HL-11. |
| 09-07 §2 vs 09-06 | 09-06 says "do not probe feeds during Discover" | 09-07 wins: probe feeds on insert, including Discover inserts. Discover still does not scrape images. |
| 09-06 scrape/hop caps | scrape 30 sources, hop cap 5 | Superseded: scrape 20, hop 3. Change the constants in `config.py`; do not change the tests, which pass `cap=` explicitly. |
| 09-06 non-goals | "no embeddings" | pHash is allowed and required. CLIP and learned embeddings remain banned. |
| Both specs | `USER_AGENT` should be `good-form/1.0` | `config.py` currently says `good-form/0.1`. Change it to `good-form/1.0 (local curator; +http://127.0.0.1:8000)`. |
| 09-07 layout | `apscheduler` for the digest cron | Not used. See HL-18. |

---

## 7. What the user does

1. Drops ~235 jpg/png/webp into the **seed root**, optionally with a `seed_notes.tsv` sidecar, in ungated `/admin`.
2. Sees clusters (target 15–20 medoids), a **coverage radius**, and the estimated Lens calls for this run, then **Discover New Sources**.
3. Approves or edits the **corpus vocabulary** that admin derived from his notes, which becomes the categorizer's tags.
4. Dead Lens URLs come back as 2004–2014 Wayback snapshots instead of vanishing.
5. **Mine Blogrolls**, then **Scrape** (RSS first) or weekly **digest** (latest 3 images per feed, zero SerpApi).
6. Reviews the grid with **J/K/Space/Enter**, zips keepers, Hall of Fame updates.
7. Runs Discover again later to spend the **next** Lens round on the least-covered corners of the corpus.
8. Exports **OPML** into NetNewsWire / Thunderbird / Feedly.
9. Optional: Connect Google Drive so seeds + gallery survive a dead HDD.
10. Watches `/logs` and provider lights (SerpApi, Brave, DDG, Wayback, Drive) to see what is down.

---

## 8. Hard locks

Each lock has an ID and a command that proves it. Section 17 makes you run all of them.

| ID | Lock | Proof |
| --- | --- | --- |
| HL-01 | SQLite file database, one `data/goodform.db`. No other DB engine. | `! grep -rniqE "pymongo\|psycopg\|sqlalchemy\|motor" --include=*.py --include=*.txt .` |
| HL-02 | A fresh `init_db()` creates every new table; an old DB `ALTER`s without losing rows. | `pytest -q tests/test_migrations.py` |
| HL-03 | Discover Lenses medoids only. For N > 20, Lens uploads per run ∈ [15, 20]. Never one call per file. | `pytest -q tests/test_cluster.py` |
| HL-04 | Lens spend is resumable and globally capped: `lens_budget_per_run` (18) and `lens_total_budget` (60), both admin-raisable, both always present. | `pytest -q tests/test_lens_rounds.py` |
| HL-05 | Fallback queries never consist of a bare number or a camera-noise token. | `pytest -q tests/test_query_terms.py` |
| HL-06 | Categorizer vocabulary is corpus-derived and admin-editable, with the hardcoded list as the floor. | `pytest -q tests/test_vocab.py` |
| HL-07 | First SerpApi 401/402/403/429/5xx/timeout/JSON error in a job switches the remainder of that job to Brave-if-keyed else DDG. No Lens retries. | `pytest -q tests/test_discover_and_hop.py` |
| HL-08 | Hop depth is 1. Hop cap default 3 medoid images. | `grep -n "HOP_IMAGE_CAP = 3" config.py` |
| HL-09 | Scrape HTML is last resort. Feeds win. Digest = 3 images/feed. | `pytest -q tests/test_digest.py tests/test_scraper_harvest.py` |
| HL-10 | The dead-site probe uses `net.probe`, not `net.fetch`, and distinguishes dead / blocked / unknown. | `grep -q "def probe" net.py && ! grep -qE "net\.fetch\|from net import fetch" wayback.py` |
| HL-11 | A resurrected source's `domain` comes from the original URL. `archive.org` can never become a source. | `pytest -q tests/test_wayback.py` |
| HL-12 | Wayback is inside `ingest_hit`, not a later plugin or optional job. CDX `from=2004&to=2014` only. | `grep -n "wayback" sources.py` |
| HL-13 | Probing is budgeted: ≤ 60 host probes and ≤ 25 CDX lookups per job, ≥ 1s between archive.org requests. | `pytest -q tests/test_wayback.py::test_probe_budget` |
| HL-14 | pHash Hamming < 5 drops a scrape **before** the cache write and **before** INSERT. Hamming 5 keeps. | `pytest -q tests/test_phash_gate.py` |
| HL-15 | Digest never strikes. A scrape cycle is scored only after the user has downloaded something. Three strikes → `probation`, `enabled=0`. | `pytest -q tests/test_probation.py` |
| HL-16 | Admin has no login. | `! grep -rniqE "clerk\|oauth2passwordbearer\|login_required\|requires_auth" --include=*.py .` |
| HL-17 | Banner and 88×31 strip use the section 14 blocks verbatim: same class names, same colours, `<marquee>` present. Width stays 468px; height may grow. | `pytest -q tests/test_chrome.py` |
| HL-18 | The digest cron is a daemon thread claiming its run through a `settings` row. No scheduler dependency. | `! grep -rniq --include=*.py --include=*.txt "apscheduler" .` |
| HL-19 | The app boots and every test passes with the Google libraries **not installed**. Drive state is then `skipped`. | `pytest -q tests/test_drive_optional.py` |
| HL-20 | `GET /api/directory.opml` exists and returns `rss` outlines with `xmlUrl`. | `pytest -q tests/test_opml.py` |
| HL-21 | The grid supports J / K / Space / Enter, not checkboxes alone. | `pytest -q tests/test_chrome.py::test_grid_keyboard_hint` |
| HL-22 | `/logs` and `/logs/{id}` exist. `/working/{id}` does not bounce home after 2s. | `pytest -q tests/test_logs.py` |
| HL-23 | No test touches the network. | `pytest -q` with the socket guard from §16 active |
| HL-24 | Server binds 127.0.0.1. Remote bind with ungated admin requires `GOODFORM_ALLOW_REMOTE=1`. | `pytest -q tests/test_bind_guard.py` |

---

## 9. Locked numeric defaults

`cluster_k_min=15`, `cluster_k_max=20`, `cluster_k_target=18`, `lens_budget_per_run=18`, `lens_total_budget=60`, near-dup merge Hamming ≤ 6 when N ≤ 20, `tight_cluster_threshold=0.15`, max 12 visual matches per medoid after policy, max 6 fallback queries, hop cap 3, mine 40, scrape 20 sources, 10 images/source (HTML) or 10/feed (scrape) or 3/feed (digest), pHash drop if Hamming < 5, probation at 3 strikes, Wayback 2004–2014, CDX ≤ 1 req/s, probe budget 60/job, CDX budget 25/job, short edge ≥ 400px, aspect 1:3–3:1, SerpApi JPEG ≤ 500KB, timeout 12s, probe timeout 4s HEAD / 8s GET, delay 0.35s, grid 400, `account.json` cache 300s, Hall of Fame 50.

Admin can raise every cap. There is always a cap.

`USER_AGENT = "good-form/1.0 (local curator; +http://127.0.0.1:8000)"`

---

## 10. Schema — migrate, never drop

Write `_add_column_if_missing(conn, table, column, ddl)` guarded by `PRAGMA table_info(<table>)`, and store `schema_version` in `settings`. `init_db()` must stay idempotent and cheap: it runs on import and on every job.

`sources.status`: `active | error | disabled | probation`.

Add on `sources`: `cycles_with_candidates INTEGER NOT NULL DEFAULT 0`, `cycles_without_save INTEGER NOT NULL DEFAULT 0`, `wayback_timestamp TEXT`, `live_url TEXT`, `last_digest_at TEXT`, `last_cycle_image_ids TEXT NOT NULL DEFAULT '[]'`, `last_cycle_at TEXT`.

Add on `images`: `phash TEXT`.

`jobs.kind` includes `digest`. `expansion_edges.via_type` includes `wayback`.

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
  notes TEXT,
  taken_at TEXT,
  lensed_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seed_clusters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  medoid_seed_id INTEGER,
  member_count INTEGER NOT NULL DEFAULT 0,
  mean_intra_distance REAL NOT NULL DEFAULT 0,
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

Providers: `serpapi`, `brave`, `ddg`, `wayback`, `drive`. States: `ok`, `skipped`, `degraded`, `down`.

Preserve: unique `sources.domain`, unique `images.image_url`, zip increments `saved_count` and `downloads_count` in one transaction, Hall of Fame = `downloads_count > 0`.

Also change `db.connect()` to close its connection deterministically (wrap in `contextlib.closing` or add an explicit `close()`), because clustering and probing open far more connections than the original code did.

---

## 11. Engine behaviour

### 11.1 Seed intake, notes, and vocabulary (`seedintake.py`, `vocab.py`)

List rasters (jpg/jpeg/png/webp) in the seed root and upsert `seeds` on `path`. Re-uploading the same filename **updates** the row; it must not raise `IntegrityError`.

**Notes sidecar.** If `seed_notes.tsv` exists in the seed root, parse it as `filename<TAB>notes`, ignoring blank lines and lines starting with `#`. Write into `seeds.notes`. If a Meta "Download Your Information" export is present instead (`posts_1.json`, either in the seed root or a `content/` subdirectory), read captions and timestamps from it into `seeds.notes` and `seeds.taken_at`. Notes are also editable per-seed in admin. Missing notes are normal and never an error.

**Vocabulary.** `vocab.py` derives candidate tags from all `seeds.notes`: lowercase, split on non-alphanumerics, drop the stoplist and any all-digit token, drop tokens shorter than 3 characters, count document frequency, keep terms appearing in ≥ 2 seeds, return the top 40 by frequency. Store the derived list in `settings` under `vocab_candidates` and the approved list under `vocab_approved`. `categorizer.tag_text` matches against **the hardcoded vocabulary plus `vocab_approved`**, never less than the hardcoded list, so `test_categorizer.py` stays green. Admin shows candidates with checkboxes and a free-text add. With no notes at all, `vocab_candidates` is empty and behaviour is exactly today's.

**Stoplist** (also used by the query builder): `img, image, images, photo, photos, pic, pics, dsc, dscn, screenshot, screen, shot, utc, jpg, jpeg, png, webp, untitled, copy, final, edit, edited, download, insta, instagram, post, posts, file, files, new, version, export`.

### 11.2 Clustering (`cluster.py`)

`import imagehash`. Two different hashes, never interchanged:

- **Seed clustering:** `imagehash.phash(img, hash_size=16)` → 256 bits, 64 hex chars.
- **Scrape/digest near-dup gate:** `imagehash.phash(img)` default → 64 bits, 16 hex chars.

**Colour feature.** 8×8×3 HSV histogram, then **L1-normalise it to sum 1.0** and store as JSON in `seeds.hist`.

**Distance.** Both terms are already in [0, 1], so the weighting is honest:

```
distance = 0.7 * (hamming / 256.0) + 0.3 * (l1 / 2.0)
```

`l1 / 2.0` because the maximum L1 distance between two distributions that each sum to 1.0 is exactly 2.0. Do **not** use the `156672` constant from the spec; it is wrong (see §6).

**Procedure.**

1. Empty seed root → log `No images in seed_images/`, finish `done`, not `error`, and make no Lens call.
2. Hash every file, upsert `seeds`.
3. `N ≤ 20`: one cluster per file, then merge any pair with pHash Hamming ≤ 6.
4. `N > 20`: build the full N×N distance matrix with numpy, then **average-linkage agglomerative**: repeatedly merge the closest pair of clusters until the count equals `clamp(cluster_k_target, cluster_k_min, cluster_k_max)`. Update distances by Lance-Williams average linkage: `d(ab, c) = (|a|*d(a,c) + |b|*d(b,c)) / (|a| + |b|)`. Break ties by scanning the upper triangle in ascending index order and taking the first strict minimum, so the result is deterministic across runs.
5. **Medoid** = the member with the minimum sum of distances to the other members. Tie-break on larger `min(width, height)`, then lower `seeds.id`.
6. Record `member_count` and `mean_intra_distance` (0 for singletons) on `seed_clusters`. A cluster is **tight** when `mean_intra_distance <= tight_cluster_threshold`, otherwise **loose**.

This is verified: at N=240 the matrix takes ~0.1s, the agglomeration ~0.2s, and it returns exactly K=18 identically on repeated runs. Run it in the job thread, never inline in a request handler.

### 11.3 Discover and resumable Lens rounds

A run Lenses at most `lens_budget_per_run` seeds, and never more than `lens_total_budget` cumulatively across all runs.

- **First run** (no seed has `lensed_at`): Lens the K medoids. For N > 20 that is 15–20 uploads (HL-03).
- **Later runs:** farthest-first traversal. Repeatedly pick the unlensed seed whose distance to its **nearest already-lensed seed** is greatest, until the budget is spent or nothing is unlensed. This spends each new round on the least-covered corner of the corpus rather than re-covering ground.
- Set `seeds.lensed_at` on every seed uploaded; set `seed_clusters.last_lensed_at` when a medoid is used.
- **Coverage radius** = the maximum over all seeds of the distance to that seed's nearest lensed seed. Report it in `/api/status` and on the admin cluster cards. It decreases monotonically as rounds are spent and tells the owner how much corpus is still unexplored.
- Admin has `Reset Lens rounds`, which clears `lensed_at` and `last_lensed_at`.

Compress each upload with the **existing** `sources.compress_for_serpapi` path to ≤ 500KB JPEG. Per medoid, ingest at most 12 `visual_matches` that pass `policy.accept_url`. Deduplicate hosts across the whole job before insert.

**Per-medoid accounting.** Log `medoid <seed id> matches=<n> blocked=<n> dead=<n> archived=<n> new=<n>` for every upload. This matters: Instagram-sourced images frequently return only the original post plus aggregator reposts, all of which `policy.py` blacklists, so a medoid can legitimately return 12 matches and yield 0 sources. Without this line the owner cannot tell a corpus mismatch from a broken API key.

**Hop.** Cluster the pool returned by `db.hop_candidates` with the same clusterer, preserving that function's existing filters and ordering as the tie-break, and Lens at most 3 medoids. Depth 1: never scrape or hop newly inserted domains in the same job.

### 11.4 Ingest and Wayback (`wayback.py`, called from `sources.ingest_hit`)

`policy.accept_url` first, keeping the existing blacklist and whitelist. Then probe the live URL.

**`net.probe(url, *, timeout_head=4, timeout_get=8) -> ProbeResult`** is new. `net.fetch` is unchanged and must not be used here (HL-10), because it collapses 403, 404 and connection errors all into `None` and discards the status code. `ProbeResult` carries `state`, `status_code`, `final_url` and `text_head` (first ~8KB), where `state` is:

- `dead` — NXDOMAIN, connection refused, timeout, HTTP 404/410/450, or a parked page
- `blocked` — HTTP 403 or 429; the host is alive and does not want us, so **do not** resurrect it
- `alive` — anything else that returned a body
- `unknown` — anything you cannot classify; treat as `alive` and do not resurrect

Parked phrases, case-insensitive, in title or body: `domain is for sale`, `buy this domain`, `parked free`, `godaddy.com/domainsearch`, `sedo.com`, `hugedomains`, `this domain may be for sale`.

**Budget (HL-13).** Deduplicate candidate **hosts** for the job and probe once per host, not once per URL, caching results in memory for the job's lifetime. Stop after 60 probes or 25 CDX lookups per job and log that you hit the budget. 20 medoids × 12 matches is 240 candidate URLs; unbudgeted, at a 0.35s delay and 12s timeouts, a single Discover would run for the better part of an hour.

On `dead`, query CDX at **≥ 1 second per archive.org request**, using a limiter dedicated to archive.org and separate from the global 0.35s delay:

```
GET https://web.archive.org/cdx/search/cdx?url={url}&output=json&from=2004&to=2014&filter=statuscode:200&collapse=digest&limit=5
```

Take a 2004–2014 snapshot. If there is none, log `no archive 2004-2014` and **do not insert the dead host**, and do not write an edge. Never fall back to a 2015-or-later snapshot. Fetch `https://web.archive.org/web/{timestamp}id_/{original}`.

**Identity (HL-11).** This is the trap in the spec. The stored `domain` is `accept_url(original_url)`. Only `sample_url` holds the snapshot URL; `live_url` holds the original and `wayback_timestamp` the CDX timestamp. Give `ingest_hit` keyword-only `live_url` and `wayback_timestamp` parameters. Additionally add `web.archive.org` and `archive.org` to `policy.BLOCKED_SUFFIXES` so a snapshot URL can never be ingested as a source by any other code path. Verified today: `accept_url("https://web.archive.org/web/20080512id_/http://cool.blog.example/page")` returns `web.archive.org` and is **not** blacklisted, which would collapse the entire resurrected directory into a single row.

Edge `via_type='wayback'`. Scrape archived pages when live is dead, resolving archived image URLs. The blacklist still applies on archive.org (no Pinterest via Wayback). On HTTP 429: log, mark Wayback `degraded`, skip remaining CDX for that job, finish ingesting URLs already probed.

### 11.5 Fallback

Order unchanged: Brave JSON if the key works, else DDG HTML. Max 6 queries. Templates `{term} personal blog`, `{term} zine archive`, `site:tumblr.com {term}`, plus `-pinterest -etsy -shutterstock -amazon -reddit`. The working/log message names the provider, e.g. `SerpApi unavailable (429); discovering via DuckDuckGo`.

**Term sourcing (HL-05), in order:** `seeds.notes` tokens → `vocab_approved` → existing directory tags → filename tokens **last**. Reject any term that is all digits or in the §11.1 stoplist. If after filtering there are no usable terms, log `no usable query terms; add seed notes or approve a vocabulary in /admin` and finish the job `done` with that message — **not** `error`, because the job did what it could and the owner needs an actionable instruction rather than a stack trace.

Missing `SERPAPI_API_KEY`: skip Lens immediately, log it, fall back.

### 11.6 Feeds, scrape, digest (`digest.py`)

On insert (including Discover inserts) and on Mine: discover RSS/Atom (`rel=alternate`, `/feed`, `/rss`, `/atom.xml`, `/index.xml`, Feedburner). One polite GET per new host. Discover still does not scrape images.

**Scrape.** If `feed_url` is set and the feed parses to ≥ 1 entry, harvest **only** from the feed. Fall back to homepage `<img>`/srcset only when there is no `feed_url` or the feed parses to zero entries, and log `html fallback` when you do. (The 09-06 spec and the v1 done-check disagreed here; this is the ruling.) Caps: 20 sources, 10 passing images.

**Digest.** `POST /jobs/digest`, `jobs.kind='digest'`: the latest 3 passing images per enabled working feed. Zero SerpApi. Sets `last_digest_at`.

### 11.7 pHash gate

After the 400px/aspect raster checks, and **before** the `scraped_cache` write and **before** the INSERT: `imagehash.phash(img)` at the default `hash_size=8`. Load all existing `images.phash` once per job. If any Hamming distance is **< 5**, drop and log `phash dup hamming={n} of image {id}`. Distance 5 keeps, 4 drops. Persist the hex on kept rows; NULL rows never match. Same gate on digest. Never use the 256-bit cluster hash here.

If a source produced raster-passing candidates but every one was dropped as a duplicate, log `<domain>: 0 new / <n> dup` and treat the cycle as having produced **no candidates**, so it earns no strike.

### 11.8 Probation (HL-15)

The spec's rule punishes the owner for running two scrapes in a row and, with the weekly cron on, disables the entire directory after three unattended weeks — which also starves the digest that caused it. The corrected rule:

- **Digest never strikes and never writes a cycle list.** Only a manual scrape does.
- At the **end** of a scrape, for each source that inserted ≥ 1 new image: set `last_cycle_image_ids` to those ids, set `last_cycle_at`, and increment `cycles_with_candidates`. No strike yet.
- At the **start** of the next scrape, a source's cycle is **scoreable only if the owner has reviewed since it was recorded** — that is, `settings.last_download_at > sources.last_cycle_at`. `last_download_at` is written by `db.record_downloads`.
  - Not scoreable: leave the list intact, change no counter, and move on.
  - Scoreable and every listed image still has `saved_count = 0`: `cycles_without_save += 1`.
  - Scoreable and any was saved: `cycles_without_save = 0`.
  - Either way, clear the list after scoring.
- At 3: `status='probation'`, `enabled=0`, logged. Probation sources are skipped by scrape and digest.
- Counters start at 0, there are no retroactive strikes, and admin restore sets counters to 0, `last_cycle_image_ids='[]'`, `status='active'`, `enabled=1`.

### 11.9 Drive (optional) (HL-19)

OAuth scope `https://www.googleapis.com/auth/drive.file`, localhost redirect. Folders `good-form/seeds` and `good-form/gallery`. Sync seeds down into the seed root, then recluster. On save or zip, copy originals to `gallery/{domain}/` and upload. Optional `goodform.db` backup to `good-form/data/`.

**`drive.py` must import `googleapiclient` and `google_auth_oauthlib` lazily, inside the functions that use them.** A module-level import makes the whole app fail to boot when the libraries are absent, which violates the lock. Missing credentials or missing libraries → `drive` state `skipped`, and everything else runs.

### 11.10 Credits badge

`GET https://serpapi.com/account.json?api_key=`, cached 300s in-process. `remaining = max(0, searches_per_month - this_month_usage)`, `plan = searches_per_month`. Lens-today counter comes from local job records. Domain count is `SELECT COUNT(*) FROM sources`. Never call `account.json` per image, and never at import time — `/api/status` takes an injectable fetcher and falls back to the last cached value or `SERPAPI SKIPPED`.

---

## 12. HTTP surface

Existing, unchanged: `POST /jobs/discover|mine|scrape|hop`, `POST /api/download`, `GET /api/images/{id}/file`, `GET /media/{id}`, `POST /api/sources/{id}/enabled`.

**Pages**

| Route | Purpose |
| --- | --- |
| `GET /` | Directory + grid chrome |
| `GET /admin` | Ungated control room |
| `GET /logs`, `GET /logs/{id}` | Job history and full log, no bounce home |
| `GET /working/{id}` | Live tail while running; on finish show the log plus a link home |

**JSON API** — the React UI reads all of its data from here. v1 omitted these and left the UI with no data layer; do not invent alternatives.

| Route | Returns |
| --- | --- |
| `GET /api/status` | provider states, remaining/plan, lens today, lens spent/budget, coverage radius, domain count, seed and cluster counts |
| `GET /api/directory` | tags with their sources, `Unsorted` last, each with feed/wayback/probation flags |
| `GET /api/sources/{id}` | detail: tags, sample/feed/live/wayback URLs, edges in and out, images |
| `GET /api/images` | grid rows (limit 400), filters `tag`, `domain`, `min_short_edge` |
| `GET /api/hall-of-fame` | top 50 by `downloads_count` |
| `GET /api/jobs`, `GET /api/jobs/{id}` | history and one full log |
| `GET /api/clusters` | cluster cards: members, medoid, tight/loose, `mean_intra_distance`, next-run estimate |
| `GET /api/vocab`, `PUT /api/vocab` | derived candidates and the approved list |
| `GET /api/settings`, `PUT /api/settings` | caps, recipes, policy lists, paths |
| `GET /api/directory.opml` | OPML 2.0 (`?all=1` includes probation/disabled) |
| `POST /api/seeds` | multipart upload |
| `DELETE /api/seeds/{id}` | remove a seed |
| `PUT /api/seeds/{id}/notes` | edit one seed's notes |
| `POST /api/seeds/recluster` | returns a job id; never runs inline |
| `POST /api/seeds/reset-lens-rounds` | clears `lensed_at` |
| `POST /api/sources` | manual URL through `accept_url` + categorizer |
| `POST /api/sources/{id}/restore` | probation restore |
| `POST /api/discover/dry-run` | clusters, next medoids, would-be hosts; zero inserts, zero Lens |
| `POST /jobs/digest` | run the digest now |
| Drive connect/sync | as needed |

**OPML 2.0.** `head/title` = `good-form`. Outlines with `type="rss"`, `xmlUrl`, `htmlUrl`, and `text`/`title`. Content-Type `text/x-opml+xml`, `Content-Disposition: attachment; filename="good-form-directory.opml"`. Default set: enabled sources with a `feed_url` and status `active` or `error`. An empty directory returns HTTP 200 with valid OPML and an empty `<body></body>`.

---

## 13. UI

`frontend/` is **Vite + React + TypeScript**, building to `frontend/dist`. FastAPI serves `frontend/dist` at `/` when `frontend/dist/index.html` exists and otherwise renders the Jinja template — both carry the same banner DOM, so the app is never broken by an unbuilt frontend. Single origin, so no CORS. Dev uses the Vite proxy to `127.0.0.1:8000`. `frontend/node_modules` and `frontend/dist` are gitignored. Every component prop gets a real TypeScript interface, and every list view has explicit loading, empty, and error states.

**Directory body.** Yahoo category directory: H2 per tag, `Unsorted` last, enable checkboxes, feed/wayback/probation badges, Hall of Fame sidebar `[rank] domain — N saved`. Times/Georgia, default blue/purple links, `#ffffcc` sidebar, tables, "you are here". Source detail page.

**Grid.** Thumbnails with `loading="lazy"`, WxH, domain link, select, single download. Filters: tag, domain, min short edge. Hint row: `J/K move  SPACE mark  ENTER zip`. Header actions: Discover, Mine Blogrolls, Scrape Active Feeds, Visual Hop, Digest, Select All / Deselect All, Download Selected, Download All, Export OPML.

**Keyboard.** `role="grid"` with roving `tabIndex`, `aria-selected` on cells, and a 3px inset black focus ring. J/ArrowDown next, K/ArrowUp previous, Space toggles, Enter zips the selection. The handler must:

- ignore the event when the target is an `input`, `textarea`, `select`, or `contenteditable`;
- ignore it when `metaKey`, `ctrlKey`, or `altKey` is held, so Cmd+Space and Ctrl+Enter still belong to the OS;
- call `preventDefault()` on Space, otherwise a focused checkbox toggles twice and cancels itself out;
- on Enter with an empty selection, show `nothing selected` and **not** fire the request, which would 400.

**Admin.** 1999 webmaster tools: nested tables and `[*]` / `[DOWN]` text, not pill chips. Recipes, caps, policy lists seeded from the current `policy.py` and `categorizer.py`, vocabulary approval, seed root and notes, Drive, cluster cards with tight/loose and coverage radius, dry-run, probation restore, settings JSON import/export with no secrets.

**Policy profiles.** Ship the current blacklist as profile `indie-web` (the default) and add `archival-research`, which unblocks `flickr.com`, `staticflickr.com`, `wikimedia.org` and `wikipedia.org` and adds whitelist bias for `.edu`, `archive.org` collections and museum/library hosts. The owner picks the profile in admin. Blocking Flickr Commons and Wikimedia Commons is right for a vaporwave corpus and wrong for an archival one, and the corpus here is the latter kind.

**Accessibility.** The verbatim `<marquee>` is the default. An admin `reduce_motion` setting swaps in static text inside the identical `.banner-title` markup, so the lock holds by default and the page is still usable by people who need it. `.web1-banner-wrapper` gets `overflow-x: auto` below 480px; the banner itself stays exactly 468px. Note that React passes `scrollamount` through to `<marquee>` unchanged — do not "fix" it into a CSS animation.

**Logs.** History table plus full scrollback.

**Binding (HL-24).** The server binds `127.0.0.1`. If the bind host is not loopback and `GOODFORM_ALLOW_REMOTE` is not `1`, refuse to start with a clear message, because `/admin` has no login and can set filesystem paths.

---

## 14. VERBATIM CHROME — copy these blocks

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

## 15. Build order — do not skip, do not reorder

Emit the section 1 report block after each phase.

| # | Phase | Done check |
| --- | --- | --- |
| 1 | **Migrations + network guard.** All new tables and columns, `_add_column_if_missing`, `schema_version`, `db.connect()` closing, the §16 socket guard, `USER_AGENT` → 1.0, caps → scrape 20 / hop 3, `.env.example` and `.gitignore` updates. | `pytest -q tests/test_migrations.py` and a fresh + an old DB both open cleanly with no row loss |
| 2 | **Seed intake, notes, vocabulary, query terms.** `seedintake.py`, `vocab.py`, TSV and DYI parsing, stoplist, term sourcing order. | `pytest -q tests/test_vocab.py tests/test_query_terms.py` |
| 3 | **`cluster.py`.** Normalised distance, deterministic agglomeration, medoids, tightness. | `pytest -q tests/test_cluster.py` — 235 near-dups collapse to K ∈ [15,20], twice identically |
| 4 | **Discover + Hop + Lens rounds.** Medoid-only first run, farthest-first later rounds, budgets, coverage radius, per-medoid accounting, circuit break to fallback. | `pytest -q tests/test_lens_rounds.py tests/test_discover_and_hop.py` — 30 near-dup images produce ≤ 20 mock Lens calls |
| 5 | **`net.probe` + `wayback.py` in ingest.** States, parked detection, CDX 2004–2014, identity from the original URL, probe/CDX budgets, archive.org rate limit. | `pytest -q tests/test_wayback.py` — a mocked 404 plus CDX JSON inserts an archive `sample_url` under the **original** domain |
| 6 | **Feed-first scrape + `digest.py`.** HTML last resort, digest 3/feed, cron thread. | `pytest -q tests/test_digest.py` — a source with a working `feed_url` never touches homepage `<img>` |
| 7 | **pHash gate.** Drop before cache and before INSERT. | `pytest -q tests/test_phash_gate.py` — two URLs, one raster, one row |
| 8 | **Probation.** Digest never strikes; scoring requires a review. | `pytest -q tests/test_probation.py` |
| 9 | **Status, logs, `account.json`.** `/api/status`, `/logs`, `/logs/{id}`, 300s cache, injectable fetcher. | `pytest -q tests/test_logs.py tests/test_status.py` |
| 10 | **React UI + OPML + chrome + admin.** Full JSON API, directory, grid with J/K/Space/Enter, verbatim banner and 88×31 strip, ungated admin, vocabulary approval, policy profiles, Drive-skipped path, bind guard. | `pytest -q tests/test_opml.py tests/test_chrome.py tests/test_drive_optional.py tests/test_bind_guard.py` |
| 11 | **Self-check.** Run every command in section 17. Fix until all pass. | `pytest -q` green and all HL rows PASS |

---

## 16. Tests — all mocked, no live network

Add this autouse fixture to `tests/conftest.py` first, in phase 1. It turns HL-23 from a promise into a mechanical failure:

```python
import socket
import pytest

@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise RuntimeError("test attempted a real network connection")
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
```

Keep every existing test passing. Add:

- `test_migrations.py` — fresh DB creates all tables; a DB built from the old schema `ALTER`s with zero row loss; `init_db()` twice is a no-op
- `test_cluster.py` — 235 synthetic near-dup groups collapse to K ∈ [15, 20]; the medoid is the minimum-summed-distance member; two runs give identical clusters; 10 distinct seeds give 10 candidates except Hamming ≤ 6 merges
- `test_lens_rounds.py` — first run Lenses only medoids; a second run Lenses different, farther seeds; `lens_total_budget` is never exceeded; coverage radius decreases
- `test_query_terms.py` — `2019-03-15_10-22-33_UTC.jpg` alone yields **no** query; notes yield real terms; all-digit and stoplist terms are rejected; the no-terms job finishes `done` with the actionable message
- `test_vocab.py` — candidates derive from notes with a document-frequency floor of 2; approved terms tag sources; the hardcoded vocabulary still works with zero notes
- `test_wayback.py` — CDX mock plus parked HTML creates a `wayback` edge whose `sources.domain` is the **original** host, never `web.archive.org`; empty 2004–2014 inserts nothing; a 2024-only CDX response inserts nothing; `403` is `blocked` and is not resurrected; `test_probe_budget` proves the 60/25 caps and one probe per host
- `test_phash_gate.py` — identical raster at two URLs gives one row, and the drop happens before the cache write; Hamming 5 keeps, 4 drops
- `test_digest.py` — 3 passing images per feed; a source with a working feed never hits homepage `<img>`
- `test_probation.py` — three scrape cycles whose images are never saved, **with a download recorded between cycles**, reach probation with `enabled=0`; without any download, no strike accrues; digest never strikes; restore clears everything
- `test_opml.py` — 200 with and without outlines; `?all=1` includes probation; outlines carry `xmlUrl`
- `test_status.py` — a mocked `account.json` drives remaining/plan; a missing key shows `SERPAPI SKIPPED`; the endpoint makes no call at import time
- `test_logs.py` — `/logs` and `/logs/{id}` render a finished job's full log
- `test_chrome.py` — `GET /` contains `web1-banner`, `banner-credits`, `<marquee`, and five `retro-badge` spans; `test_grid_keyboard_hint` finds the `J/K move` hint
- `test_drive_optional.py` — with the Google modules absent from `sys.modules` and un-importable, the app still boots and `drive` reports `skipped`
- `test_bind_guard.py` — a non-loopback host without `GOODFORM_ALLOW_REMOTE=1` is refused
- Existing zip-increment and Hall-of-Fame tests still pass

---

## 17. Self-check — run every one of these before you report done

Run `python3 -m pytest -q` and confirm the count is **above 28** and nothing failed. Then run each proof command in the section 8 table and record PASS or FAIL. Then confirm every line below is **false**:

- Discover uploads more than 20 seeds to SerpApi in one run, or one call per file when N > 20
- Lens spend is not resumable, or there is no total budget
- Fallback queries are built from filenames when notes or an approved vocabulary exist, or a query is a bare number
- The categorizer vocabulary is still only the hardcoded 22 words
- MongoDB, Clerk, Stripe, a scheduler library, or a login screen appeared
- Wayback is a stub, a TODO, or a separate optional job
- A resurrected source's `domain` is `web.archive.org`
- The dead-site probe is built on `net.fetch`
- Probing is unbudgeted, or archive.org is hit faster than 1 req/s
- Scrape writes the cache before the pHash gate
- Digest awards probation strikes, or a strike accrues without a review
- There is no `GET /api/directory.opml`
- The React UI has no JSON data endpoints, or the grid has checkboxes only and no J/K/Space/Enter
- Space double-toggles a focused checkbox, or Enter on an empty selection fires a request
- `/working/{id}` hard-redirects home in 2s, or `/logs` does not exist
- The 468×60 banner is missing `<marquee>` or was restyled into a card or hero
- The 88×31 strip is missing or uses different dimensions
- The credit line never reads remaining/plan or `SERPAPI SKIPPED`
- The digest job is missing
- Drive is required to boot, or `drive.py` imports Google libraries at module level
- Any test touches the live network
- Hop depth > 1, or the hop cap is still 5
- HTML scrape runs even though `feed_url` works and the feed has entries
- An existing test was edited, weakened, or deleted

Work through phase 11. Finish the engine before polishing copy.

---

## Appendix — follow-up pastes if you stop early

**A. Skin fidelity.** Restore the verbatim banner and badge HTML and CSS from section 14. No Tailwind on `.web1-banner`. Keep the Times directory tables.

**B. OPML.** `GET /api/directory.opml` must import into Feedly and NetNewsWire: `rss` outlines with `xmlUrl`.

**C. Drive OAuth.** localhost redirect, `drive.file` scope, lazy imports, `skipped` state without secrets or libraries.

**D. Wayback 429.** One backoff, mark `degraded`, finish ingesting URLs already probed.

**E. Credit cache.** `account.json` at most once per 300s; the banner reads `/api/status`.

**F. Dry run.** `POST /api/discover/dry-run` returns clusters, the medoids the next round would Lens, and would-be hosts, with zero inserts and zero Lens calls.

**G. Hop clustering.** Group unsaved dud images and Lens at most 3 medoids.

**H. Lens rounds.** Farthest-first traversal for round 2+, coverage radius on `/api/status` and the admin cluster cards, and `Reset Lens rounds`.

**I. Corpus vocabulary.** Derive candidates from `seeds.notes`, approve them in `/admin`, and use them for both tagging and fallback query terms.
