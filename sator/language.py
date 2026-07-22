#!/usr/bin/env python3
"""Language parser for torrent titles."""

import os
import re
from typing import Optional, List
from sator.iso_langs import iso_code, _ISO_BY_1, _ISO_BY_3

# ═══════════════════════════════════════════════════════════════════════════════
# LANGUAGE PARSER (from Radarr LanguageParser.cs)
# ═══════════════════════════════════════════════════════════════════════════════

# Language codes that the parser can detect
LANG_PATTERNS = {
    # (regex_pattern, iso_code)
    "english": [r'\beng\b', r'english'],
    "french": [r'\b(?:FR|VO|VF|VFF|VFQ|VFI|VF2|TRUEFRENCH|FRENCH|FRE)\b', r'\bfrench\b'],
    "german": [r'\b(?:swiss)?german\b', r'\bger\b', r'videomann', r'ger[.\s]dub'],
    "italian": [r'\b(?:ita|italian)\b'],
    "spanish": [r'\bespañol\b', r'\bcastellano\b', r'\blatino\b', r'\b(?:spa|esp)\b'],
    "dutch": [r'\bdutch\b', r'\bflemish\b'],
    "japanese": [r'\bjap(?:anese)?\b'],
    "russian": [r'\b(?:rus|ru)\b'],
    "chinese": [r'\[(?:CH[ST]|BIG5|GB)\]', r'简', r'繁', r'字幕', r'\bchinese\b', r'\bmandarin\b', r'\bcantonese\b'],
    "korean": [r'\bkor(?:ean)?\b'],
    "polish": [r'\b(?:PL\W?DUB|DUB\W?PL|LEK\W?PL|PL\W?LEK)\b', r'\bpolish\b'],
    "portuguese": [r'\bportuguese\b', r'\bpt\b(?!-BR)'],
    "brazilian": [r'\b(dublado|pt-BR)\b', r'\bbrazilian\b'],
    "swedish": [r'\bswedish\b', r'\bswe\b'],
    "danish": [r'\bdanish\b', r'\bdan\b'],
    "norwegian": [r'\bnorwegian\b', r'\bnor\b'],
    "finnish": [r'\bfinnish\b', r'\bfin\b'],
    "turkish": [r'\bturkish\b', r'\btur\b'],
    "hungarian": [r'\b(?:HUNDUB|HUN)\b', r'\bhungarian\b'],
    "hebrew": [r'\b(?:HebDub|HebDubbed)\b', r'\bhebrew\b'],
    "arabic": [r'\barabic\b', r'\bara\b'],
    "thai": [r'\bthai\b'],
    "hindi": [r'\bhindi\b'],
    "romanian": [r'\bromanian\b', r'\brodubbed\b'],
    "bulgarian": [r'\bbulgarian\b', r'\bbgaudio\b'],
    "ukrainian": [r'(?:(?:\dx)?UKR)', r'\bukrainian\b'],
    "greek": [r'\bgreek\b'],
    "czech": [r'\bczech\b', r'\bCZ\b'],
    "slovak": [r'\bslovak\b', r'\bSK\b'],
    "lithuanian": [r'\blithuanian\b', r'\bLT\b'],
    "latvian": [r'\blatvian\b', r'\b(?:lat|lav|lv)\b'],
    "croatian": [r'\bcroatian\b'],
    "serbian": [r'\bserbian\b'],
    "bosnian": [r'\bbosnian\b'],
    "estonian": [r'\bestonian\b'],
    "slovenian": [r'\bslovenian\b'],
    "icelandic": [r'\bicelandic\b'],
    "vietnamese": [r'\bvietnamese\b', r'\bVIE\b'],
    "bengali": [r'\bbengali\b'],
    "persian": [r'\bpersian\b'],
    "telugu": [r'\btel(?:ugu)?\b'],
    "tamil": [r'\btamil\b'],
    "malayalam": [r'\bmalayalam\b'],
    "kannada": [r'\bkannada\b'],
    "albanian": [r'\balbanian\b'],
    "afrikaans": [r'\bafrikaans\b'],
    "marathi": [r'\bmarathi\b'],
    "tagalog": [r'\btagalog\b'],
    "urdu": [r'\burdu\b'],
    "romansh": [r'\bromansh\b', r'\brumantsch\b', r'\bromansch\b'],
    "mongolian": [r'\bmongolian\b', r'\bkhalkha\b'],
    "georgian": [r'\bgeorgian\b', r'\b(?:geo|ka|kat)\b'],
    "catalan": [r'\bcatalan?\b', r'\bcatalán\b', r'\bcatalà\b'],
    "flemish": [r'\bflemish\b'],
}

# Compiled patterns
_LANG_COMPILED = {}
for lang, patterns in LANG_PATTERNS.items():
    _LANG_COMPILED[lang] = [re.compile(p, re.IGNORECASE) for p in patterns]

# Case-sensitive patterns
_CASE_SENSITIVE_PATTERNS = {
    "lithuanian": re.compile(r'\bLT\b'),
    "czech": re.compile(r'\bCZ\b'),
    "polish": re.compile(r'\bPL\b'),
    "bulgarian": re.compile(r'\bBG\b'),
    "slovak": re.compile(r'\bSK\b'),
    "spanish": re.compile(r'\b(?<!DTS[._ -])ES\b'),
}


def parse_languages(title: str) -> List[str]:
    """Parse language ISO codes from a torrent/release title.
    Returns list of ISO 639-1 codes found in the title.
    """
    detected = set()
    title_lower = title.lower()

    # Full-name matching
    full_name_map = {
        'english': 'en', 'spanish': 'es', 'danish': 'da', 'dutch': 'nl',
        'japanese': 'ja', 'icelandic': 'is', 'mandarin': 'zh', 'cantonese': 'zh',
        'chinese': 'zh', 'korean': 'ko', 'russian': 'ru', 'romanian': 'ro',
        'hindi': 'hi', 'arabic': 'ar', 'thai': 'th', 'bulgarian': 'bg',
        'polish': 'pl', 'vietnamese': 'vi', 'swedish': 'sv', 'norwegian': 'no',
        'finnish': 'fi', 'turkish': 'tr', 'portuguese': 'pt', 'hungarian': 'hu',
        'hebrew': 'he', 'ukrainian': 'uk', 'persian': 'fa', 'bengali': 'bn',
        'slovak': 'sk', 'latvian': 'lv', 'tamil': 'ta', 'telugu': 'te',
        'malayalam': 'ml', 'kannada': 'kn', 'albanian': 'sq', 'afrikaans': 'af',
        'marathi': 'mr', 'tagalog': 'tl', 'urdu': 'ur', 'croatian': 'hr',
        'serbian': 'sr', 'bosnian': 'bs', 'estonian': 'et', 'slovenian': 'sl',
        'greek': 'el', 'czech': 'cs',
    }
    for name, code in full_name_map.items():
        if name in title_lower and code not in {'pt'}:
            # Special case: 'portuguese' should not match Brazilian
            if name == 'portuguese' and ('brazil' in title_lower or 'dublado' in title_lower):
                continue
            detected.add(code)

    # Brazilian Portuguese
    if 'brazilian' in title_lower or 'dublado' in title_lower or 'pt-br' in title_lower:
        detected.add('pt')  # We use 'pt' for both, but track as Brazilian variant

    # Regex-based language detection
    for lang, patterns in _LANG_COMPILED.items():
        code = iso_code(lang)
        if not code:
            continue
        for pat in patterns:
            if pat.search(title):
                detected.add(code)
                break

    # Case-sensitive patterns
    for lang, pat in _CASE_SENSITIVE_PATTERNS.items():
        code = iso_code(lang)
        if code and pat.search(title):
            detected.add(code)

    # Special: if DL (Dual Language) is found with German, treat as multi
    if 'de' in detected and re.search(r'(?<![A-Za-z])DL\b', title, re.IGNORECASE) and 'WEB' not in title.upper():
        detected.add('en')

    if 'de' in detected and re.search(r'\bML\b', title, re.IGNORECASE):
        detected.add('en')

    return sorted(detected)

def parse_subtitle_language(filename: str) -> Optional[str]:
    """Parse language from subtitle filename.
    Returns ISO 639-1 code or None.
    """
    basename = os.path.splitext(os.path.basename(filename))[0]
    # Match pattern like: movie.eng.srt, movie.english.forced.srt
    m = re.search(r'[-_. ](?P<iso>[a-z]{2,3})([-_. ](?:forced|foreign|default|cc|psdh|sdh))?$', basename, re.IGNORECASE)
    if m:
        code = m.group('iso').lower()
        # Try 2-letter first, then 3-letter
        entry = _ISO_BY_1.get(code) or _ISO_BY_3.get(code)
        if entry:
            return entry[0]
    return None

