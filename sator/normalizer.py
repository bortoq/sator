#!/usr/bin/env python3
"""File-name normalizer for torrents in qBittorrent.

Usage (indirect, via CLI ``-n`` flag):

    sator -s "Show" -sn 1 -a -n

After a torrent is added to qBittorrent, this module renames its files
according to user-configurable templates (see ``settings.py``) and writes
a sidecar ``.orig.json`` mapping original → new names.
"""

import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

from sator.quality import parse_quality, strip_modifiers, QualityInfo
from sator.title import parse_title


# ── Helpers ──────────────────────────────────────────────────────────────────

# Pattern to detect series files: S01, S01E01, etc.
_SERIES_PATTERN = re.compile(
    r'[.\s-]+S(?P<season>\d{2,})(?:E(?P<episode>\d{2,}))?',
    re.IGNORECASE,
)

_EXT_PATTERN = re.compile(r'\.(?P<ext>[a-zA-Z0-9]+)$')


def _parse_season_episode(file_name: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract season and episode numbers from a file name."""
    m = _SERIES_PATTERN.search(file_name)
    if not m:
        return None, None
    season = int(m.group('season'))
    episode = int(m.group('episode')) if m.group('episode') else None
    return season, episode


def _extract_ext(file_name: str) -> str:
    """Get the file extension without dot."""
    m = _EXT_PATTERN.search(file_name)
    return m.group('ext').lower() if m else ''


def _clean_show_name(file_name: str) -> str:
    """Derive a clean show/movie name from the torrent file name.

    Strips season/episode markers, quality tokens, release group, year, etc.
    """
    name = file_name.replace('_', ' ')

    # Remove extension
    name = re.sub(r'\.(mkv|mp4|avi|m2ts|ts|m4v|mov|wmv|flv|webm|mp3|flac|m4a)$',
                  '', name, flags=re.IGNORECASE)

    # Remove season/episode markers
    name = _SERIES_PATTERN.sub('', name)

    # Remove year in parens or standalone
    name = re.sub(r'\b(?:19|20)\d{2}\b', '', name)

    # Remove quality/resolution/codec tokens
    name = re.sub(
        r'\b(?:480[ip]|576[ip]|720[ip]|1080[ip]|2160[ip]'
        r'|[xh]\.?26[45]|HEVC|AV1|VP9|Xvid|Divx|AVC'
        r'|DD\W?5[. ]1|DDP?5[. ]1'
        r'|8bit|10bit|8-bit|10-bit'
        r'|848x480|1280x720|1920x1080|3840x2160|4096x2160)\b',
        '', name, flags=re.IGNORECASE
    )

    # Remove source tokens
    name = re.sub(
        r'\b(?:BluRay|WEB[-_. ]?DL|WEBRip|BDRip|BRRip|HDTV|DVD|DVDR|'
        r'SCREENER|TELESYNC|TELECINE|CAM|WORKPRINT|PDTV|SDTV|TVRip)\b',
        '', name, flags=re.IGNORECASE
    )

    # Remove modifiers
    name = strip_modifiers(name)

    # Remove release group at end: -GROUP
    name = re.sub(r'[-. ]+[a-zA-Z0-9]+$', '', name.strip())

    # Remove bracketed groups
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\(.*?\)', '', name)

    # Replace separators with spaces and normalize
    name = re.sub(r'[._-]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def _extract_release_group(file_name: str) -> str:
    """Extract release group from file name (reuses title.py logic)."""
    pt = parse_title(file_name)
    return pt.release_group


# ── Public API ───────────────────────────────────────────────────────────────


def compute_new_name(
    file_name: str,
    template_movie: str,
    template_series: str,
    quality: Optional[QualityInfo] = None,
    known_season: Optional[int] = None,
    known_episode: Optional[int] = None,
    known_show: Optional[str] = None,
    ep_title: str = '',
) -> Tuple[str, dict]:
    """Generate a new file name from the given template.

    Args:
        file_name: Original file name (e.g. ``Show.S01E01.1080p.WEB-DL.FLUX.mkv``).
        template_movie: Format string for movies (see settings.py).
        template_series: Format string for series (see settings.py).
        quality: Pre-parsed quality info (if None, parsed from file_name).
        known_season: Season number (if known from context, e.g. ``-sn``).
        known_episode: Episode number (if known).
        known_show: Show name (if known from query context).
        ep_title: Episode title (optional, from TMDB or parsed).

    Returns:
        ``(new_name, metadata_dict)`` where metadata_dict contains all
        extracted values for inspection / sidecar logging.
    """
    # Parse quality if not provided
    if quality is None:
        quality = parse_quality(file_name)

    # Extract extension
    ext = _extract_ext(file_name)

    # Extract season/episode
    season, episode = _parse_season_episode(file_name)
    if known_season is not None:
        season = known_season
    if known_episode is not None:
        episode = known_episode

    # Derive show name
    show = known_show if known_show else _clean_show_name(file_name)

    # Extract year from show name
    year_match = re.search(r'\b((?:19|20)\d{2})\b', file_name)
    year = int(year_match.group(1)) if year_match else None

    # Release group
    group = _extract_release_group(file_name)

    # Modifiers string
    mod_str = '/'.join(quality.modifiers) if quality.modifiers else ''

    # Quality label string for template
    quality_label = quality.quality_label

    # Determine if this is a series (has season number)
    is_series = season is not None

    metadata = {
        'title': ep_title if is_series and ep_title else show,
        'show': show,
        'year': year or 0,
        'season': season or 0,
        'episode': episode or 0,
        'ep_title': ep_title,
        'quality': quality_label,
        'resolution': f'{quality.resolution}p' if quality.resolution else '',
        'source': quality.source,
        'codec': quality.codec,
        'audio': quality.audio,
        'hdr': quality.hdr,
        'group': group,
        'mod': mod_str,
        'ext': ext,
    }

    # Choose template
    try:
        if is_series:
            new_name = template_series.format(**metadata)
        else:
            new_name = template_movie.format(**metadata)
    except KeyError as e:
        print(f'  \u26a0 Unknown placeholder in template: {e}', file=sys.stderr)
        new_name = file_name
        metadata['error'] = f'Unknown placeholder: {e}'

    # Clean up: remove artifacts from empty placeholders
    # Remove empty brackets [], (), etc.
    new_name = re.sub(r'\s*\[\s*\]\s*', '', new_name)
    new_name = re.sub(r'\s*\(\s*\)\s*', '', new_name)
    new_name = re.sub(r'\s*\{\s*\}', '', new_name)
    # Remove double spaces
    new_name = re.sub(r'\s+', ' ', new_name).strip()
    # Remove trailing/leading separators
    new_name = re.sub(r'[. ]$', '', new_name)

    return new_name, metadata


def build_sidecar(
    torrent_hash: str,
    torrent_name: str,
    file_map: List[Dict[str, str]],
    template_used: str,
    metadata: dict,
) -> dict:
    """Build the sidecar JSON structure.

    Args:
        torrent_hash: qBittorrent torrent hash.
        torrent_name: Original torrent name.
        file_map: List of ``{'original': ..., 'renamed': ...}`` dicts.
        template_used: The template string that was used.
        metadata: Metadata dict used for renaming.

    Returns:
        Serializable dict for JSON dump.
    """
    return {
        'torrent_hash': torrent_hash,
        'torrent_name': torrent_name,
        'renamed': True,
        'template': template_used,
        'metadata': metadata,
        'files': file_map,
    }


def write_sidecar(
    save_path: str,
    torrent_hash: str,
    torrent_name: str,
    file_map: List[Dict[str, str]],
    template_used: str,
    metadata: dict,
) -> Optional[str]:
    """Write sidecar JSON file to disk.

    Args:
        save_path: Directory where the torrent content is saved (qB save path).
        … Same as :func:`build_sidecar`.

    Returns:
        Path to the written sidecar file, or None if save_path does not exist.
    """
    # Verify save_path exists
    if not os.path.isdir(save_path):
        print(f'  \u26a0 Sidecar save path does not exist: {save_path}',
              file=sys.stderr)
        return None

    sidecar = build_sidecar(torrent_hash, torrent_name, file_map,
                            template_used, metadata)

    # Sanitize torrent_name for use as filename: strip dangerous chars
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', torrent_name)
    safe_name = safe_name[:100]  # limit length
    filename = f'{safe_name}.orig.json'
    sidecar_path = os.path.join(save_path, filename)

    with open(sidecar_path, 'w', encoding='utf-8') as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)

    return sidecar_path
