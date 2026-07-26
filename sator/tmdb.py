#!/usr/bin/env python3
"""TMDB enrichment for search queries.

Best-effort: if no API key is available, all functions are no-ops.
"""

import json
import os
import re
import urllib.parse
import urllib.request
from sator import settings

# Default config path
CONFIG_PATH = os.path.expanduser(settings.CONFIG_PATH)

# Cache for TMDB queries (in-memory, per session)
_cache: dict = {}

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

def enrich_query(query: str, api_key: str = '') -> str:
    """Enrich a search query with TMDB data.
    
    If the query looks like a movie title (no year), try to fetch the
    release year from TMDB. Returns enriched query (with year) or
    original query if anything fails.
    
    api_key overrides the config file key.
    """
    key = api_key or _load_tmdb_key()
    if not key:
        return query
    
    # Skip queries that already have a year
    if re.search(settings.TMDB_YEAR_PATTERN, query):
        return query
    
    # Check cache
    if query in _cache:
        return _cache[query]
    
    try:
        url = f'https://api.themoviedb.org/3/search/multi?api_key={key}&query={urllib.parse.quote(query)}'
        req = urllib.request.Request(url, headers={'User-Agent': settings.UA_TMDB})
        with urllib.request.urlopen(req, timeout=settings.TIMEOUT_TMDB) as resp:
            data = json.loads(resp.read().decode())

        if data.get('results'):
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
