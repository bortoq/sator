#!/usr/bin/env python3
"""Query building: expand -sn specs into pack queries."""

import os
import re
import sys
from sator import settings
from sator.series import expand_series_queries
from sator.wikidata import get_season_episode_count, get_series_season_count_wikidata
from sator.tmdb import get_series_season_count as tmdb_get_series_season_count


def _build_queries(parsed) -> tuple:
    """Build and expand search queries from CLI args.

    Handles: reading from file or string, series enrichment (-sn),
    episode-level expansion via Wikidata.

    Returns (queries, series_meta, series_plan, cache_dir).
    """
    queries = []
        
    for s in parsed.search_strings:
        if os.path.isfile(s):
            try:
                with open(s) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        year = ''
                        ym = re.search(r'([12]\d{3})', line)
                        if ym:
                            year = ym.group(1)
                        cleaned = ''
                        if re.match(r'^\d+\.', line):
                            cleaned = re.sub(r'^\d+\.\s*\*\*', '', line)
                            cleaned = re.sub(r'\*\*.*', '', cleaned)
                            cleaned = re.sub(r'\s*—\s*$', '', cleaned).strip()
                            cleaned = re.sub(r'\s*/.*', '', cleaned).strip()
                        if not cleaned:
                            cleaned = re.sub(r'^[-*]*\s*', '', line).strip()
                        if not cleaned:
                            continue
                        if year:
                            cleaned = f'{cleaned} {year}'
                        queries.append(cleaned)
            except OSError as e:
                print(f'\u2716 Error reading {s}: {e}', file=sys.stderr)
        else:
            queries.append(s)
    
    # ── Series enrichment ─────────────────────────────────────────────────
    if parsed.season_number:
        expanded = []
        for q in queries:
            expanded.extend(expand_series_queries(q, parsed.season_number))
        queries = expanded
    
    # ── Episode-level expansion ────────────────────────────────────────────
    cache_dir = os.path.expanduser(settings.CACHE_DIR)
    wiki_cache = os.path.join(cache_dir, 'seriess.json')
    os.makedirs(cache_dir, exist_ok=True)
    
    _series_meta = {}
    _series_plan = {}
    _series_orig = list(queries)
    
    if parsed.season_number and not getattr(parsed, 'no_episode_expansion', False):
        for spec in parsed.season_number:
            if not spec:
                # ── bare -sn: expand to ALL seasons ──
                for orig_q in _series_orig:
                    clean_q = re.sub(r'\s+complete seasons$', '', orig_q, flags=re.IGNORECASE).strip()
                    if not clean_q:
                        continue
                    print(f'  \u2022 [{clean_q}] looking up season count...', file=sys.stderr, end='', flush=True)
                    # Try TMDB first, fall back to Wikidata
                    season_count = tmdb_get_series_season_count(clean_q, getattr(parsed, 'tmdb_key', ''))
                    if not season_count:
                        season_count = get_series_season_count_wikidata(clean_q, wiki_cache)
                    print(f' {season_count}', file=sys.stderr, flush=True)
                    if not season_count:
                        if parsed.verbose:
                            print(f'  \u26a0 [{clean_q}] season count not found, using pack only',
                                  file=sys.stderr)
                        continue
                    # Build pack query for each season (episodes added later for weak packs)
                    for sn in range(1, season_count + 1):
                        print(f'  \u2022 [{clean_q}] episode count for S{sn:02d}...', file=sys.stderr, end='', flush=True)
                        ep_count = get_season_episode_count(clean_q, sn, wiki_cache)
                        print(f' {ep_count}', file=sys.stderr, flush=True)
                        pack_q = f"{clean_q} S{sn:02d}"
                        if pack_q not in queries:
                            queries.append(pack_q)
                        _series_meta[pack_q] = {'type': 'pack', 'spec_idx': sn}
                        _series_plan[sn] = {
                            'pack_q': pack_q, 'clean_q': clean_q,
                            'ep_count': ep_count or 0, 'spec_idx': sn,
                        }
            elif len(spec) == 1:
                season_num = int(spec[0])
                for orig_q in _series_orig:
                    clean_q = re.sub(r'\s+S\d{2}(E\d{2})?$', '', orig_q).strip()
                    if not clean_q or clean_q == orig_q:
                        continue
                    print(f'  \u2022 [{clean_q}] episode count for S{season_num:02d}...', file=sys.stderr, end='', flush=True)
                    ep_count = get_season_episode_count(clean_q, season_num, wiki_cache)
                    print(f' {ep_count}', file=sys.stderr, flush=True)
                    if not ep_count:
                        if parsed.verbose:
                            name = clean_q or orig_q
                            print(f'  \u26a0 [{name} S{season_num:02d}] '
                                  f'episode count not found on Wikidata, using pack only',
                                  file=sys.stderr)
                        continue
                    pack_q = f"{clean_q} S{season_num:02d}"
                    if pack_q not in queries:
                        continue
                    _series_meta[pack_q] = {'type': 'pack', 'spec_idx': season_num}
                    _series_plan[season_num] = {
                        'pack_q': pack_q, 'clean_q': clean_q,
                        'ep_count': ep_count, 'spec_idx': season_num,
                    }
    
    # ── Cleanup: remove "complete seasons" queries if expanded to seasons ──
    if parsed.season_number and _series_plan:
        _remove = []
        for q in queries:
            if re.search(r'complete seasons$', q, re.IGNORECASE):
                # Check if this query was successfully expanded (at least one season in plan)
                clean_base = re.sub(r'\s+complete seasons$', '', q, flags=re.IGNORECASE).strip()
                if any(plan.get('pack_q', '').startswith(clean_base + ' S') for plan in _series_plan.values()):
                    _remove.append(q)
        for q in _remove:
            queries.remove(q)
    
    if not queries:
        if parsed.tracker_titles:
            from sator.process import TRACKER_LABELS
            for label in TRACKER_LABELS.values():
                print(label, file=sys.stderr)
            sys.exit(0)
        print('\u2716 No search queries provided', file=sys.stderr)
        sys.exit(1)
    
    return queries, _series_meta, _series_plan, cache_dir
