#!/usr/bin/env python3
"""Harvest Judaica metadata and IIIF pages from Penn's current repository.

Default discovery unions Judaica keywords with explicit Jewish collections.
--limit creates a development sample; omit it for a complete scoped harvest.
The previous output is preserved if any request fails.
"""
import argparse
import concurrent.futures
import datetime
import threading
import uuid
import json
import os
import re
import tempfile
import time
from urllib.parse import urlencode

import requests
from harvest_openn import geocode, parse_year

BASE = 'https://digitalcollections.library.upenn.edu'
REPOSITORY = 'https://digitalrepository.library.upenn.edu'
KEYWORDS = [
    'judaica', 'hebrew', 'yiddish', 'ladino', 'judeo-arabic',
    'jewish', 'jews', 'judaism', 'genizah', 'ketubah', 'ketubot',
    'sephardic', 'ashkenazi', 'zionism', 'holocaust', 'talmud', 'kabbalah',
]
COLLECTIONS = [
    'Arnold and Deanne Kaplan Collection of Early American Judaica (University of Pennsylvania)',
    'Arnold and Deanne Kaplan Collection of Modern American Judaica (University of Pennsylvania)',
    'Arnold and Deanne Kaplan Isaac Leeser Collection',
    'Isaac Leeser Collection at the Herbert D. Katz Center for Advanced Judaic Studies (University of Pennsylvania)',
    'Isaac Leeser Digital Repository',
    'Sabato Morais Collection (University of Pennsylvania)',
    'Cairo Genizah Collection (University of Pennsylvania. Center for Advanced Judaic Studies. Library)',
    'Gratz-Mandell Jewish Music Collection (University of Pennsylvania)',
]
COLLECTION_PATTERN = re.compile(r'juda|jewish|hebrew|yiddish|ladino|leeser|morais|genizah|ketub|katz', re.I)
LOCAL = threading.local()


def fetch_json(url, missing_ok=False):
    if not hasattr(LOCAL, 'session'):
        LOCAL.session = requests.Session()
        LOCAL.session.headers['User-Agent'] = 'PennJudaicaPortal/0.3 (research discovery index)'
    for attempt in range(5):
        try:
            r = LOCAL.session.get(url, timeout=(10, 60))
            if missing_ok and r.status_code in (403, 404):
                return None
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if attempt == 4:
                raise
            time.sleep(min(30, 2 ** attempt))


def atomic_json(path, data):
    path = __import__('pathlib').Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, path)


def discover_collections():
    collections = set(COLLECTIONS)
    page, seen_values = 1, set()
    while True:
        data = fetch_json(BASE + '/items/facet/collection_ssim.json?' + urlencode({'facet.page': page}))
        facet = data['response']['facets']
        entries = facet['items']
        if not entries:
            break
        new = {entry['value'] for entry in entries} - seen_values
        if not new:
            raise RuntimeError('Collection facet pagination repeated a page')
        seen_values.update(new)
        collections.update(value for value in new if COLLECTION_PATTERN.search(value))
        if len(entries) < facet['limit']:
            break
        page += 1
    return sorted(collections)


def discover(cache_dir, reuse=False):
    from pathlib import Path
    checkpoint = Path(cache_dir) / 'discovery.json'
    if reuse and checkpoint.exists():
        data = json.loads(checkpoint.read_text())
        if data.get('complete') and data.get('keywords') == KEYWORDS:
            print('Resuming verified discovery:', len(data['ids']), 'unique IDs', flush=True)
            return data
    collections = discover_collections()
    print(f'Discovered {len(collections)} named Judaica collection scopes', flush=True)
    scopes = [('collection', collection, {'f[collection_ssim][]': collection}) for collection in collections]
    scopes += [('keyword', keyword, {'q': keyword}) for keyword in KEYWORDS]
    all_ids, reports = set(), []
    import hashlib
    for kind, label, params in scopes:
        scope_key = hashlib.sha256((kind + ':' + label + ':title-sort-v1').encode()).hexdigest()
        scope_path = Path(cache_dir) / 'scopes' / (scope_key + '.json')
        if reuse and scope_path.exists():
            cached = json.loads(scope_path.read_text())
            all_ids.update(cached['ids'])
            reports.append(cached['report'])
            print(f'Resumed scope: {label} — {len(cached["ids"]):,}', flush=True)
            continue
        scope_ids, passes, expected, total_pages = set(), [], None, 0
        # Penn's index has tied sort values that can repeat across page boundaries.
        # Independent advertised orderings recover those gaps; accept only a union
        # equal to the source total, never the number of rows downloaded.
        for ordering in ['last_published_at_dtsi desc', 'title_sort asc,', 'relevance', 'first_published_at_dtsi desc']:
            pass_key = hashlib.sha256((scope_key + ordering).encode()).hexdigest()
            pass_path = Path(cache_dir) / 'passes' / (pass_key + '.json')
            if reuse and pass_path.exists():
                cached_pass = json.loads(pass_path.read_text())
                pass_ids, pass_expected, page_count = set(cached_pass['ids']), cached_pass['reported'], cached_pass['pages']
            else:
                def load_page(page):
                    url = BASE + '/items.json?' + urlencode(dict(params, page=page, per_page=100, sort=ordering))
                    return fetch_json(url)
                first = load_page(1)
                pass_expected = int(first['meta']['pages']['total_count'])
                page_count = int(first['meta']['pages'].get('total_pages') or max(1, (pass_expected + 99) // 100))
                pass_ids = {str(entry['id']) for entry in first['data']}
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    for page, payload in enumerate(executor.map(load_page, range(2, page_count + 1)), start=2):
                        total = int(payload['meta']['pages']['total_count'])
                        if total != pass_expected:
                            raise RuntimeError(f'Source changed during pagination for {label}: {pass_expected} → {total}. Retry discovery.')
                        pass_ids.update(str(entry['id']) for entry in payload['data'])
                        if page % 25 == 0:
                            print(f'  {label[:45]}: page {page}/{page_count}, {len(pass_ids):,} unique IDs', flush=True)
                atomic_json(pass_path, {'ids': sorted(pass_ids), 'reported': pass_expected, 'pages': page_count})
            if expected is not None and pass_expected != expected:
                raise RuntimeError(f'Source changed across sort passes for {label}')
            expected = pass_expected
            total_pages += page_count
            scope_ids.update(pass_ids)
            passes.append({'sort': ordering, 'uniqueIds': len(pass_ids), 'pages': page_count})
            if len(scope_ids) == expected:
                break
            if len(scope_ids) > expected:
                raise RuntimeError(f'Source membership changed during discovery of {label}')
            print(f'  Recovering pagination gaps for {label[:45]}: {len(scope_ids):,}/{expected:,}; trying another supported ordering', flush=True)
        if len(scope_ids) != expected:
            raise RuntimeError(f'Incomplete scope {label}: {len(scope_ids)} unique IDs / {expected} reported')
        all_ids.update(scope_ids)
        report = {'kind': kind, 'query': label, 'reported': expected, 'discovered': len(scope_ids), 'pages': total_pages, 'passes': passes}
        reports.append(report)
        atomic_json(scope_path, {'ids': sorted(scope_ids), 'report': report})
        print(f'{kind}: {label} — {len(scope_ids):,} / {expected:,}; union {len(all_ids):,}', flush=True)
    result = {'complete': True, 'discoveredAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'keywords': KEYWORDS, 'collections': collections, 'scopes': reports, 'ids': sorted(all_ids)}
    atomic_json(checkpoint, result)
    return result


def values(attrs, key):
    value = attrs.get(key, '')
    if isinstance(value, dict):
        value = value.get('attributes', {}).get('value', [])
    return value if isinstance(value, list) else ([value] if value else [])


def language_text(value):
    if isinstance(value, dict):
        return ' '.join(str(v) for vs in value.values() for v in vs)
    return str(value or '')


def manifest_pages(manifest):
    pages = []
    for canvas in manifest.get('items', []):
        for group in canvas.get('items', []):
            for annotation in group.get('items', []):
                body = annotation.get('body', {})
                if not isinstance(body, dict) or body.get('type') != 'Image':
                    continue
                services = body.get('service', [])
                if isinstance(services, dict):
                    services = [services]
                service = next((s.get('id') or s.get('@id') for s in services
                                if s.get('id') or s.get('@id')), None)
                image = service + '/full/1600,/0/default.jpg' if service else body.get('id')
                thumb = service + '/full/!300,300/0/default.jpg' if service else image
                if image:
                    pages.append({'img': image, 'thumb': thumb,
                                  'label': language_text(canvas.get('label'))})
    return pages


def normalize(document, manifest):
    rid = document['id']
    attrs = document['attributes']
    get = lambda key: '; '.join(str(v) for v in values(attrs, key))
    date = get('date_ssim')
    place = get('geographic_subject_ssim') or get('place_of_publication_ssim')
    region, lat, lng = geocode(place)
    pages = manifest_pages(manifest)
    location = get('physical_location_tesim')
    # Penn physical-location values end with the shelfmark when present.
    callno = location.rsplit(', ', 1)[-1] if ', ' in location else ''
    if not re.search(r'\d', callno):
        callno = ''
    return {
        'system': 'DigitalCollections', 'source': 'digitalcollections',
        'digital_id': rid, 'title': get('title') or 'Untitled',
        'creator': get('name_with_role_tesim') or 'Unknown',
        'collection': get('collection_ssim') or 'Penn Digital Collections',
        'collections': values(attrs, 'collection_ssim'),
        'types': values(attrs, 'physical_format_ssim'),
        'languages': values(attrs, 'language_ssim'),
        'year': parse_year(date), 'dateText': date or 'n.d.',
        'place': place or 'Unknown', 'region': region, 'lat': lat, 'lng': lng,
        'lang': get('language_ssim') or 'Unknown',
        'type': get('physical_format_ssim') or 'Digital item',
        'iiif': bool(pages), 'img': pages[0]['thumb'] if pages else '',
        'manifest': f'{REPOSITORY}/iiif/items/{rid}/manifest',
        'srcUrl': f'{BASE}/items/{rid}', 'callno': callno,
        'desc': get('description_tesim') or get('note_tesim'),
        'subjects': values(attrs, 'subject_ssim'),
        'extent': get('extent_tesim'), 'rights': get('rights_uri_ssim'),
        'pages': pages,
    }


def normalize_repository(item):
    """Use the repository's public combined metadata/assets representation."""
    metadata = item['descriptive_metadata']
    names = {'title': 'title', 'name': 'name_with_role_tesim',
             'date': 'date_ssim', 'collection': 'collection_ssim',
             'physical_format': 'physical_format_ssim', 'language': 'language_ssim',
             'description': 'description_tesim', 'note': 'note_tesim',
             'geographic_subject': 'geographic_subject_ssim',
             'physical_location': 'physical_location_tesim', 'extent': 'extent_tesim',
             'subject': 'subject_ssim'}
    attrs = {target: {'attributes': {'value': [entry['value'] for entry in metadata.get(source, []) if entry.get('value')]}}
             for source, target in names.items()}
    attrs['rights_uri_ssim'] = {'attributes': {'value': [entry.get('uri') or entry.get('value') for entry in metadata.get('rights', []) if entry.get('uri') or entry.get('value')]}}
    row = normalize({'id': item['id'], 'attributes': attrs}, {})
    manifest = item.get('derivatives', {}).get('iiif_manifest') or {}
    pages = []
    for asset in item.get('assets', []):
        preservation = asset.get('preservation_file') or {}
        if not preservation.get('mime_type', '').startswith('image/'):
            continue
        derivatives = asset.get('derivatives') or {}
        access, thumbnail = derivatives.get('access') or {}, derivatives.get('thumbnail') or {}
        service = 'https://iiif-images.library.upenn.edu/iiif/3/' + str(uuid.UUID(asset['id']))
        image = access.get('url') if access.get('mime_type', '').startswith('image/') else None
        if not image and manifest.get('url'):
            image = service + '/full/!1600,1600/0/default.jpg'
        if not image:
            continue
        pages.append({'img': image, 'thumb': thumbnail.get('url') or image,
                      'label': asset.get('label') or 'Page ' + str(len(pages) + 1)})
    row.update({'pages': pages, 'iiif': bool(pages),
                'img': pages[0]['thumb'] if pages else '',
                'manifest': manifest.get('url', ''),
                'manifestStatus': 'available' if manifest.get('url') else 'unavailable'})
    return row


def import_item(rid, cache_dir):
    from pathlib import Path
    uuid.UUID(rid)  # Cache filenames must be item UUIDs, never arbitrary paths.
    cache = Path(cache_dir) / 'items' / (rid + '.json')
    if cache.exists():
        row = json.loads(cache.read_text())
        if row.get('digital_id') == rid and row.get('_schema') == 2:
            return row
    repository = fetch_json(f'{REPOSITORY}/v1/items/{rid}?assets=true', missing_ok=True)
    if repository and repository.get('data', {}).get('item', {}).get('descriptive_metadata') is not None:
        item = normalize_repository(repository['data']['item'])
    else:
        detail = fetch_json(f'{BASE}/items/{rid}.json')['data']
        manifest = fetch_json(f'{REPOSITORY}/iiif/items/{rid}/manifest', missing_ok=True)
        item = normalize(detail, manifest or {})
        item['manifestStatus'] = 'available' if manifest else 'unavailable'
        if not manifest:
            item['manifest'] = ''
    item['_schema'] = 2
    atomic_json(cache, item)
    return item


def harvest(limit=None, cache_dir='raw/.digitalcollections-cache', workers=4, resume=False):
    discovery = discover(cache_dir, reuse=resume)
    ids = discovery['ids'][:limit] if limit else discovery['ids']
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for item in executor.map(lambda rid: import_item(rid, cache_dir), ids):
            yield item


def main():
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='raw/digitalcollections.jsonl')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--cache', default='raw/.digitalcollections-cache')
    ap.add_argument('--resume', action='store_true', help='reuse a verified discovery checkpoint; item cache is always reused')
    ap.add_argument('--discover-only', action='store_true')
    args = ap.parse_args()
    if args.limit is not None and args.limit < 1:
        ap.error('--limit must be positive')
    if not 1 <= args.workers <= 4:
        ap.error('--workers must be between 1 and 4')
    if args.discover_only:
        discovery = discover(args.cache, reuse=args.resume)
        print('Discovery complete:', len(discovery['ids']), 'unique IDs')
        return
    directory = os.path.dirname(args.out) or '.'
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=directory, suffix='.tmp')
    count, unavailable, seen = 0, 0, set()
    started = time.monotonic()
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            for item in harvest(args.limit, args.cache, args.workers, args.resume):
                if item['digital_id'] in seen:
                    raise RuntimeError('Duplicate item ID in import')
                seen.add(item['digital_id'])
                unavailable += item.get('manifestStatus') == 'unavailable'
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                count += 1
                if count % 250 == 0:
                    print(f'Imported {count:,} digital items ({time.monotonic() - started:.0f}s)', flush=True)
        if not count:
            raise RuntimeError('No records returned; previous harvest preserved')
        discovery = json.loads((Path(args.cache) / 'discovery.json').read_text())
        if not args.limit and seen != set(discovery['ids']):
            raise RuntimeError('Imported IDs do not match the discovered union')
        os.replace(temporary, args.out)
        audit = {key: val for key, val in discovery.items() if key != 'ids'}
        audit.update({'complete': not bool(args.limit), 'harvestedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'discovered': len(discovery['ids']), 'imported': count, 'unavailableManifests': unavailable})
        atomic_json(str(Path(args.out).with_suffix('.audit.json')), audit)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f'Wrote {count:,} Digital Collections items to {args.out}; {unavailable} without available manifests')


if __name__ == '__main__':
    main()
