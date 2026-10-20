import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.nightly_site import package, validate


class NightlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = {'items': [
            {'id': 1, 'system': 'OPenn', 'iiif': True},
            {'id': 2, 'system': 'DigitalCollections', 'digital_id': 'uuid'},
            {'id': 3, 'system': 'FindingAids'}],
            'coverage': {'DigitalCollections': {'complete': True, 'imported': 1, 'discovered': 1,
                'scopes': [{'reported': 1, 'discovered': 1}]}}}
        self.baseline = copy.deepcopy(self.payload)
        (self.root / 'records').mkdir()
        (self.root / 'records/1.json').write_text('{"id":1,"pages":[]}')
        self.write()

    def write(self):
        (self.root / 'items.json').write_text(json.dumps(self.payload))

    def test_complete_harvest_passes(self):
        self.assertEqual(validate(self.root, self.baseline)['DigitalCollections'], 1)

    def test_missing_source_blocks_publication(self):
        self.payload['items'] = self.payload['items'][:-1]
        self.write()
        with self.assertRaisesRegex(ValueError, 'no records'):
            validate(self.root, self.baseline)

    def test_incomplete_digital_scope_blocks_publication(self):
        self.payload['coverage']['DigitalCollections']['complete'] = False
        self.write()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            validate(self.root, self.baseline)

    def test_large_record_loss_blocks_publication(self):
        self.baseline['items'] += [{'id': i, 'system': 'OPenn'} for i in range(4, 10)]
        with self.assertRaisesRegex(ValueError, 'fell from'):
            validate(self.root, self.baseline)

    def test_missing_page_shard_blocks_publication(self):
        self.payload['items'][0]['id'] = 999
        self.write()
        with self.assertRaisesRegex(ValueError, 'Missing page data'):
            validate(self.root, self.baseline)

    def test_package_excludes_private_and_intermediate_files(self):
        for name in ('index.html', 'styles.css', 'app.js'):
            (self.root / name).write_text('public')
        (self.root / '.env').write_text('private')
        (self.root / 'raw').mkdir()
        (self.root / 'raw/private.json').write_text('{}')
        destination = self.root / '_site'
        package(self.root, destination)
        self.assertTrue((destination / 'items.json').exists())
        self.assertFalse((destination / '.env').exists())
        self.assertFalse((destination / 'raw').exists())


if __name__ == '__main__':
    unittest.main()
