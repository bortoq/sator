#!/usr/bin/env python3
"""TMDB enrichment for search queries and episode titles.

Best-effort: if no API key is available, all functions are no-ops.

API key sources (in order of precedence):
  1. ``api_key`` parameter passed directly
  2. ``--tmdb-key`` CLI argument (stored in filters)
  3. ``tmdb_key`` line in ``~/.config/sator/config``
"""

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Dict, List, Optional
from sator import settings

# Default config path
CONFIG_PATH = os.path.expanduser(settings.CONFIG_PATH)

# ── Disk caches ──────────────────────────────────────────────────────────────

_EPISODE_CACHE_PATH = os.path.join(
    os.path.expanduser(settings.CACHE_DIR), 'episodes.json'
)

# TTL in seconds: cache entries older than this are discarded
CACHE_TTL = 7 * 24 * 3600  # 7 days

def _load_episode_cache() -> dict:
    """Load episode title cache from disk, discarding entries older than CACHE_TTL."""
    import time
    try:
        with open(_EPISODE_CACHE_PATH) as f:
            raw = json.load(f)
        now = time.time()
        result = {}
        for show_key, episodes in raw.items():
            # Check timestamp
            ts = episodes.get('_cached_at', 0)
            if now - ts > CACHE_TTL:
                continue
            titles = episodes.get('titles', {})
            if not titles:
                continue
            result[show_key] = {int(k): v for k, v in titles.items()}
        return result
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return {}

def _save_episode_cache(cache: dict):
    """Save episode title cache to disk with timestamp for TTL."""
    import time
    try:
        os.makedirs(os.path.dirname(_EPISODE_CACHE_PATH), exist_ok=True)
        # Wrap in timestamp format
        now = time.time()
        to_save = {}
        for key, titles in cache.items():
            to_save[key] = {'titles': titles, '_cached_at': now}
        with open(_EPISODE_CACHE_PATH, 'w') as f:
            json.dump(to_save, f, indent=2, ensure_ascii=False)
    except OSError:
        pass

# ── Key loading ──────────────────────────────────────────────────────────────

def _load_tmdb_key() -> str:
    """Load TMDB API key from config file."""
    try:
        with open(CONFIG_PATH) as f:
            for line in f:
                if line.startswith('tmdb_key'):
                    return line.split('=', 1)[1].strip()
    except (OSError, IndexError):
        pass
    return ''

def _resolve_key(api_key: str = '') -> str:
    """Resolve the effective API key from best available source."""
    return api_key or _load_tmdb_key()

# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _tmdb_get(endpoint: str, api_key: str, params: dict = None) -> Optional[dict]:
    """Make a GET request to TMDB API."""
    if not api_key:
        return None
    url = f'https://api.themoviedb.org/3/{endpoint.lstrip("/")}'
    params = dict(params or {})
    params['api_key'] = api_key
    url += '?' + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': settings.UA_TMDB})
        with urllib.request.urlopen(req, timeout=settings.TIMEOUT_TMDB) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

# ── Public API ───────────────────────────────────────────────────────────────

def enrich_query(query: str, api_key: str = '') -> str:
    """Enrich a search query with TMDB data.

    If the query looks like a movie title (no year), try to fetch the
    release year from TMDB. Returns enriched query (with year) or
    original query if anything fails.

    api_key overrides the config file key.
    """
    key = _resolve_key(api_key)
    if not key:
        return query

    # Skip queries that already have a year
    if re.search(settings.TMDB_YEAR_PATTERN, query):
        return query

    # In-memory cache
    global _cache
    if query in _cache:
        return _cache[query]

    try:
        data = _tmdb_get('search/multi', key, {'query': query})
        if data and data.get('results'):
            result = data['results'][0]
            year = result.get('release_date') or result.get('first_air_date', '')
            if year and len(year) >= 4:
                enriched = f'{query} {year[:4]}'
                _cache[query] = enriched
                return enriched
    except Exception:
        pass

    _cache[query] = query
    return query


def get_tv_show_id(show_name: str, api_key: str = '') -> Optional[int]:
    """Get TMDB TV show ID by name.

    Returns the first matching TV show's TMDB ID, or None if not found.
    """
    key = _resolve_key(api_key)
    if not key:
        return None

    # Clean the show name: strip year, quality tokens, etc.
    clean = re.sub(r'\b(?:19|20)\d{2}\b', '', show_name).strip()
    clean = re.sub(r'\s+', ' ', clean).strip()
    if not clean:
        clean = show_name

    data = _tmdb_get('search/tv', key, {'query': clean})
    if not data or not data.get('results'):
        return None
    return data['results'][0].get('id')


def get_season_episode_titles(
    show_name: str,
    season_number: int,
    api_key: str = '',
) -> Dict[int, str]:
    """Get episode titles for a TV season from TMDB.

    Args:
        show_name: TV show name (e.g. ``Breaking Bad``).
        season_number: Season number (1-indexed).
        api_key: TMDB API key (optional, falls back to config).

    Returns:
        Dict mapping episode_number -> title, e.g. ``{1: "Pilot", 2: "Cat's in the Bag"}``.
        Empty dict if lookup fails or no key available.
    """
    key = _resolve_key(api_key)
    if not key:
        return {}

    # Check disk cache
    cache_key = f'{show_name.lower().strip()} {season_number}'
    episode_cache = _load_episode_cache()
    cached = episode_cache.get(cache_key)
    if cached is not None:
        return cached

    # Get TV show ID
    show_id = get_tv_show_id(show_name, key)
    if not show_id:
        return {}

    # Get season details
    data = _tmdb_get(f'tv/{show_id}/season/{season_number}', key)
    if not data or not data.get('episodes'):
        return {}

    # Build result dict
    result: Dict[int, str] = {}
    for ep in data['episodes']:
        ep_num = ep.get('episode_number')
        ep_name = ep.get('name', '').strip()
        if ep_num and ep_name:
            result[ep_num] = ep_name

    # Save to disk cache
    if result:
        episode_cache[cache_key] = result
        _save_episode_cache(episode_cache)

    return result
