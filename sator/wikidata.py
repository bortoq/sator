#!/usr/bin/env python3
"""Wikidata original language lookup."""

import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
from sator import settings

# ═══════════════════════════════════════════════════════════════════════════════
# WIKIDATA ORIGINAL LANGUAGE LOOKUP
# ═══════════════════════════════════════════════════════════════════════════════

# Wikidata Q-code → ISO 639-1 mapping
WIKIDATA_ISO = {
    # Q12107 = Breton
    'Q1860': 'en', 'Q188': 'de', 'Q12107': 'br', 'Q150': 'fr', 'Q652': 'it',
    'Q1321': 'es', 'Q5146': 'pt', 'Q7411': 'nl', 'Q809': 'pl', 'Q9027': 'sv',
    'Q9035': 'da', 'Q1412': 'fi', 'Q9056': 'cs', 'Q9067': 'hu', 'Q7913': 'ro',
    'Q8798': 'uk', 'Q9129': 'el', 'Q256': 'tr', 'Q9217': 'th', 'Q9199': 'vi',
    'Q1568': 'hi', 'Q9610': 'bn', 'Q9288': 'he', 'Q13955': 'ar', 'Q5287': 'ja',
    'Q9176': 'ko', 'Q7855': 'zh', 'Q9043': 'no', 'Q9240': 'id', 'Q9237': 'ms',
    'Q9299': 'sr', 'Q6654': 'hr', 'Q9058': 'sk', 'Q7918': 'bg', 'Q9063': 'sl',
    'Q9083': 'lt', 'Q9052': 'lv', 'Q9072': 'et', 'Q294': 'is', 'Q9142': 'ga',
    'Q9309': 'cy', 'Q9166': 'mt', 'Q8748': 'sq', 'Q9296': 'mk', 'Q9303': 'bs',
    'Q7026': 'ca', 'Q10134': 'gl', 'Q8752': 'eu', 'Q397': 'la', 'Q7737': 'ru',
    'Q9264': 'tt', 'Q9255': 'ky', 'Q9252': 'kk', 'Q9267': 'tk', 'Q9260': 'tg',
    'Q9246': 'mn', 'Q9247': 'ug', 'Q13267': 'si', 'Q5885': 'ta', 'Q8097': 'te',
    'Q36236': 'ml', 'Q33673': 'kn', 'Q1571': 'mr', 'Q34057': 'tl', 'Q1617': 'ur',
    'Q58635': 'pa', 'Q58680': 'ps', 'Q9168': 'fa', 'Q13218': 'xh', 'Q10179': 'zu',
    'Q7838': 'sw', 'Q13275': 'so', 'Q9211': 'lo', 'Q9228': 'my', 'Q9205': 'km',
    'Q7738': 'qu', 'Q13199': 'rm', 'Q36163': 'ku', 'Q14185': 'oc',
    'Q34219': 'wa', 'Q35939': 'ia', 'Q35852': 'ie', 'Q352': 'io', 'Q143': 'eo',
    'Q8641': 'yi', 'Q8108': 'ka', 'Q8785': 'hy', 'Q9091': 'be',
    'Q33350': 'ce', 'Q13307': 'na', 'Q33823': 'ne',
}

# Noise words to strip before Wikidata lookup
_NOISE_WORDS = (
    'complete', 'series', 'season', r's\d+', 'episode', r'e\d+',
    '1080p', '720p', '2160p', '480p', '4k', 'uhd',
    'bluray', 'blu-ray', 'bdrip', 'bd-rip', 'brrip',
    'webdl', 'web-dl', 'webrip', 'web-rip', 'hdtv', 'hdtvrip',
    'x264', 'x265', 'hevc', 'h264', 'h265', 'avc',
    'aac', 'ac3', 'dts', 'flac', 'mp3',
    'multi', 'dual', 'proper', 'repack', 'internal', 'readnfo',
    'flux', 'ntb', 'sparks', 'yify', 'rarbg', 'tigole', 'paw',
)

def _clean_query(raw: str) -> str:
    '''Remove torrent noise words from query for better search results.'''
    # Shell escapes inside double quotes are passed literally to the program.
    raw = re.sub(r'\\([ ()])', r'\1', raw)
    s = raw.lower()
    # Remove noise words
    for pat in _NOISE_WORDS:
        s = re.sub(r'\b' + pat + r'\b', '', s)
    # Remove extra spaces
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.strip(' -_').strip()
    return s or raw

def _wikidata_api(params: dict, deadline: float) -> dict:
    """One bounded Wikidata API request; callers share the same deadline."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Wikidata lookup budget exhausted')
    url = 'https://www.wikidata.org/w/api.php?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': settings.UA_SATOR})
    with urllib.request.urlopen(req, timeout=min(settings.WIKIDATA_LOOKUP_REQUEST_TIMEOUT,
                                                 remaining)) as resp:
        data = json.loads(resp.read().decode())
    if 'error' in data:
        raise ValueError(data['error'].get('info', 'Wikidata API error'))
    return data


def _entity_language(entity: dict, title: str, year: str) -> str:
    """Accept a matching work and return its original-language code."""
    labels = entity.get('labels', {})
    label = labels.get('en', {}).get('value', '')
    normalized = lambda value: re.sub(r'\W+', ' ', value.casefold()).strip()
    if normalized(label) != normalized(title):
        return ''
    description = entity.get('descriptions', {}).get('en', {}).get('value', '').lower()
    if not any(word in description for word in ('film', 'movie', 'series', 'anime', 'animation')):
        return ''
    claims = entity.get('claims', {})
    if year:
        dates = []
        for prop in ('P577', 'P571', 'P580'):
            for claim in claims.get(prop, []):
                value = claim.get('mainsnak', {}).get('datavalue', {}).get('value', {})
                if isinstance(value, dict):
                    dates.append(value.get('time', '')[1:5])
        if year not in dates and year not in description:
            return ''
    for prop in ('P364', 'P407', 'P2439'):
        for claim in claims.get(prop, []):
            lang_q = claim.get('mainsnak', {}).get('datavalue', {}).get('value', {})
            if isinstance(lang_q, dict) and lang_q.get('id') in WIKIDATA_ISO:
                return WIKIDATA_ISO[lang_q['id']]
    return ''


def get_wikidata_original_lang(query: str, cache_file: str = "", verbose: bool = False) -> str:
    """Find original language directly in Wikidata, including films without enwiki."""
    query = _clean_query(query)
    cache = {}
    if cache_file:
        try:
            with open(cache_file) as f:
                cache = json.load(f)
            cached = cache.get(query)
            if isinstance(cached, str):
                return cached
            if isinstance(cached, dict) and cached.get('expires', 0) > time.time():
                return cached.get('lang', '')
        except (OSError, ValueError, TypeError):
            cache = {}

    year_match = re.search(r'\b((?:19|20)\d{2})\b', query)
    year = year_match.group(1) if year_match else ''
    title = re.sub(r'\s*\(?\b(?:19|20)\d{2}\b\)?\s*$', '', query).strip()
    if not title:
        title = query
    deadline = time.monotonic() + settings.WIKIDATA_LOOKUP_BUDGET
    iso = ''
    try:
        # Entity search provides labels and descriptions in one response. Use
        # them to fetch only plausible works, avoiding large unrelated items.
        searches = [
            {'action': 'wbsearchentities', 'search': title, 'language': 'en',
             'type': 'item', 'limit': 20, 'format': 'json'},
            # Full-text fallback also searches descriptions and reaches works
            # outside the first page of entity-name search results.
            {'action': 'query', 'list': 'search',
             'srsearch': f'{title} {year} film'.strip() if year else title,
             'srnamespace': 0, 'srlimit': 10, 'format': 'json'},
        ]
        for params in searches:
            found = _wikidata_api(params, deadline)
            candidates = {}
            if params['action'] == 'wbsearchentities':
                for item in found.get('search', []):
                    label = item.get('label', '')
                    description = item.get('description', '').lower()
                    if (re.sub(r'\W+', ' ', label.casefold()).strip() ==
                            re.sub(r'\W+', ' ', title.casefold()).strip() and
                            any(word in description for word in ('film', 'movie', 'series', 'anime')) and
                            (not year or year in description)):
                        candidates[item.get('id', '')] = item
                ids = list(candidates)
            else:
                ids = [item.get('title', '') for item in found.get('query', {}).get('search', [])]
            ids = [item for item in ids if re.fullmatch(r'Q\d+', item)]
            if not ids:
                continue
            entities = _wikidata_api({'action': 'wbgetentities', 'ids': '|'.join(ids),
                                     'props': ('claims' if candidates else
                                               'claims|labels|descriptions'),
                                     'languages': 'en', 'format': 'json'}, deadline)
            for entity_id in ids:
                entity = entities.get('entities', {}).get(entity_id, {})
                if entity_id in candidates:
                    entity = dict(entity)
                    entity['labels'] = {'en': {'value': candidates[entity_id]['label']}}
                    entity['descriptions'] = {'en': {'value': candidates[entity_id]['description']}}
                iso = _entity_language(entity, title, year)
                if iso:
                    break
            if iso:
                break
    except (OSError, ValueError, TimeoutError) as exc:
        # Network failures are transient: don't cache them as a missing title.
        if verbose:
            import sys
            print(f'Wikidata lookup failed for {query}: {exc}', file=sys.stderr)
        return ''

    if cache_file:
        try:
            cache[query] = iso if iso else {'lang': '', 'expires': time.time() + 3600}
            directory = os.path.dirname(os.path.abspath(cache_file))
            os.makedirs(directory, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix='.wikilang-', dir=directory)
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(cache, f)
                os.replace(temp_path, cache_file)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except OSError:
            pass
    return iso



# ═══════════════════════════════════════════════════════════════════════════════
# SERIES / SEASON EPISODE COUNT LOOKUP
# ═══════════════════════════════════════════════════════════════════════════════

def _wp_search(query: str, srlimit: int = 5) -> list:
    '''Search Wikipedia and return list of page titles.'''
    params = urllib.parse.urlencode({
        'action': 'query', 'list': 'search',
        'srsearch': query, 'format': 'json', 'srlimit': srlimit
    })
    req = urllib.request.Request(
        f'https://en.wikipedia.org/w/api.php?{params}',
        headers={'User-Agent': settings.UA_SATOR}
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=settings.TIMEOUT_WIKIDATA).read().decode())
    return [p['title'] for p in resp.get('query', {}).get('search', [])]


def _get_wikidata_id(wp_title: str) -> str:
    '''Get Wikidata Q-ID from a Wikipedia page title.'''
    params = urllib.parse.urlencode({
        'action': 'query', 'prop': 'pageprops',
        'titles': wp_title, 'format': 'json'
    })
    req = urllib.request.Request(
        f'https://en.wikipedia.org/w/api.php?{params}',
        headers={'User-Agent': settings.UA_SATOR}
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=settings.TIMEOUT_WIKIDATA).read().decode())
    for pid, pdata in resp.get('query', {}).get('pages', {}).items():
        if 'pageprops' in pdata and 'wikibase_item' in pdata['pageprops']:
            return pdata['pageprops']['wikibase_item']
    return ''


def _get_wikidata_entity(eid: str) -> dict:
    '''Get full Wikidata entity data.'''
    req = urllib.request.Request(
        f'https://www.wikidata.org/wiki/Special:EntityData/{eid}.json',
        headers={'User-Agent': settings.UA_SATOR}
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=settings.TIMEOUT_WIKIDATA).read().decode())
    return resp.get('entities', {}).get(eid, {})


def get_season_episode_count(series_query: str, season_num: int,
                              cache_file: str = "") -> int:
    '''Get the number of episodes in a given TV season via Wikipedia/Wikidata.

    Returns episode count (int) or 0 if not found.
    '''
    # Clean query for better searching
    cleaned = re.sub(r'\s*S\d+(E\d+)?\s*$', '', series_query).strip()
    if not cleaned:
        cleaned = series_query

    # Check cache
    cache_key = f'season:{cleaned}:{season_num}'
    if cache_file and os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cache = json.load(f)
            if cache_key in cache:
                return cache[cache_key]
        except (json.JSONDecodeError, OSError):
            pass

    try:
        # 1. Search Wikipedia — try multiple query variants
        queries_to_try = [
            cleaned,
            cleaned + ' TV series',
            cleaned + ' (TV series)',
        ]
        wp_title = ''
        for sq in queries_to_try:
            pages = _wp_search(sq)
            if pages:
                # Find first page that is likely the series (skip list pages)
                for p in pages:
                    title_lower = p.lower()
                    if 'list of' in title_lower:
                        continue
                    if 'episode' in title_lower and cleaned.lower() not in title_lower:
                        continue
                    wp_title = p
                    break
                if not wp_title and pages:
                    wp_title = pages[0]
                if wp_title:
                    break

        if not wp_title:
            return 0

        # 2. Get Wikidata ID
        qid = _get_wikidata_id(wp_title)
        if not qid:
            return 0

        # 3. Get Wikidata entity
        entity = _get_wikidata_entity(qid)
        claims = entity.get('claims', {})

        # 4. Find season entities via P527 (has part)
        season_qids = []
        for claim in claims.get('P527', []):
            val = claim.get('mainsnak', {}).get('datavalue', {})
            pid = val.get('value', {}).get('id', '')
            if pid:
                season_qids.append(pid)

        if not season_qids:
            return 0

        # 5. For each season entity, check if it matches our season number
        for sid in season_qids:
            s_entity = _get_wikidata_entity(sid)
            s_labels = s_entity.get('labels', {})
            s_label = s_labels.get('en', {}).get('value', '')
            s_claims = s_entity.get('claims', {})

            # Verify it's a television season (P31 = Q3464665)
            is_season = False
            for c in s_claims.get('P31', []):
                val = c.get('mainsnak', {}).get('datavalue', {})
                if val.get('value', {}).get('id') == 'Q3464665':
                    is_season = True
                    break
            if not is_season:
                continue

            # Extract season number from English label ("Show, season N")
            sn_match = re.search(r'season[,\s]*(\d+)', s_label, re.I)
            if not sn_match:
                continue
            if int(sn_match.group(1)) != season_num:
                continue

            # Get episode count (P1113)
            if 'P1113' not in s_claims:
                continue
            ep_amt = s_claims['P1113'][0].get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('amount', '0')
            ep_count = int(ep_amt.replace('+', ''))

            # Cache result
            if cache_file:
                try:
                    cache = {}
                    if os.path.exists(cache_file):
                        with open(cache_file) as f:
                            cache = json.load(f)
                    cache[cache_key] = ep_count
                    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                    with open(cache_file, 'w') as f:
                        json.dump(cache, f)
                except OSError:
                    pass

            return ep_count

        return 0

    except Exception:
        return 0


def get_series_season_count_wikidata(series_query: str,
                                     cache_file: str = "") -> int:
    """Get the total number of seasons for a TV series via Wikidata.

    Uses the same Wikipedia→Wikidata lookup as ``get_wikidata_original_lang``,
    then counts season-level entities (P527) that are instances of TV season (P31=Q3464665).

    Returns number of seasons (int), or 0 if not found.
    """
    # Guard: reject None/empty
    if not series_query:
        return 0
    # Clean query
    cleaned = re.sub(r'\s*S\d+(E\d+)?\s*$', '', series_query).strip()
    if not cleaned:
        cleaned = series_query

    # Check cache
    cache_key = f'season_count:{cleaned}'
    if cache_file and os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cache = json.load(f)
            if cache_key in cache:
                return cache[cache_key]
        except (json.JSONDecodeError, OSError):
            pass

    try:
        # 1. Search Wikipedia — try multiple query variants
        queries_to_try = [
            cleaned,
            cleaned + ' TV series',
            cleaned + ' (TV series)',
        ]
        wp_title = ''
        for sq in queries_to_try:
            pages = _wp_search(sq)
            if pages:
                for p in pages:
                    title_lower = p.lower()
                    if 'list of' in title_lower:
                        continue
                    wp_title = p
                    break
                if wp_title:
                    break

        if not wp_title:
            return 0

        # 2. Get Wikidata ID
        qid = _get_wikidata_id(wp_title)
        if not qid:
            return 0

        # 3. Get Wikidata entity
        entity = _get_wikidata_entity(qid)
        claims = entity.get('claims', {})

        # 4. Find season entities via P527 (has part) and count unique season numbers
        season_numbers = set()
        for claim in claims.get('P527', []):
            val = claim.get('mainsnak', {}).get('datavalue', {})
            sid = val.get('value', {}).get('id', '')
            if not sid:
                continue
            s_entity = _get_wikidata_entity(sid)
            s_claims = s_entity.get('claims', {})

            # Verify it's a television season (P31 = Q3464665)
            is_season = False
            for c in s_claims.get('P31', []):
                cv = c.get('mainsnak', {}).get('datavalue', {})
                if cv.get('value', {}).get('id') == 'Q3464665':
                    is_season = True
                    break
            if not is_season:
                continue

            # Extract season number from English label
            s_labels = s_entity.get('labels', {})
            s_label = s_labels.get('en', {}).get('value', '')
            sn_match = re.search(r'season[,\s]*(\d+)', s_label, re.I)
            if sn_match:
                season_numbers.add(int(sn_match.group(1)))

        season_count = len(season_numbers) if season_numbers else 0

        # Cache result
        if cache_file:
            try:
                cache = {}
                if os.path.exists(cache_file):
                    with open(cache_file) as f:
                        cache = json.load(f)
                cache[cache_key] = season_count
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                with open(cache_file, 'w') as f:
                    json.dump(cache, f)
            except OSError:
                pass

        return season_count

    except Exception:
        return 0
