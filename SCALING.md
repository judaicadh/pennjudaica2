# Scaling the Penn Judaica Portal

This document plans the move from "1,749 items in a 55 MB `data.js`" to
"tens of thousands of **Judaica** items across OPenn, finding aids, and
Colenda" without giving up the static, no-server deployment that makes the
site sustainable in the first place.

> **Status (Phase 1+2 implemented).** The build pipeline (`harvest_openn.py`,
> `harvest_findingaids.py`, `build.py`) is in place. `data.js` is replaced by
> `items.json` (search/card fields) + `records/<id>.json` (per-item page data,
> lazy-loaded). On the current 1,748-item OPenn dataset the initial page load
> dropped from **52 MB to 180 KB gzipped** (~290× smaller), with average shard
> size 30 KB. See §11 below for the as-built layout.

**Realistic target scale.** With OPenn + finding aids (hybrid mode,
component-level) + Colenda, expect ~10-30k Judaica items at the high end.
Franklin (the catalog) is intentionally out of scope for now; if it's
added later it would push the total into the 100k range, and the
architecture below is built to handle that without changes.

**Scope rule.** Every harvester is Judaica-scoped from the start. We never
pull "all of Penn" and filter later — the filters belong at the source. The
specific filters per system are documented in §4 (finding aids), and the
analogous rule applies to Colenda when that source is added.

It is the architectural complement to `HARVESTING.md` (which describes the
protocols) and `harvest.py` (which implements the OPenn pull).

## 1. Why the current shape can't scale

The browser today reads one file, `data.js`, that contains *every* record
inline. At 1,749 items this is already 55 MB. Three things break as it grows:

| At ~20k items | Current shape | Effect |
|---|---|---|
| `data.js` on the wire | ~600 MB uncompressed, ~120 MB gzipped | Multi-minute page load; CDN bills spike. |
| JS heap | 80-160 MB | Sluggish on mobile, noticeable jank on desktop. |
| `Array.filter()` per keystroke | O(n) over 20k records | 40-80 ms typing lag; facets re-render slowly. |
| Leaflet with 20k markers | One DOM node per marker | Map view stutters; clustering needed. |

(At 100k items every row gets multiplied by 5×. The point is that the
current shape doesn't have headroom even for the modest scale we're
actually targeting.)

The fix is to **move work from runtime to build time**. The browser should
read a small, pre-indexed view of the data and fetch detail records only
when the user actually opens one.

## 2. Target architecture

Everything stays static. Netlify (or GitHub Pages, or any CDN) serves a
build folder. The harvester runs on a schedule, builds the folder, and
publishes it.

```
                                       ┌────────────────────────────┐
   Penn source systems                  │ Harvester (GH Actions cron)│        Netlify CDN
   ──────────────────                   │  Python, scheduled weekly  │        ───────────
   OPenn (HTML + IIIF)  ─────────────▶  │                            │  ──▶   /index/        (Pagefind shards)
   Finding Aids (HTML)  ─────────────▶  │  harvest → normalize       │  ──▶   /records/      (one JSON per item)
   Colenda (OAI-PMH)    ─────────────▶  │  → dedupe → enrich         │  ──▶   /aggregates/   (facets, map, timeline)
                                       │  → build static artifacts  │  ──▶   /             (HTML + JS)
                                       └────────────────────────────┘
```

### 2.1 What the harvester produces

```
/dist
  /index/                          ← Pagefind: sharded, lazy-loaded search index
    pagefind.js
    pagefind.<lang>.pf_meta
    fragment/*.pf_fragment
    index/*.pf_index
  /records/                         ← one detail JSON per item, lazy-loaded
    00/000001.json
    00/000002.json
    ...
    fa/UPENN_CAJS_CJS.ARCMS52.json
  /aggregates/
    summary.json                    ← { total, lastHarvest, sources }
    facets.json                     ← top-N values + counts for every facet
    map.json                        ← lat/lng clusters with item counts
    timeline.json                   ← decade buckets with counts
    featured.json                   ← curated highlight IDs
  index.html, app.js, styles.css    ← unchanged frontend shell
```

`data.js` goes away. Nothing the browser ever loads exceeds a few hundred KB.

### 2.2 The search index: Pagefind

We recommend [Pagefind](https://pagefind.app/) over MiniSearch / Lunr /
FlexSearch for one reason: at 100k+ docs, the *index itself* gets large, and
Pagefind is the only static engine that **shards the index and loads only
the shards needed for the current query**. A user typing "ketubah" downloads
maybe 50-100 KB of index, not the whole thing. It also has built-in faceting,
which we currently compute in JavaScript over every item on every keystroke.

Trade-offs:
- Pagefind is built from the *rendered HTML* of pages by default, but it
  also accepts a JSON-driven indexing mode (`pagefind --site dist` with
  `data-pagefind-body` attributes, or the NodeJS API for fully programmatic
  indexing). We'll use the programmatic API to index from our normalized
  JSON.
- Pagefind is a Rust binary; it runs in the GitHub Actions job, not in the
  user's browser. The browser just loads `/index/pagefind.js`.

### 2.3 Detail records, lazy-loaded

Each item becomes one small JSON file (typically 1–5 KB):

```
/records/<bucket>/<id>.json
```

Bucketing by the first two hex chars of a hashed ID keeps any one directory
under ~1,000 files (fine for Netlify and for Git). The frontend fetches a
record only when the user opens its modal — so 100,000 records cost nothing
unless someone clicks them.

### 2.4 Pre-computed aggregates

The map view, timeline view, and facet counts are O(n) operations today.
We pre-compute them at build time:

- **`facets.json`** — for each facet (collection, format, region, language,
  era), the top 200 values with their counts. This is what the sidebar reads.
  When the user combines facets, Pagefind narrows the index and returns
  *filtered* counts; the JSON is only the unfiltered baseline.
- **`map.json`** — places grouped by lat/lng with item counts. Leaflet draws
  ~200-2,000 markers instead of 100,000. Clicking a marker fires a Pagefind
  query for `place == X` to load the actual items.
- **`timeline.json`** — items bucketed by decade. The timeline view renders
  a histogram, and clicking a bar opens a search for that decade.

## 3. Frontend refactor (small surface area)

Today `app.js` reads `window.PJP.items` directly everywhere. We collapse
that into one async data adapter and leave the views alone:

```js
const PJP = {
  async search(q, filters, page) {   // → { items, total, facets }
    // uses Pagefind under the hood
  },
  async getItem(id) {                // → full record
    // fetch /records/<bucket>/<id>.json, cache in memory
  },
  async getFacets()      { /* /aggregates/facets.json   */ },
  async getMap()         { /* /aggregates/map.json      */ },
  async getTimeline()    { /* /aggregates/timeline.json */ },
  async getSources()     { /* /aggregates/summary.json  */ },
  async getFeatured()    { /* /aggregates/featured.json */ },
};
```

The five views (search, map, timeline, highlights, saved), the modal viewer,
URL state, saved items, sort, advanced search — all keep their existing
shape. They each gain `await` in a few places.

A back-compat shim can keep the old synchronous `window.PJP.items` array
*populated by the current search result page only* during the migration so
we can swap views one at a time without a big-bang rewrite.

## 4. Finding aids harvester

`findingaids.library.upenn.edu` is a Blacklight/Rails app sitting on Solr,
backed by EAD finding aids harvested from ArchivesSpace and other partners.
It does not expose JSON publicly, but the HTML is regular and paginated,
and every record has a stable URL: `/records/<ID>`.

### 4.1 Discovery (which records to harvest)

We union three strategies and dedupe by record ID. Each is just a paginated
HTML scrape of `/records?...&per_page=100&page=N`:

**(a) Subject keyword search** — multiple passes:
- `q=judaica`
- `q=jews`
- `q=hebrew`
- `q=yiddish`
- `q=zionism`
- `q=ladino`
- `q=judaism`
- `q=sephardic`
- `q=ashkenazi`

**(b) Language facet:**
- `f[languages_ssim][]=Hebrew`
- `f[languages_ssim][]=Yiddish`
- `f[languages_ssim][]=Ladino` (if present)
- `f[languages_ssim][]=Judeo-Arabic` (if present)

**(c) Repository allowlist** — Penn Judaica-specific:
- `University of Pennsylvania: Kislak Center for Special Collections, Rare Books and Manuscripts`
- `University of Pennsylvania: Archives at the Library of the Katz Center for Advanced Judaic Studies`
- (optionally) `University of Pennsylvania: University Archives and Records Center`

**(d) Curated IDs** — `findingaids_curated_ids.txt` in the repo; one ID per
line. This is the escape hatch for collections that don't surface via (a)-(c)
but that you want to include.

The HTML head exposes `meta-totalResults: N` so we always know when we've
paged through everything.

### 4.2 Record extraction

Each `/records/<ID>` page has a predictable structure. We parse:

| Field | Source on the page |
|-------|--------------------|
| `id` | URL last segment (e.g. `UPENN_CAJS_CJS.ARCMS52`) |
| `title` | First `<h1>` |
| `collection` / `repository` | "Held at:" link |
| `callno` | "Call Number:" |
| `extent` | "Extent:" |
| `lang` | "Language:" |
| `dateText` / `year` | "Date:" (parse year range, take earliest) |
| `desc` | "Abstract:" |
| `creator` | "Creator" / "Finding Aid Author" if present |
| `people[]` / `corpnames[]` / `subjects[]` / `places[]` / `genres[]` | "Name and Subject Headings" lists |
| `place`, `region`, `lat`, `lng` | first matching `place` against the existing GAZETTEER |
| `srcUrl` | the page URL |
| `source` | `findingaids-kislak`, `findingaids-cajs`, `findingaids-other` |
| `type` | `Finding aid` (always) |

### 4.3 Hybrid mode — items inside the inventory

For finding aids with a "Collection Inventory" that contains a digitized
component (a `<dao>` in EAD, surfaced on the HTML as a "View digital object"
or thumbnail link), we emit additional items at the component level:

- `id` = `<finding-aid-id>__c<n>`
- `title` = component title (e.g. "Correspondence 1984")
- `desc` = component's "Scope and Contents" text
- `parentId` = the finding aid ID
- `parentTitle` = the finding aid title
- `pages[]` = images discovered on the DAO link (IIIF if available)

If the component is **not** digitized, we skip it — the parent finding aid
record already covers it in search.

This matches the user's hybrid choice from our earlier conversation:
top-level finding aid as one record, plus any digitized component that has
an associated image.

### 4.4 Politeness

200 ms between requests, identifiable User-Agent, retry-with-backoff on
5xx — same shape as the existing OPenn harvester.

## 5. Cross-source dedupe

The same physical item can be described in OPenn *and* a Finding Aid (and
later, Colenda). We dedupe in a normalize step keyed on, in priority order:

1. IIIF manifest URL (strongest — exact match means same item)
2. OPenn object identifier (`<repo>/<obj>`)
3. Call number + repository (matches OPenn ↔ Finding Aid)
4. Fingerprint `(title, creator, year, language)` with fuzzy match

When two records merge, the resulting item keeps the richest field from each
side (OPenn gives images and pages; the Finding Aid gives biography, scope,
and subject headings).

## 6. The build pipeline

One script per source, all writing JSONL into `/raw`, then a unified
normalize/dedupe/aggregate/index step:

```
harvest_openn.py          --out raw/openn.jsonl
harvest_findingaids.py    --out raw/findingaids.jsonl
harvest_colenda.py        --out raw/colenda.jsonl      (Phase 4, optional)
build.py                  raw/*.jsonl  → dist/
   ├─ normalize.py        (apply schema, geocode)
   ├─ dedupe.py           (key cascade above)
   ├─ aggregate.py        (facets.json, map.json, timeline.json)
   ├─ shard_records.py    (write /records/<bucket>/<id>.json)
   └─ pagefind index dist/ (Pagefind CLI builds /index/)
```

Each harvester is independent — if Finding Aids is down on Monday, the OPenn
items still rebuild and the deploy still happens with stale finding aid data.
`build.py` *refuses to write* if it would produce zero items (same safety
rail as the existing OPenn harvester).

## 7. GitHub Actions + Netlify

```
.github/workflows/harvest.yml
  on:
    schedule: [{ cron: "0 5 * * 1" }]   # Mondays 5am UTC
    workflow_dispatch: {}
  jobs:
    harvest:
      runs-on: ubuntu-latest
      steps:
        - checkout
        - setup-python
        - pip install -r requirements.txt
        - run: python harvest_openn.py --out raw/openn.jsonl
        - run: python harvest_findingaids.py --out raw/findingaids.jsonl
        - run: python build.py raw/ dist/
        - setup-node                                  # for pagefind
        - run: npx pagefind --site dist
        - run: |
            curl -X POST -d {} ${{ secrets.NETLIFY_BUILD_HOOK }}
```

Netlify watches the `gh-pages` (or `dist`) branch; the hook just kicks a
fresh deploy from the published artifacts. No build needed on Netlify —
GitHub Actions already produced `dist/`.

## 8. Phased rollout

We can ship this incrementally without breaking the running site:

### Phase 1 — Refactor the data layer (existing data only)
1-2 days. Same 1,749 items, new pipeline. Page load goes from 55 MB to
~2 MB initial. Search latency improves. This is the foundation for everything
that follows.

- Add `build.py`
- Switch `app.js` to the async `PJP` adapter
- Keep `data.js` around briefly as a compatibility shim
- Verify all five views work

### Phase 2 — Finding aids harvester
1-2 days. Write `harvest_findingaids.py`. Run it. Expect 200-1,000 new items
(top-level + digitized components). Confirm dedupe doesn't double-count
anything that's also in OPenn.

- Add `findingaids_config.yml` (keywords, languages, repos, curated IDs)
- Update `SOURCES` in normalize step
- Update front-end source-color map
- Update README and HARVESTING.md

### Phase 3 — Scale tests
1 day. Generate a synthetic Judaica corpus (duplicate existing items with
new IDs and randomized fields) to land at 20k, 50k, 100k items. Watch index
size, search latency, map render time. Tune Pagefind options. We *don't*
expand scope to non-Judaica items just to fake scale.

### Phase 4 — Colenda (optional)
2-3 days. Judaica-scoped from day one — Colenda's OAI-PMH endpoint exposes
sets, and we'd pull only the Judaica-relevant sets (Ketubot, Schoenberg
Manuscripts, etc.) rather than the whole repository. Franklin (the catalog)
is intentionally out of scope.

### Phase 5 — Automate
Half day. GitHub Actions cron + Netlify build hook. The site refreshes
itself on Mondays.

## 9. What changes for users

Nothing visible until Phase 4. Same UI, same URL shape (the share links keep
working). What they get:

- Page load drops from 55 MB to ~2 MB.
- Search stays snappy as the collection grows.
- Map and timeline scale to any size because they're pre-aggregated.
- A new "Finding Aid" type in the facet sidebar.
- Component-level records link back to their parent finding aid via a
  "Part of: [collection title]" line in the modal.

## 10. Files this plan introduces

## 11. As-built layout (what shipped)

The repo today:

```
index.html                        loads MiniSearch (CDN), app.js, items.json
styles.css                        unchanged
app.js                            async load of items.json, MiniSearch index,
                                  lazy-loads records/<id>.json on modal open
items.json                        ~1 MB raw / 180 KB gzipped — sources, light
                                  items (search/card fields), featured ids
records/<id>.json                 per-item page-image arrays (1748 shards,
                                  avg 30 KB) — fetched only when the modal opens
data.js                           DEPRECATED placeholder; safe to delete
harvest_openn.py                  emits raw/openn.jsonl  (OPenn — Judaica-scoped)
harvest_findingaids.py            emits raw/findingaids.jsonl  (Finding Aids)
build.py                          reads raw/*.jsonl, dedupes, writes items.json
                                  + records/<id>.json shards
findingaids_curated_ids.txt       optional curated IDs (one per line) appended
                                  to the finding-aids discovery union
requirements.txt                  requests
.gitignore                        raw/ (intermediate), __pycache__, etc.
netlify.toml                      publish=".", no build, cache headers
.github/workflows/harvest.yml     weekly cron: harvest + build + commit
SCALING.md                        this document
HARVESTING.md                     points to the new scripts
README.md                         updated to reflect the new pipeline
```

To run the pipeline locally:

```
pip install -r requirements.txt
python harvest_openn.py
python harvest_findingaids.py
python build.py
# items.json + records/*.json now ready to deploy
```

Use `--limit N` on either harvester for a fast smoke test.
