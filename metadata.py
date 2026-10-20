"""Conservative date interpretation and independently searchable metadata values."""
import re
from places import resolve_place


def split_values(value):
    values = value if isinstance(value, list) else str(value or '').split(';')
    return list(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))


FORMAT_GROUPS = {
    'Letters & correspondence': r'letter|correspondence',
    'Books & pamphlets': r'book|pamphlet|codic|incunab',
    'Manuscripts': r'manuscript|codic|fragment|detached leav',
    'Ketubot & marriage documents': r'ketub|marriage certificate',
    'Photographs': r'photograph|stereograph|negative|lantern slide',
    'Music & scores': r'music|score',
    'Newspapers & periodicals': r'newspaper|periodical|serials',
    'Trade cards & advertising': r'trade card|advertis',
    'Financial & business records': r'billhead|financial|account|receipt|shipping|ledger|credit record',
    'Legal & government records': r'legal|deed|government|military record|contract',
    'Prints, drawings & other visual works': r'visual work|drawing|engraving|lithograph|painting|print \(|portrait|map \(',
    'Broadsides, posters & ephemera': r'broadside|poster|invitation|envelope|memorabilia|ephemera|playbill|program',
    'Literary & other texts': r'literary|writing|poem|poetry|text',
    'Objects': r'object|vessel|jug|money|coin|medal|brush|box',
    'Archival collection guides': r'finding aid|collection guide',
}


def date_range(text):
    """Return Gregorian bounds only when the source text supports them.

    A zero year means unknown/unresolved, never a guessed calendar conversion.
    Original wording is always retained by the caller.
    """
    s = str(text or '').lower()
    if not s or re.fullmatch(r'(n\.?d\.?|undated|unknown)', s.strip()):
        return 0, 0, 'unknown'
    # Digital Collections often lists an ISO Gregorian date before its Hebrew equivalent.
    iso = re.match(r'^(1[0-9]{3}|20[0-9]{2})-\d{2}-\d{2}(?:;|$)', s)
    if iso:
        year = int(iso[1])
        return year, year, 'year'
    alternate = bool(re.search(r'a\.?\s*h\.|hijra|hijri|seleucid|hebrew (?:year|calendar)|\[5\]|\b[5][0-9]{3}\b|\b[5-6][0-9]{2}-\s*\[', s))
    # Bracketed/parenthetical Gregorian equivalents override other calendars.
    equivalents = re.findall(r'[\[(]([^\])]*\b(?:1[4-9][0-9]{2}|20[0-9]{2})\b[^\])]*)[\])]', s)
    eq = re.search(r'=\s*([^.;]+)', s)
    if eq and re.search(r'\b(?:1[0-9]{3}|20[0-9]{2})\b', eq.group(1)):
        s = eq.group(1)
    elif alternate and equivalents:
        s = ' and '.join(equivalents)
    elif alternate and ';' in s and re.search(r'\b(?:1[0-9]{3}|20[0-9]{2})\b', s.split(';')[0]):
        s = s.split(';')[0]
    elif alternate:
        # Some sources give a spelled-out equivalent instead of brackets.
        match = re.search(r'\bor\s+[^.;]*?\b(1[4-9][0-9]{2}|20[0-9]{2})\b', s)
        if not match:
            return 0, 0, 'unresolved calendar'
        s = match.group(1)
    if re.search(r'\bb\.?c\.?e?\.?\b', s):
        return 0, 0, 'unresolved BCE date'
    century = re.search(r'(\d{1,2})(?:st|nd|rd|th)(?:\s*(?:[-–]|or)\s*(\d{1,2})(?:st|nd|rd|th))?\s*cent', s)
    if century:
        first = int(century[1]); last = int(century[2] or first)
        repeated = re.search(r'century\s*(?:[-–]|or)\s*(\d{1,2})(?:st|nd|rd|th)\s*cent', s)
        if repeated: last = int(repeated[1])
        if not 1 <= first <= last <= 21:
            return 0, 0, 'unknown'
        start, end = (first-1)*100, last*100-1
        if first == last:
            if 'second half' in s: start += 50
            elif 'first half' in s: end -= 50
        return max(1,start), end, 'approximate range'
    s = re.sub(r'\bf{1,2}\.\s*\d+[rv]?(?:\s*[-–]\s*\d+[rv]?)?', '', s)
    uncertain = re.search(r'\b(\d{2,3})(?:x+|-{1,2})(?![\d\w])', s)
    if uncertain:
        scale = 10 ** (4-len(uncertain[1]))
        start = int(uncertain[1])*scale
        exact = [int(v) for v in re.findall(r'\b(\d{4})\b', s)]
        return min([start]+exact), max([start+scale-1]+exact), 'approximate range'
    years = [int(v) for v in re.findall(r'\b(\d{3,4})\b', s)]
    years = [v for v in years if 1 <= v <= 2100]
    if not years:
        return 0, 0, 'unknown'
    if re.search(r'\b(before|after|not before|not after|earlier than|later than)\s+(?:ca\.?\s*)?\d{3,4}\b', s):
        return 0, 0, 'unresolved open range'
    # Expand abbreviated ranges such as 1895/6 or 1909-19.
    abbreviated = re.search(r'\b(\d{4})\s*[-–/]\s*(\d{1,2})(?![\d-])', s)
    if abbreviated:
        a, tail = int(abbreviated[1]), abbreviated[2]
        b = a // (10**len(tail)) * (10**len(tail)) + int(tail)
        if b < a: b += 10**len(tail)
        return a, b, 'range'
    # ISO dates include hyphen-prefixed month/day; those are not years.
    start, end = years[0], years[0]
    if len(years) > 1 and re.search(r'between|[-–/]\s*\d{3,4}|\bto\b|\band\b|\bor\b', s):
        start, end = min(years), max(years)
    status = 'range' if start != end else ('approximate' if re.search(r'\?|circa|\bca\.|about|perhaps', s) else 'year')
    return start, end, status


def enrich(item):
    resolved = resolve_place(item.get('place'))
    if resolved:
        item.update(mapLabel=resolved['label'], placeDisplay=resolved['label'],
                    region=resolved['country'], lat=resolved['lat'], lng=resolved['lng'])
    else:
        display = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', str(item.get('place') or 'Unknown').split(';')[0]).strip()
        item.update(mapLabel='', placeDisplay=display, lat=None, lng=None)

    memberships = split_values(item.get('collection') or item.get('collections'))
    def collection_name(value):
        if value.lower().removeprefix('the ') == 'jesselson family collection of isaac leeser material':
            return 'Jesselson Family Collection of Isaac Leeser Material'
        if value.startswith('Cairo Genizah Collection (University of Pennsylvania'):
            return 'Cairo Genizah Collection'
        if value == 'Keffer Collection of Sheet Music (University of Pennsylvania)':
            return 'Keffer Collection of Sheet Music'
        return value
    item['collections'] = list(dict.fromkeys(collection_name(v) for v in memberships))
    item['regions'] = list(dict.fromkeys(v.split(' -- ')[0].strip() for v in split_values(item.get('region'))))
    item['types'] = split_values(item.get('types') or item.get('type'))
    item['languages'] = split_values(item.get('languages') or item.get('lang'))
    groups = []
    for value in item['types']:
        matches = [label for label, pattern in FORMAT_GROUPS.items() if re.search(pattern, value, re.I)]
        groups.extend(matches or ['Other formats'])
    item['formats'] = list(dict.fromkeys(groups))
    start, end, status = date_range(item.get('dateText'))
    item.update(year=start, yearStart=start, yearEnd=end, dateStatus=status)
    return item
