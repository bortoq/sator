#!/usr/bin/env python3
"""Wikidata original language lookup."""

import json
import os
import re
import urllib.parse
import urllib.request

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

def get_wikidata_original_lang(query: str, cache_file: str = "") -> str:
    """Get original language ISO code for a movie via Wikidata.
    Returns ISO 639-1 code or empty string.
    """
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
        # 1. Wikipedia search
        params = urllib.parse.urlencode({
            'action': 'query', 'list': 'search',
            'srsearch': query + ' film', 'format': 'json', 'srlimit': 1
        })
        req = urllib.request.Request(
            f'https://en.wikipedia.org/w/api.php?{params}',
            headers={'User-Agent': 'sator/0.1'}
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        pages = resp.get('query', {}).get('search', [])
        if not pages:
            return ""
        title = pages[0]['title']

        # 2. Get wikibase ID
        params = urllib.parse.urlencode({
            'action': 'query', 'prop': 'pageprops',
            'titles': title, 'format': 'json'
        })
        req = urllib.request.Request(
            f'https://en.wikipedia.org/w/api.php?{params}',
            headers={'User-Agent': 'sator/0.1'}
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
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
            headers={'User-Agent': 'sator/0.1'}
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        claims = resp.get('entities', {}).get(eid, {}).get('claims', {})
        lang_claim = claims.get('P364', []) or claims.get('P407', []) or claims.get('P2439', [])
        if not lang_claim:
            return ""
        lang_q = lang_claim[0].get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id', '')
        if not lang_q:
            return ""

        iso = WIKIDATA_ISO.get(lang_q, "")

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

