#!/usr/bin/env python3
"""Wikidata original language lookup."""

import json
import os
import re
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
    'Q8641': 'yi', 'Q8108': 'ka', 'Q8785': 'hy', 'Q9091': 'be', 'Q9255': 'ky',
    'Q33350': 'ce', 'Q13307': 'na', 'Q33823': 'ne', 'Q9260': 'tg',
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
    s = raw.lower()
    # Remove noise words
    for pat in _NOISE_WORDS:
        s = re.sub(r'\b' + pat + r'\b', '', s)
    # Remove extra spaces
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.strip(' -_').strip()
    return s or raw

def get_wikidata_original_lang(query: str, cache_file: str = "") -> str:
    """Get original language ISO code for a movie via Wikidata.
    Returns ISO 639-1 code or empty string.
    """
    # Clean query: strip torrent noise words for better Wikipedia search
    query = _clean_query(query)
    
    # Check cache
    if cache_file and os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cache = json.load(f)
            if query in cache:
                return cache[query]
        except (json.JSONDecodeError, OSError):
            pass

    try:
        # 1. Wikipedia search — try multiple queries, iterate results
        queries_to_try = [
            query,
            query + ' film',
            query + ' TV series',
        ]
        def _get_lang_for_title(wp_title):
            params = urllib.parse.urlencode({
                'action': 'query', 'prop': 'pageprops',
                'titles': wp_title, 'format': 'json'
            })
            req = urllib.request.Request(
                f'https://en.wikipedia.org/w/api.php?{params}',
                headers={'User-Agent': settings.UA_SATOR}
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=settings.TIMEOUT_WIKIDATA).read().decode())
            eid = None
            for pid, pdata in resp.get('query', {}).get('pages', {}).items():
                if 'pageprops' in pdata and 'wikibase_item' in pdata['pageprops']:
                    eid = pdata['pageprops']['wikibase_item']
                    break
            if not eid:
                return ""
            # 3. Get Wikidata entity
            req = urllib.request.Request(
                f'https://www.wikidata.org/wiki/Special:EntityData/{eid}.json',
                headers={'User-Agent': settings.UA_SATOR}
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=settings.TIMEOUT_WIKIDATA).read().decode())
            claims = resp.get('entities', {}).get(eid, {}).get('claims', {})
            lang_claim = claims.get('P364', []) or claims.get('P407', []) or claims.get('P2439', [])
            if not lang_claim:
                return ""
            lang_q = lang_claim[0].get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id', '')
            if not lang_q:
                return ""
            return WIKIDATA_ISO.get(lang_q, "")

        iso = ""
        for sq in queries_to_try:
            params = urllib.parse.urlencode({
                'action': 'query', 'list': 'search',
                'srsearch': sq, 'format': 'json', 'srlimit': settings.WIKIPEDIA_SRLIMIT
            })
            req = urllib.request.Request(
                f'https://en.wikipedia.org/w/api.php?{params}',
                headers={'User-Agent': settings.UA_SATOR}
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=settings.TIMEOUT_WIKIDATA).read().decode())
            pages = resp.get('query', {}).get('search', [])
            if not pages:
                continue
            # Extract meaningful words from the cleaned query for relevance
            query_words = set(w for w in re.sub(r'[^a-z0-9 ]', ' ', query).split() if len(w) > 1)
            for p in pages:
                # Skip if the result title doesn't share at least one word with
                # the original query — avoids false positives from unrelated pages
                if query_words:
                    title_lower = p['title'].lower()
                    if not any(w in title_lower for w in query_words):
                        continue
                iso = _get_lang_for_title(p['title'])
                if iso:
                    break
            if iso:
                break
        if not iso:
            return ""


        # Cache result
        if iso and cache_file:
            try:
                cache = {}
                if os.path.exists(cache_file):
                    with open(cache_file) as f:
                        cache = json.load(f)
                cache[query] = iso
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                with open(cache_file, 'w') as f:
                    json.dump(cache, f)
            except OSError:
                pass

        return iso
    except Exception:
        return ""



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
