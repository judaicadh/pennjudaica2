import unittest
from metadata import date_range, enrich


class MetadataTests(unittest.TestCase):
    def test_hebrew_equivalent(self):
        self.assertEqual(date_range('[5]604 Shevat 15 [1844 February 5]')[:2], (1844, 1844))
        self.assertEqual(date_range('567- [1909-1919]')[:2], (1909, 1919))
        self.assertEqual(date_range('of 677 [= Saturday 26-05-1917].')[:2], (1917, 1917))

    def test_hijri_equivalents_and_unresolved(self):
        self.assertEqual(date_range('between A.H. 1268 (1851) and 1276 (1859)')[:2], (1851,1859))
        self.assertEqual(date_range('1335 to the Hijra [1917/8]')[:2], (1917,1918))
        self.assertEqual(date_range('Dated 1266 A.H.')[:2], (0,0))
        self.assertEqual(date_range('5423, or Monday April 2, 1663')[:2], (1663,1663))

    def test_centuries_retain_uncertainty(self):
        self.assertEqual(date_range('11th-12th century')[:2], (1000,1199))
        self.assertEqual(date_range('10th century-12th century?')[:2], (900,1199))
        self.assertEqual(date_range('second half of the 16th century, after 1542')[:2], (1550,1599))

    def test_plain_dates_and_ranges(self):
        self.assertEqual(date_range('1800-11-19')[:2], (1800,1800))
        self.assertEqual(date_range('Between 0900 and 1399')[:2], (900,1399))
        self.assertEqual(date_range('1909-19')[:2], (1909,1919))
        self.assertEqual(date_range('0300')[:2], (300,300))
        self.assertEqual(date_range('1843; 21 Tammuz 5603')[:2], (1843,1843))
        self.assertEqual(date_range('before 1800')[:2], (0,0))
        self.assertEqual(date_range('1822-06-16; 5582')[:2], (1822,1822))
        self.assertEqual(date_range('Hebrew translation, second half of the 16th century, after 1542')[:2], (1550,1599))
        self.assertEqual(date_range('n.d.')[:2], (0,0))

    def test_uncertain_decades_and_folio_numbers(self):
        self.assertEqual(date_range('5605 or 565- Adar 5 [1845 February 12 or 189-]')[:2], (1845,1899))
        self.assertEqual(date_range('186X~')[:2], (1860,1869))
        self.assertEqual(date_range('1912/191X')[:2], (1910,1919))
        self.assertEqual(date_range('colophon dated 1446 (f. 250v); pages (f. 251r-269r)')[:2], (1446,1446))

    def test_memberships_not_combinations(self):
        row=enrich({'collection':'Kaplan; Leeser; Kaplan','type':'letters (correspondence); manuscripts (documents)','lang':'Hebrew; English','dateText':'1844'})
        self.assertEqual(row['collections'], ['Kaplan','Leeser'])
        self.assertEqual(row['formats'], ['Letters & correspondence','Manuscripts'])
        self.assertEqual(row['languages'], ['Hebrew','English'])

    def test_synonyms_condense(self):
        for term in ['letters (correspondence)','correspondence','Letter']:
            self.assertEqual(enrich({'type':term})['formats'], ['Letters & correspondence'])
