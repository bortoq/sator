#!/usr/bin/env python3
"""Filter torrent results against user criteria."""

from dataclasses import asdict
from typing import Optional
from sator.quality import parse_quality
from sator.language import parse_languages
from sator.iso_langs import iso_name

def filter_result_json(result: dict, filters: dict) -> Optional[dict]:
    """Filter a torrent result dict against filter criteria.
    Returns the result if it passes, None if filtered out.
    """
    title = result.get('title', '')
    size_bytes = int(result.get('size_bytes', 0))

    # Resolution bounds
    rl = filters.get('rl')
    rb = filters.get('rb')
    quality = parse_quality(title)

    if rl is not None:
        res_rl = _parse_res_filter(rl)
        if res_rl and quality.resolution > res_rl:
            return None

    if rb is not None:
        res_rb = _parse_res_filter(rb)
        if res_rb and quality.resolution > 0 and quality.resolution < res_rb:
            return None

    # Size bounds
    zl = filters.get('zl')
    zb = filters.get('zb')
    if zl and size_bytes > 0 and size_bytes > zl:
        return None
    if zb and size_bytes > 0 and size_bytes < zb:
        return None

    # Language filters
    lang_filters = filters.get('lang', [])
    if lang_filters:
        detected = parse_languages(title)
        has_lang = any(lc in detected for lc in lang_filters)
        if not has_lang:
            # If no language detected in title AND filter is only English,
            # pass through (English is the default/unmarked language)
            if detected or lang_filters != ['en']:
                return None

    # Subtitle filters
    subs_filters = filters.get('subs', [])
    if subs_filters:
        has_subs = any(f'sub.{sc}' in title.lower() or f'{sc}.sub' in title.lower()
                       for sc in subs_filters)
        # Also check full language name
        for sc in subs_filters:
            sn = iso_name(sc)
            if sn:
                has_subs = has_subs or f'sub.{sn.lower()}' in title.lower() or f'{sn.lower()}.sub' in title.lower()
        if not has_subs:
            return None

    # Enrich with parsed info
    result['_quality'] = asdict(quality)
    result['_languages'] = parse_languages(title)
    return result

def _parse_res_filter(val) -> Optional[int]:
    """Parse resolution filter value to integer."""
    val = str(val).lower()
    if '2160' in val or '4k' in val:
        return 2160
    if '1080' in val or 'fhd' in val:
        return 1080
    if '720' in val or 'hd' in val:
        return 720
    if '480' in val or 'sd' in val:
        return 480
    return None

