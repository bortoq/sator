#!/usr/bin/env python3
"""Utility functions for the CLI — extracted from cli.py to reduce module size."""

import argparse
import json
import os
import re
import sys
from typing import List, Optional

from sator.normalizer import compute_new_name, write_sidecar, _parse_season_episode
from sator.qb_client import QBClient, QBConfig
from sator.tmdb import get_season_episode_titles, _load_tmdb_key
from sator import settings

# ── Hash helpers ────────────────────────────────────────────────────────────

_MAGNET_HASH_RE = re.compile(r'btih:([a-fA-F0-9]+)', re.IGNORECASE)


def _extract_info_hash(magnet: str) -> str:
    """Extract the info_hash (btih) from a magnet URI."""
    m = _MAGNET_HASH_RE.search(magnet)
    return m.group(1).lower() if m else ''


def _find_torrent_by_hash(client: QBClient, info_hash: str) -> Optional[dict]:
    """Find a torrent in qB by info_hash (prefix match)."""
    torrents = client.get_torrents()
    for t in torrents:
        t_hash = t.get('hash', '').lower()
        if t_hash.startswith(info_hash):
            return t
    return None


# ── File parsing ───────────────────────────────────────────────────────────

def _parse_sator_file(path: str) -> list:
    """Parse a sator-format file and return list of dicts with magnet + metadata.

    File format (sator -o output)::

        # [source] title
        # Size: ... | quality_label | seeders: N
        # Normalized: <normalized_file_name>
        # Meta: {"show_name": "...", "season": N, "episode": N, ...}
        magnet:?xt=urn:btih:...

    Lines starting with ``# Meta:`` contain JSON metadata for re-ingestion.
    Plain magnet lines are also accepted (backward compat).
    """
    if not os.path.exists(path):
        print(f'\u2716 File not found: {path}', file=sys.stderr)
        sys.exit(1)
    entries = []
    current_meta = {}
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith('# Meta:'):
                try:
                    current_meta = json.loads(s[7:].strip())
                except (json.JSONDecodeError, ValueError):
                    current_meta = {}
            elif s.startswith('#') or s.startswith('//'):
                continue
            elif s.startswith('magnet:'):
                entry: dict = {'magnet': s}
                if current_meta.get('show_name'):
                    entry['show_name'] = current_meta['show_name']
                if current_meta.get('season'):
                    entry['season'] = int(current_meta['season'])
                if current_meta.get('episode'):
                    entry['episode'] = int(current_meta['episode'])
                if current_meta.get('normalized'):
                    entry['normalized'] = current_meta['normalized']
                entries.append(entry)
                current_meta = {}
            else:
                raise ValueError(f"Unexpected line in sator file: {s[:80]!r}")
    return entries


# ── Normalization ──────────────────────────────────────────────────────────

def _normalize_torrents(
    parsed: argparse.Namespace,
    added_magnets: list,
    all_torrents: list,
    added_count: int,
):
    """After adding torrents to qB, rename files according to templates.

    For series with ``-sn``, attempts to fetch episode titles from TMDB
    to fill the ``{ep_title}`` placeholder in the template.
    """
    if not added_magnets:
        return

    print('  \u2022 Normalizing file names...', file=sys.stderr)

    # Resolve TMDB key
    tmdb_key = (parsed.tmdb_key or '') or _load_tmdb_key()

    # Build QBClient
    config = QBConfig(url=parsed.qb_url)
    client = QBClient(config)

    # Determine template
    is_series = bool(parsed.season_number)
    template = settings.TEMPLATE_SERIES if is_series else settings.TEMPLATE_MOVIE

    # ── Pre-fetch episode titles from TMDB ──────────────────────────────────
    _ep_titles_cache: dict = {}  # (show_name, season) -> {1: "Pilot", ...}
    if is_series and tmdb_key:
        seen_pairs = set()
        for item in added_magnets:
            show_name = item.get('show_name', '')
            season = item.get('season')
            if show_name and season and (show_name, season) not in seen_pairs:
                seen_pairs.add((show_name, season))
                titles = get_season_episode_titles(show_name, season, tmdb_key)
                if titles:
                    _ep_titles_cache[(show_name, season)] = titles
                    if parsed.verbose:
                        count = len(titles)
                        print(f'  \u2022 TMDB: {show_name} S{season:02d} '
                              f'({count} episode titles)', file=sys.stderr)

    renamed_count = 0
    error_count = 0

    for item in added_magnets:
        magnet = item['magnet']
        info_hash = _extract_info_hash(magnet)
        if not info_hash:
            continue

        # Find torrent in qB
        torrent = _find_torrent_by_hash(client, info_hash)
        if not torrent:
            continue

        torrent_hash = torrent['hash']
        torrent_name = torrent.get('name', '')
        save_path = torrent.get('save_path', '')

        # Get files
        files = client.get_torrent_files(torrent_hash)
        if not files:
            continue

        # Get per-torrent context
        show_name = item.get('show_name', torrent_name)
        known_season = item.get('season')
        known_episode = item.get('episode')

        # Look up episode titles for this show/season
        ep_titles = _ep_titles_cache.get((show_name, known_season), {})

        # Rename each file
        sidecar_files = []
        metadata = {}
        template_used = template

        for f in files:
            old_name = f.get('name', '')
            if not old_name:
                continue

            # Detect episode number from file name (or use known)
            _, file_ep = _parse_season_episode(old_name)
            ep_num = file_ep or known_episode

            # Look up episode title
            ep_title = ep_titles.get(ep_num, '') if ep_num else ''

            new_name, meta = compute_new_name(
                old_name,
                template_movie=settings.TEMPLATE_MOVIE,
                template_series=settings.TEMPLATE_SERIES,
                quality=None,
                known_season=known_season,
                known_episode=ep_num,
                known_show=show_name,
                ep_title=ep_title,
            )

            # Fallback: if we had a season from context but file didn't have episode
            if known_episode is not None and file_ep is None:
                meta['episode'] = known_episode
                new_name, meta = compute_new_name(
                    old_name,
                    template_movie=settings.TEMPLATE_MOVIE,
                    template_series=settings.TEMPLATE_SERIES,
                    quality=None,
                    known_season=known_season,
                    known_episode=known_episode,
                    known_show=show_name,
                    ep_title=ep_title,
                )

            if new_name == old_name:
                continue

            # Rename via API
            try:
                result = client.rename_file(torrent_hash, old_name, new_name)
                if isinstance(result, dict) and result.get('error'):
                    if parsed.verbose:
                        print(f'    \u2717 rename error: {result["error"]}', file=sys.stderr)
                    error_count += 1
                else:
                    renamed_count += 1
                    sidecar_files.append({'original': old_name, 'renamed': new_name})
                    metadata = meta
                    template_used = template
            except Exception as e:
                if parsed.verbose:
                    print(f'    \u2717 rename exception: {e}', file=sys.stderr)

        # Write sidecar
        if sidecar_files and save_path:
            try:
                write_sidecar(
                    save_path, torrent_hash, torrent_name,
                    sidecar_files, template_used, metadata,
                )
            except OSError as e:
                if parsed.verbose:
                    print(f'    \u26a0 Sidecar write error: {e}', file=sys.stderr)

    print(f'  \u2022 Renamed: {renamed_count} files  (errors: {error_count})', file=sys.stderr)
