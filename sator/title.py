#!/usr/bin/env python3
"""Title parser for torrent filenames."""

import re
from dataclasses import dataclass, field
from typing import Optional, List
from sator.quality import QualityInfo, parse_quality
from sator.language import parse_languages

# ═══════════════════════════════════════════════════════════════════════════════
# TITLE PARSER (from Radarr Parser.cs)
# ═══════════════════════════════════════════════════════════════════════════════

# Edition patterns
EDITION_REGEX = re.compile(
    r'\(?\b(?P<edition>('
    r'((Recut\.|Extended\.|Ultimate\.)?'
    r'(Director\.?s|Collector\.?s|Theatrical|Ultimate|Extended|Despecialized|'
    r'(Special|Rouge|Final|Assembly|Imperial|Diamond|Signature|Hunter|Rekall)'
    r'(?=(\.(Cut|Edition|Version)))?'
    r'|\d{2,3}(th)?\.Anniversary)'
    r'(\.(Cut|Edition|Version))?'
    r'(\.(Extended|Uncensored|Remastered|Unrated|Uncut|Open\.?Matte|IMAX|Fan\.?Edit))?'
    r')'
    r'|((Uncensored|Remastered|Unrated|Uncut|Open\.?Matte|IMAX|Fan\.?Edit|Restored|((2|3|4)in1)))'
    r'))\b\)?',
    re.IGNORECASE
)

YEAR_REGEX = re.compile(r'\b(?P<year>(?:19|20)\d{2})(?!p|i|px|\]|\.\d{2,})')


# Simple release group patterns (no variable-length look-behind)
RELEASE_GROUP_DASH = re.compile(
    r'-(?P<group>[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)?)(?:\b|[-._ ]|$)',
    re.IGNORECASE
)


BRACKET_GROUP_REGEX = re.compile(r'[-._ ]\[(?P<group>[a-z0-9]+)\]$', re.IGNORECASE)
ANIME_GROUP_REGEX = re.compile(r'^\[(?P<group>[^\]]+)\]', re.IGNORECASE)


HARDCODED_SUBS_REGEX = re.compile(
    r'\b((?P<hcsub>\w+SUBS?)|(?P<hc>(HC|SUBBED)))\b',
    re.IGNORECASE
)


@dataclass
class ParsedTitle:
    title: str = ""
    year: Optional[int] = None
    edition: str = ""
    release_group: str = ""
    languages: List[str] = field(default_factory=list)
    quality: QualityInfo = field(default_factory=QualityInfo)
    hardcoded_subs: Optional[str] = None
    original_title: str = ""


def parse_title(raw_title: str) -> ParsedTitle:
    """Parse a torrent/release title and extract structured information."""
    result = ParsedTitle(original_title=raw_title)

    # Remove extension
    title = re.sub(r'\.(mkv|mp4|avi|m2ts|ts|m4v|mov|wmv|flv|webm)$', '', raw_title, flags=re.IGNORECASE)
    title = title.strip().replace('_', ' ')

    # Extract anime group [Subgroup]
    anime_match = ANIME_GROUP_REGEX.search(title)
    if anime_match:
        result.release_group = anime_match.group('group')
        title = ANIME_GROUP_REGEX.sub('', title).strip()

    # Extract edition
    edition_match = EDITION_REGEX.search(title)
    if edition_match:
        result.edition = edition_match.group('edition').replace('.', ' ')

    # Step 1: Remove resolution/quality/codec artifacts BEFORE year extraction
    # This prevents "2011.1080p" from confusing the year matcher
    cleaned_for_year = re.sub(
        r'\b(?:480[ip]|576[ip]|720[ip]|1080[ip]|2160[ip]'
        r'|[xh]\.?26[45]|HEVC|AV1|VP9|Xvid|Divx|AVC'
        r'|DD\W?5[. ]1|DDP?5[. ]1'
        r'|8bit|10bit|8-bit|10-bit'
        r'|848x480|1280x720|1920x1080|3840x2160|4096x2160)\b',
        ' ', title, flags=re.IGNORECASE
    )

    # Extract year from cleaned title
    year_match = YEAR_REGEX.search(cleaned_for_year)
    if year_match:
        result.year = int(year_match.group('year'))
        # Remove year from original title for further cleaning
        title = YEAR_REGEX.sub('', title, count=1).strip()

    # Step 2: Further clean the title
    clean = re.sub(
        r'\b(?:480[ip]|576[ip]|720[ip]|1080[ip]|2160[ip]'
        r'|[xh]\.?26[45]|HEVC|AV1|VP9|Xvid|Divx|AVC'
        r'|DD\W?5[. ]1|DDP?5[. ]1'
        r'|8bit|10bit|8-bit|10-bit'
        r'|848x480|1280x720|1920x1080|3840x2160|4096x2160)\b',
        '', title, flags=re.IGNORECASE
    )

    # Remove edition text from clean title
    if result.edition:
        clean = re.sub(re.escape(result.edition), '', clean, flags=re.IGNORECASE)

    # Remove bracketed groups
    clean = re.sub(r'\[.*?\]', '', clean)

    # Remove parenthesized groups
    clean = re.sub(r'\(.*?\)', '', clean)

    # Remove common prefixes like [url]
    clean = re.sub(r'^[\[(][^\])]*[)\]]\s*', '', clean)

    # Clean up separators
    clean = re.sub(r'[._-]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    # Remove remaining year artifacts from clean title
    if result.year:
        clean = re.sub(r'\b' + str(result.year) + r'\b', '', clean).strip()

    result.title = clean

    # Parse languages
    result.languages = parse_languages(raw_title)

    # Parse quality
    result.quality = parse_quality(raw_title)

    # Hardcoded subs
    hc_match = HARDCODED_SUBS_REGEX.search(raw_title)
    if hc_match:
        if hc_match.group('hcsub'):
            sub_val = hc_match.group('hcsub')
            # Filter out false positives
            if not re.match(r'^(SOFT|MULTI|HORRIBLE)SUBS?$', sub_val, re.IGNORECASE):
                result.hardcoded_subs = sub_val
        elif hc_match.group('hc'):
            result.hardcoded_subs = "Generic Hardcoded Subs"

    # Release group (if not already set by anime match)
    if not result.release_group:
        bracket_match = BRACKET_GROUP_REGEX.search(raw_title)
        if bracket_match:
            result.release_group = bracket_match.group('group')
        else:
            # Use a smarter approach: look for -GROUP pattern in cleaned title
            # that excludes common quality/source/codec tokens
            cleaned_for_group = re.sub(
                r'\b(?:480[ip]|576[ip]|720[ip]|1080[ip]|2160[ip]'
                r'|[xh]\.?26[45]|HEVC|AV1|VP9|Xvid|Divx|AVC'
                r'|WEB\b.*?(?:DL|Rip)'
                r'|BluRay|Blu-Ray|BDRip|BRRip|HDTV|WEBRip|WEB-DL'
                r'|DTS|AC3|AAC|FLAC|TrueHD|PCM|MP3|Opus'
                r'|HDR|HDR10|HLG|Dolby[-. ]?Vision|DOVI'
                r'|REMASTERED|REMUX|REPACK|PROPER|INTERNAL|READNFO)', 
                '', raw_title, flags=re.IGNORECASE
            )
            rg_match = RELEASE_GROUP_DASH.search(cleaned_for_group)
            if rg_match:
                group = rg_match.group('group')
                # Filter out strings that look like years or other metadata
                ignore = {'DL', 'Rip', 'HD', 'TV', 'ES', 'EN', 'DE', 'FR', 'IT', 'PT', 'RU', 'JA', 'KO', 'ZH'}
                if group not in ignore and not re.match(r'^\d{4}$', group) and len(group) > 1:
                    result.release_group = group

    return result

