#!/usr/bin/env python3
"""Validate a fresh harvest and package only the public static site."""
import argparse
import json
import math
import shutil
from collections import Counter
from pathlib import Path

SYSTEMS = ('OPenn', 'DigitalCollections', 'FindingAids')


def validate(root, baseline):
    root = Path(root)
    payload = json.loads((root / 'items.json').read_text())
    items = payload['items']
    ids = [item['id'] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate item IDs; refusing to publish')
    if any(type(rid) is not int or rid < 0 for rid in ids):
        raise ValueError('Invalid item IDs; refusing to publish')
    counts = Counter(item['system'] for item in items)
    previous = Counter(item['system'] for item in baseline['items'])
    for system in SYSTEMS:
        if not counts[system]:
            raise ValueError(f'{system}: no records; refusing to publish')
        minimum = math.ceil(previous[system] * 0.8)
        if counts[system] < minimum:
            raise ValueError(f'{system}: fell from {previous[system]} to {counts[system]} records; review before publishing')
    audit = payload.get('coverage', {}).get('DigitalCollections', {})
    digital_ids = [item.get('digital_id') for item in items if item['system'] == 'DigitalCollections']
    if not (audit.get('complete') and audit.get('discovered') == audit.get('imported') == counts['DigitalCollections']):
        raise ValueError('Digital Collections import is incomplete or disagrees with the index')
    if not digital_ids or None in digital_ids or len(set(digital_ids)) != len(digital_ids):
        raise ValueError('Digital Collections has missing or duplicate source IDs')
    if not audit.get('scopes') or any(scope['reported'] != scope['discovered'] for scope in audit['scopes']):
        raise ValueError('Digital Collections scope counts do not match the source')
    for item in items:
        if item.get('iiif'):
            shard = root / 'records' / f"{item['id']}.json"
            if not shard.is_file():
                raise ValueError(f'Missing page data for {item["id"]}')
    return counts


def package(root, destination):
    root, destination = Path(root), Path(destination)
    if destination.exists():
        raise ValueError('Package destination must be a new directory')
    destination.mkdir(parents=True)
    for name in ('index.html', 'styles.css', 'app.js', 'items.json'):
        shutil.copy2(root / name, destination / name)
    for name in ('milgroym.css', 'data.js'):
        if (root / name).is_file():
            shutil.copy2(root / name, destination / name)
    for name in ('records', 'assets'):
        if (root / name).is_dir():
            shutil.copytree(root / name, destination / name)
    (destination / '.nojekyll').touch()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--out', default='_site')
    args = parser.parse_args()
    baseline = json.loads(Path(args.baseline).read_text())
    counts = validate(args.root, baseline)
    package(args.root, args.out)
    print('Validated and packaged:', dict(counts))


if __name__ == '__main__':
    main()
