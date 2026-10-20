import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import dedupe_key, stable_id, merge
from harvest_openn import parse_year
from harvest_digitalcollections import normalize, manifest_pages


class PipelineTests(unittest.TestCase):
    def test_collection_guide_not_deduplicated_with_item(self):
        item = {'system': 'OPenn', 'source': 'cajs', 'callno': 'MS 12', 'openn_repo': '0002', 'openn_obj': '12'}
        guide = {'system': 'FindingAids', 'source': 'katz', 'callno': 'MS 12', 'fa_id': 'guide'}
        self.assertFalse(set(dedupe_key(item)) & set(dedupe_key(guide)))

    def test_shelfmark_does_not_merge_different_institutions(self):
        a = {'system': 'OPenn', 'source': 'bl', 'callno': 'MS 12', 'openn_repo': '10', 'openn_obj': '12'}
        b = dict(a, source='cajs', openn_repo='2')
        self.assertFalse(set(dedupe_key(a)) & set(dedupe_key(b)))

    def test_digital_identity_is_stable(self):
        a = {'system': 'DigitalCollections', 'digital_id': 'uuid', 'title': 'A'}
        self.assertEqual(stable_id(a), stable_id(dict(a, title='B')))

    def test_converted_calendar_date(self):
        self.assertEqual(parse_year('year 164 of the Seleucid Era (= 1853)'), 1853)

    def test_iiif_v3_pages(self):
        manifest = {'items': [{'label': {'none': ['Leaf 1']}, 'items': [{'items': [{'body': {'type': 'Image', 'id': 'https://example/image', 'service': [{'id': 'https://example/iiif'}]}}]}]}]}
        page = manifest_pages(manifest)[0]
        self.assertEqual(page['label'], 'Leaf 1')
        self.assertEqual(page['img'], 'https://example/iiif/full/1600,/0/default.jpg')
        doc = {'id': 'uuid', 'attributes': {'title': 'Test', 'collection_ssim': {'attributes': {'value': ['Judaica']}}}}
        self.assertEqual(normalize(doc, manifest)['collection'], 'Judaica')

    def test_cross_source_provenance(self):
        a = {'system': 'OPenn', 'desc': '', 'iiif': True}
        b = {'system': 'DigitalCollections', 'desc': 'A description', 'srcUrl': 'https://example/item'}
        self.assertEqual(merge(a, b)['alsoIn'], ['https://example/item'])



class BuildIntegrationTests(unittest.TestCase):
    def test_scale_test_records_are_excluded(self):
        import tempfile
        from build import build
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            real = {'system': 'OPenn', 'source': 'cajs', 'openn_repo': '0002', 'openn_obj': 'real', 'title': 'Real', 'year': 1850}
            fake = dict(real, openn_repo='9000', openn_obj='real-syn1', title='Fake')
            (raw / 'sample.jsonl').write_text(json.dumps(real) + '\n' + json.dumps(fake) + '\n')
            build(str(raw), str(root / 'items.json'))
            output = json.loads((root / 'items.json').read_text())
            self.assertEqual([i['title'] for i in output['items']], ['Real'])

    def test_finding_aid_title_skips_masthead(self):
        from unittest.mock import patch
        from harvest_findingaids import parse_record
        markup = '<h1 class="sitename">Philadelphia Area Archives</h1><h1 class="index_title document-title-heading col">Judaica &amp; community papers</h1>'
        with patch('harvest_findingaids.fetch', return_value=markup):
            self.assertEqual(parse_record('TEST')['title'], 'Judaica & community papers')


class FullHarvestTests(unittest.TestCase):
    def test_digital_components_with_same_call_number_stay_separate(self):
        a = {'system': 'DigitalCollections', 'source': 'digitalcollections', 'digital_id': 'one', 'callno': 'Ms. Coll. 95', 'manifest': 'https://example/manifest/one'}
        b = dict(a, digital_id='two', manifest='https://example/manifest/two')
        self.assertFalse(set(dedupe_key(a)) & set(dedupe_key(b)))

    def test_discovery_collects_every_page_and_audits_union(self):
        import tempfile
        from unittest.mock import patch
        import harvest_digitalcollections as dc
        first = {'meta': {'pages': {'total_count': 2, 'total_pages': 2}}, 'data': [{'id': 'a'}], 'links': {'next': 'page2'}}
        second = {'meta': {'pages': {'total_count': 2}}, 'data': [{'id': 'b'}], 'links': {}}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(dc, 'discover_collections', return_value=['Judaica']), patch.object(dc, 'KEYWORDS', []), patch.object(dc, 'fetch_json', side_effect=[first, second]):
                output = dc.discover(directory)
            self.assertEqual(output['ids'], ['a', 'b'])
            self.assertEqual(output['scopes'][0]['discovered'], 2)
            self.assertEqual(output['scopes'][0]['reported'], 2)
            self.assertTrue(output['complete'])

    def test_discovery_refuses_incomplete_scope(self):
        import tempfile
        from unittest.mock import patch
        import harvest_digitalcollections as dc
        response = {'meta': {'pages': {'total_count': 2}}, 'data': [{'id': 'a'}], 'links': {}}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(dc, 'discover_collections', return_value=['Judaica']), patch.object(dc, 'KEYWORDS', []), patch.object(dc, 'fetch_json', return_value=response):
                with self.assertRaisesRegex(RuntimeError, 'Incomplete scope'):
                    dc.discover(directory)

    def test_facet_discovery_pages_past_top_collections(self):
        from unittest.mock import patch
        import harvest_digitalcollections as dc
        pages = [{'response': {'facets': {'items': [{'value':'Unrelated collection'}], 'limit': 1}}},
                 {'response': {'facets': {'items': [{'value':'Small Jewish collection'}], 'limit': 1}}},
                 {'response': {'facets': {'items': [], 'limit': 1}}}]
        with patch.object(dc, 'fetch_json', side_effect=pages):
            self.assertIn('Small Jewish collection', dc.discover_collections())

    def test_discovery_recovers_gaps_with_another_ordering(self):
        import tempfile
        from unittest.mock import patch
        import harvest_digitalcollections as dc
        first = {'meta': {'pages': {'total_count': 2}}, 'data': [{'id': 'a'}], 'links': {}}
        second = {'meta': {'pages': {'total_count': 2}}, 'data': [{'id': 'b'}], 'links': {}}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(dc, 'discover_collections', return_value=['Judaica']), patch.object(dc, 'KEYWORDS', []), patch.object(dc, 'fetch_json', side_effect=[first, second]):
                output = dc.discover(directory)
            self.assertEqual(output['ids'], ['a', 'b'])
            self.assertEqual(len(output['scopes'][0]['passes']), 2)
            self.assertEqual(output['scopes'][0]['discovered'], 2)

    def test_unavailable_manifest_keeps_metadata(self):
        import tempfile
        from unittest.mock import patch
        import harvest_digitalcollections as dc
        rid = '6b7ee6fd-21b5-4777-be49-04edc9d2a99c'
        detail = {'data': {'id': rid, 'attributes': {'title': 'Searchable item'}}}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(dc, 'fetch_json', side_effect=[None, detail, None]):
                item = dc.import_item(rid, directory)
        self.assertEqual(item['title'], 'Searchable item')
        self.assertFalse(item['iiif'])
        self.assertEqual(item['manifestStatus'], 'unavailable')

    def test_repository_metadata_preserves_images_and_collection(self):
        import harvest_digitalcollections as dc
        item = {'id': '6b7ee6fd-21b5-4777-be49-04edc9d2a99c',
                'descriptive_metadata': {'title':[{'value':'Letter'}], 'collection':[{'value':'Leeser'}], 'language':[{'value':'English'}]},
                'derivatives': {'iiif_manifest':{'url':'https://example/manifest'}},
                'assets':[{'id':'0b6671dc-37eb-4138-8533-85dc61a2ed93','label':'Leaf 1',
                           'preservation_file':{'mime_type':'image/tiff'},'derivatives':{'thumbnail':{'url':'https://example/thumb'}}}]}
        row = dc.normalize_repository(item)
        self.assertEqual(row['collection'], 'Leeser')
        self.assertEqual(row['lang'], 'English')
        self.assertEqual(row['pages'][0]['label'], 'Leaf 1')
        self.assertEqual(row['manifest'], 'https://example/manifest')
        self.assertTrue(row['iiif'])


if __name__ == '__main__':
    unittest.main()
