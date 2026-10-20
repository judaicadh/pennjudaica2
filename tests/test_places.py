import unittest
from places import resolve_place
from metadata import enrich
from harvest_openn import geocode


class PlaceTests(unittest.TestCase):
    def test_barcelona_labels_and_country_context(self):
        spanish = resolve_place('Spain -- Barcelona; Spain; United States -- Pennsylvania -- Philadelphia')
        venezuelan = resolve_place('Venezuela -- Barcelona; Venezuela; United States -- Pennsylvania -- Philadelphia')
        self.assertEqual(spanish['label'], 'Barcelona')
        self.assertEqual(venezuelan['label'], 'Barcelona, Venezuela')
        self.assertGreater(spanish['lng'], 0)
        self.assertLess(venezuelan['lng'], -60)

    def test_joined_source_values_cleaned(self):
        for value in ['Spain, N.E.Barcelona', 'SpainCataloniaBarcelonaFranceProvenceBas-Languedoc', 'SpainCataloniaBarcelonaItaly']:
            self.assertEqual(resolve_place(value)['label'], 'Barcelona')

    def test_city_precedes_country_and_heading_order_preserved(self):
        self.assertEqual(resolve_place('Italy -- Venice')['label'], 'Venice')
        self.assertEqual(resolve_place('United States -- Pennsylvania -- Philadelphia; Spain -- Barcelona')['label'], 'Philadelphia')

    def test_conflicting_country_does_not_get_foreign_city(self):
        self.assertEqual(resolve_place('United States -- Virginia -- Alexandria')['country'], 'United States')
        self.assertNotEqual(geocode('Venezuela -- Barcelona')[0], 'Spain')

    def test_unknown_place_is_not_guessed(self):
        self.assertIsNone(resolve_place('Unknown'))
        self.assertIsNone(resolve_place('South America'))

    def test_original_wording_preserved(self):
        original='Spain -- Barcelona; Spain; United States -- Pennsylvania -- Philadelphia'
        row=enrich({'place':original})
        self.assertEqual(row['place'],original)
        self.assertEqual(row['placeDisplay'],'Barcelona')
