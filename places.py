"""Small, deterministic place resolver; source wording is never overwritten.

Barcelona, Venezuela: GeoNames (10.1384, -64.6877), verified 2026-10-19:
https://www.geonames.org/advanced-search.html?country=VE&q=Barcelona
The remaining coordinates retain the project's curated gazetteer.
"""
import re
import unicodedata

GAZETTEER = [
    ("kaifeng",        ("China", 34.80, 114.35)),
    ("china",          ("China", 34.80, 114.35)),
    ("jerusalem",      ("Land of Israel", 31.78, 35.22)),
    ("safed",          ("Land of Israel", 32.97, 35.50)),
    ("tiberias",       ("Land of Israel", 32.79, 35.53)),
    ("jaffa",          ("Land of Israel", 32.05, 34.75)),
    ("hebron",         ("Land of Israel", 31.53, 35.10)),
    ("palestine",      ("Land of Israel", 31.50, 35.00)),
    ("israel",         ("Land of Israel", 31.50, 35.00)),
    ("cairo",          ("Egypt", 30.04, 31.24)),
    ("fustat",         ("Egypt", 30.01, 31.23)),
    ("alexandria",     ("Egypt", 31.20, 29.92)),
    ("egypt",          ("Egypt", 30.04, 31.24)),
    ("yemen",          ("Yemen", 15.55, 48.52)),
    ("san'a",          ("Yemen", 15.37, 44.19)),
    ("baghdad",        ("Iraq", 33.32, 44.36)),
    ("iraq",           ("Iraq", 33.22, 43.68)),
    ("isfahan",        ("Iran", 32.65, 51.67)),
    ("persia",         ("Iran", 32.43, 53.69)),
    ("iran",           ("Iran", 32.43, 53.69)),
    ("istanbul",       ("Turkey", 41.01, 28.98)),
    ("constantinople", ("Turkey", 41.01, 28.98)),
    ("salonika",       ("Greece", 40.64, 22.94)),
    ("ottoman",        ("Turkey", 39.00, 35.24)),
    ("turkey",         ("Turkey", 39.00, 35.24)),
    ("morocco",        ("Morocco", 31.79, -7.09)),
    ("tunis",          ("Tunisia", 36.81, 10.18)),
    ("cochin",         ("India", 9.93, 76.27)),
    ("calcutta",       ("India", 22.57, 88.36)),
    ("bombay",         ("India", 19.08, 72.88)),
    ("india",          ("India", 22.00, 79.00)),
    ("amsterdam",      ("Netherlands", 52.37, 4.90)),
    ("netherlands",    ("Netherlands", 52.13, 5.29)),
    ("holland",        ("Netherlands", 52.13, 5.29)),
    ("venice",         ("Italy", 45.44, 12.32)),
    ("rome",           ("Italy", 41.90, 12.50)),
    ("livorno",        ("Italy", 43.55, 10.31)),
    ("italy",          ("Italy", 41.90, 12.50)),
    ("solsona",        ("Spain", 41.99, 1.52)),
    ("barcelona",      ("Spain", 41.39, 2.17)),
    ("toledo",         ("Spain", 39.86, -4.02)),
    ("spain",          ("Spain", 40.00, -3.70)),
    ("portugal",       ("Portugal", 39.40, -8.22)),
    ("london",         ("England", 51.51, -0.13)),
    ("england",        ("England", 52.30, -1.20)),
    ("united kingdom", ("England", 52.30, -1.20)),
    ("paris",          ("France", 48.86, 2.35)),
    ("france",         ("France", 46.60, 2.30)),
    ("prague",         ("Czech lands", 50.08, 14.44)),
    ("vienna",         ("Austria", 48.21, 16.37)),
    ("germany",        ("Germany", 51.10, 10.40)),
    ("poland",         ("Poland", 52.00, 19.00)),
    ("philadelphia",   ("United States", 39.95, -75.16)),
    ("new york",       ("United States", 40.71, -74.01)),
    ("united states",  ("United States", 39.83, -98.58)),
    ("america",        ("United States", 39.83, -98.58)),
]

CITY_NAMES = {
    'kaifeng':'Kaifeng', 'jerusalem':'Jerusalem', 'safed':'Safed',
    'tiberias':'Tiberias', 'jaffa':'Jaffa', 'hebron':'Hebron',
    'cairo':'Cairo', 'fustat':'Fustat', 'alexandria':'Alexandria',
    "san'a":"Sana’a", 'baghdad':'Baghdad', 'isfahan':'Isfahan',
    'istanbul':'Istanbul', 'constantinople':'Istanbul', 'salonika':'Thessaloniki',
    'tunis':'Tunis', 'cochin':'Kochi', 'calcutta':'Kolkata', 'bombay':'Mumbai',
    'amsterdam':'Amsterdam', 'venice':'Venice', 'rome':'Rome', 'livorno':'Livorno',
    'solsona':'Solsona', 'barcelona':'Barcelona', 'toledo':'Toledo',
    'london':'London', 'paris':'Paris', 'prague':'Prague', 'vienna':'Vienna',
    'philadelphia':'Philadelphia', 'new york':'New York',
}


def normalized(text):
    # Recover boundaries lost when source HTML joined adjacent place elements.
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text or '')
    text = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', text.replace('’', "'")).lower()


def resolve_place(place):
    """Use the first resolvable heading, preferring a city over its country.

    Multiple catalog headings are not concatenated into a map label. Explicit
    country context disambiguates city names. Unknown places remain unplotted.
    """
    for part in str(place or '').split(';'):
        text = normalized(part)
        matches = []
        for needle, (country, lat, lng) in GAZETTEER:
            match = re.search(r'(?<![a-z])' + re.escape(needle) + r'(?![a-z])', text)
            if match:
                matches.append((needle, country, lat, lng, match.start()))
        countries = {country for needle,country,_,_,_ in matches if needle not in CITY_NAMES}
        if 'venezuela' in text:
            countries.add('Venezuela')
            if re.search(r'\bbarcelona\b', text):
                return dict(label='Barcelona, Venezuela', country='Venezuela', lat=10.1384, lng=-64.6877)
        cities = [m for m in matches if m[0] in CITY_NAMES and (not countries or m[1] in countries)]
        if cities:
            needle,country,lat,lng,_ = min(cities, key=lambda m:m[4])
            return dict(label=CITY_NAMES[needle], country=country, lat=lat, lng=lng)
        broad = [m for m in matches if m[0] not in CITY_NAMES]
        if broad:
            needle,country,lat,lng,_ = min(broad, key=lambda m:m[4])
            if needle == 'america' and re.search(r'\b(south|central|latin) america\b', text):
                continue
            return dict(label=country, country=country, lat=lat, lng=lng)
    return None
