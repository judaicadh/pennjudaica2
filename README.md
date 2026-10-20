# Penn Judaica Portal

An independent discovery prototype joining Penn Digital Collections, OPenn Judaica,
and archival finding aids. Not an official Penn Libraries service.

## Run locally

```sh
python3 -m http.server 8765
```

Open http://localhost:8765. No frontend build is required.

## Refresh the index

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python harvest_openn.py
.venv/bin/python harvest_digitalcollections.py
.venv/bin/python harvest_findingaids.py
.venv/bin/python build.py
```

Digital Collections uses the current `digitalcollections.library.upenn.edu/items.json`
search endpoint and the repository’s public `/v1/items/<uuid>?assets=true`
response for full metadata and ordered image assets. Item detail JSON and IIIF
Presentation 3 manifests are retained as a fallback.
Discovery paginates the entire collection facet and includes named Judaica,
Jewish, Hebrew, Yiddish, Ladino, Leeser, Morais, Genizah, Ketubah, and Katz
collections. Explicit scopes also include both Kaplan Judaica collections,
Kaplan/Leeser, Morais, Cairo Genizah, and Gratz-Mandell Jewish Music. Seventeen
keyword passes broaden coverage beyond these collections. Independent sort orders recover pagination gaps caused by tied values. Each scope validates
its union of unique IDs against Penn’s reported total; the import then verifies that every
discovered ID was downloaded. This covers the configured scope, not a guaranteed
identification of every Judaica-related object in Penn’s entire repository.

`--limit N` on an importer creates a development sample. Run Digital Collections
without that flag to import all scoped results. Up to four concurrent workers
fetch full metadata and ordered image assets. Downloaded items are cached in
`raw/.digitalcollections-cache/`; `--resume` reuses a previously verified discovery
checkpoint after an interrupted run. Normal runs rediscover the current source
results and reuse cached item metadata. Remove the cache to refresh all metadata.
The last successful raw output is replaced only after the import succeeds.

The completed October 19, 2026 import contains **21,731 Digital Collections
records**, validated against 19 named collection scopes and 17 keyword scopes.
Two records have no available image manifest and remain searchable.

`raw/digitalcollections.audit.json` records per-scope reported/discovered counts,
unique discovered/imported totals, unavailable manifests, and timestamps. Its
coverage report is included in `items.json` and shown in the interface. A 403/404
manifest does not discard a searchable metadata record. Finding aids still contain
a sample of 30 records; OPenn uses the existing real harvested dataset.
Counts in the interface reflect primary records after deduplication; merged source
links remain visible on the record. The build timestamp is not a per-source harvest date.

Finding-aid keyword and language searches include regional partners. Only the Katz
Center is included as a whole repository; Kislak is searched by topic and language
so unrelated archives are not all imported. Finding aids describe archival
collections and do not imply online access to their contents.

`build.py` preserves stable item IDs, removes scale-test records with `-syn`
identifiers, and keeps collection guides separate from individual digital items.
Exact manifests can merge duplicate digital records; distinct Digital Collections
UUIDs never merge just because their archival call numbers match.
Additional source URLs are retained. Collection labels from Digital Collections
are preserved. Large page arrays are written to `records/<id>.json` and fetched
only when a reader opens an item.

The nightly workflow refreshes all three sources at 2:17 a.m. America/New_York,
validates coverage and page data, commits `items.json` and `records/`, and deploys
the validated site to GitHub Pages. It must be installed on the published repository’s
default branch with Pages configured for GitHub Actions. The revised site is currently
local; this schedule is prepared but is not yet active. Local edits do not push or deploy.
See `HARVESTING.md` for validation safeguards and activation details.

## Validation

```sh
.venv/bin/python -m unittest discover -s tests
node --check app.js
node tests/test_search.cjs
```

Search, source and collection facets, digital-image filtering, advanced-search URL
state, saved lists, map, timeline, and page viewing share the same local index.
If the search CDN is unavailable, keyword search falls back to local text matching.
External images and viewer libraries still depend on their source services.
Always consult each source record for image rights and access restrictions.

## Visual direction

The interface uses the supplied pomegranate woodcut, printed in red using a CSS
luminance mask, as part of the logo, with neutral off-white, bold serif headings, and ink rules inspired by *Milgroym*. The layout remains a collection
search interface. Presentation refinements live in `milgroym.css`; collection
images retain their original colors.

## Date and filter interpretation

`metadata.py` adds Gregorian date bounds while retaining the source wording. Explicit
calendar equivalents take precedence; unresolved calendar and open-ended dates remain
unplaced. Century ranges retain their full span. Timeline groups use neutral year
labels and place each range once by its earliest year. Advanced date searches match
overlapping ranges. These interpretations do not correct errors in the source catalog.

Collection memberships, original format terms, and languages are stored as separate
values. Sixteen format groups combine related source terms without discarding them.
Facets and advanced search match any membership of a record, counting it once per
value; collection totals can overlap. Advanced search separates source system,
repository group, and named collection, with a collection-name filter.

Map labels and placement use `places.py`: separate catalog headings, recover joined
place-name boundaries, prefer cities to countries, and respect country context.
Unresolved places stay searchable without a speculative marker. `mapLabel` and
`placeDisplay` are presentation fields; `place` retains the original catalog text.
Barcelona, Venezuela is disambiguated using the GeoNames coordinates cited in that file.

## Branches and deployment

`master` is the publishing branch and contains the revised static portal. `main`
remains available as the previous development branch. The merge preserves both
histories. Legacy Astro sources remain in the repository, but their deployment
workflow is retired; only the validated static-site package is published.

Push `master` to publish the revised site and install the nightly refresh on
the repository’s default branch. The GitHub Pages environment already permits
`master`; no change to its deployment permissions is required for this merge.
