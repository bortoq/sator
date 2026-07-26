#!/usr/bin/env python3
"""Internal process-query orchestration."""

import sys
from dataclasses import asdict
from sator.indexer import search_all, _enrich_from_detail
from sator.filter import filter_result_json
from sator.qb_client import _qb_add_simple
from sator.size import bytes_to_human
from sator import settings
from sator.tmdb import enrich_query
from sator.quality import parse_quality
from sator.language import parse_languages
from sator.exclude import is_excluded


# Scoring for best-mode selection
# settings.TRUSTED_GROUPS moved to sator/settings.py

# _SOURCE_SCORES moved to sator/settings.py

def _score_result(t: dict, preferred_res: int = settings.PREFERRED_RES) -> float:
    '''Score a filtered torrent result for best-mode selection.'''
    score = 0.0

    # 1. Download efficiency: more seeders per GB = faster download
    #    Cap seeders at 100 (user channel is the bottleneck beyond that)
    #    Floor size at 0.1 GB to avoid division by zero
    seeders = min(t.get('seeders', 0), settings.SEEDER_CAP)
    size_gb = max(t.get('size_bytes', 0) / (1024 ** 3), settings.SIZE_FLOOR_GB)
    score += seeders / size_gb * settings.EFFICIENCY_WEIGHT

    # 2. Source quality
    src = t.get('_quality', {}).get('source', '')
    score += settings.SOURCE_SCORES.get(src, 0)

    # 3. Resolution match
    res = t.get('_quality', {}).get('resolution', 0)
    if res == preferred_res:
        score += settings.EXACT_RES_BONUS
    elif res > 0 and abs(res - preferred_res) <= settings.CLOSE_RES_THRESHOLD:
        score += settings.CLOSE_RES_BONUS

    # 4. Reasonable size (not too small, not too large)
    size_gb = t.get('size_bytes', 0) / (1024**3)
    if settings.REASONABLE_SIZE_MIN_GB <= size_gb <= settings.REASONABLE_SIZE_MAX_GB:
        score += settings.REASONABLE_SIZE_BONUS

    # 5. Trusted release groups
    title = t.get('title', '')
    if any(g in title for g in settings.TRUSTED_GROUPS):
        score += 20

    return score



# Human-readable tracker names
TRACKER_LABELS = {
    'nyaa': 'Nyaa',
    'tpb': 'PirateBay',
    'limetorrents': 'LimeTorrents',
    'yts': 'YTS',
    'solidtorrents': 'SolidTorrents',
    'eztv': 'EZTV',
    'tgx': 'TorrentGalaxy',
    'yourbittorrent': 'YourBittorrent',
    'torrentfunk': 'TorrentFunk',
    'magnetz': 'Magnetz',
    'glotorrents': 'GloTorrents',
}

# Fixed order for compact status chars
TRACKER_ORDER = ['nyaa', 'tpb', 'yts', 'solidtorrents', 'eztv', 'tgx', 'limetorrents', 'yourbittorrent', 'torrentfunk', 'magnetz', 'glotorrents']

def _make_progress_cb(query_num: int, total_queries: int, query: str,
                       verbose: bool, status_chars: list,
                       tracker_results: dict, tracker_errors: dict):
    """Create a progress callback for search_all()."""
    
    def _print_compact():
        """Print/refresh one-line compact progress."""
        chars = ''.join(status_chars)
        qdisp = query[:50] + '...' if len(query) > 50 else query
        line = f'[{query_num}/{total_queries}] {qdisp}  {chars}'
        print(f'\r{line}\033[K', end='', file=sys.stderr, flush=True)
    
    def cb(name: str, status: str, count: int, error_msg: str = ''):
        nonlocal status_chars
        
        idx = TRACKER_ORDER.index(name) if name in TRACKER_ORDER else -1
        
        if verbose:
            # Verbose mode: print each tracker event on its own line
            label = TRACKER_LABELS.get(name, name)
            if status == 'requesting':
                print(f'  {label} ...', file=sys.stderr, flush=True)
            elif status == 'ok':
                tracker_results[name] = count
                print(f'  {label} \u2713 {count} results', file=sys.stderr, flush=True)
            elif status == 'error':
                tracker_errors[name] = error_msg
                print(f'  {label} \u2717 {error_msg}', file=sys.stderr, flush=True)
        else:
            # Compact mode: update status char and refresh line
            ch = '?'
            if status == 'requesting':
                ch = '?'
            elif status == 'ok':
                ch = 'o' if count > 0 else '.'
                tracker_results[name] = count
            elif status == 'error':
                ch = '!'
                tracker_errors[name] = error_msg
            if idx >= 0:
                status_chars[idx] = ch
            _print_compact()
    
    return cb


def _process_query_internal(query: str, filters: dict, qb_add: bool = False,
                           qb_url: str = settings.DEFAULT_QB_URL,
                           category: str = '', tags: str = '',
                           output_file: str = '',
                           verbose: bool = False,
                           show_tracker_titles: bool = False,
                           query_num: int = 1,
                           total_queries: int = 1,
                           trackers: list = None,
                           best_mode: bool = True) -> dict:
    """Internal: search all trackers, filter, optionally add to qBittorrent.
    Returns dict with {found, added, total_size, magnets, display_lines, found_any,
                        filtered_count, best_indices}."""
    
    # Track per-tracker state for progress
    status_chars = ['?'] * len(TRACKER_ORDER)
    tracker_results = {}
    tracker_errors = {}
    
    progress_cb = _make_progress_cb(query_num, total_queries, query,
                                     verbose, status_chars,
                                     tracker_results, tracker_errors)
    
    if verbose:
        print(f'[{query_num}/{total_queries}] {query}', file=sys.stderr)
    
    # Show tracker titles once if requested
    if show_tracker_titles and query_num == 1:
        for name in TRACKER_ORDER:
            print(TRACKER_LABELS.get(name, name), file=sys.stderr)
    
    # Search with progress callback
    enriched = enrich_query(query, api_key=filters.get('tmdb_key', '')) if filters.get('tmdb_enrich', True) else query
    results = search_all(enriched, trackers=trackers, progress_cb=progress_cb)
    
    out = {
        'found': 0,
        'added': 0,
        'total_size': 0,
        'magnets': [],
        'torrents': [],
        'display_lines': [],
        'found_any': False,
        'filtered_count': 0,
        'best_indices': [],
    }
    
    # Group results by source tracker
    grouped: dict = {}
    for r in results:
        src = r.source
        if src not in grouped:
            grouped[src] = []
        grouped[src].append(r)
    
    # Track raw counts per tracker (before filtering)
    raw_counts = {}
    filtered_out = {}
    for name in TRACKER_ORDER:
        if name in grouped:
            raw_counts[name] = len(grouped[name])
        else:
            raw_counts[name] = 0
        filtered_out[name] = 0
    
    # Process and filter results
    all_filtered = 0
    best_src = None
    _fallback_candidates = []
    # Cache for detail page enrichment (by info_url)
    _enrich_cache = {}
    
    def _try_enrich(r, d):
        '''Fetch detail page once per URL, inject subs/languages into title.'''
        if not r.info_url:
            return d
        # Check cache
        if r.info_url not in _enrich_cache:
            _enrich_cache[r.info_url] = _enrich_from_detail(r)
        enriched = _enrich_cache[r.info_url]
        if not enriched:
            return d
        d2 = dict(d)
        if enriched.get('languages') and not d2.get('languages'):
            d2['languages'] = enriched['languages']
        if enriched.get('subs'):
            d2['_enriched_subs'] = enriched['subs']
        return d2
    
    for r in results:
        d = asdict(r)
        d['quality'] = asdict(r.quality)
        d['languages'] = r.languages
        
        # First filter pass
        filtered = filter_result_json(d, filters)
        
        # If filtered but has detail URL, try enrichment and re-filter
        if not filtered and r.info_url:
            d2 = _try_enrich(r, d)
            if d2 is not d:  # enrichment added something
                filtered = filter_result_json(d2, filters)
                if filtered:
                    d = d2  # use enriched version
        
        if not filtered:
            all_filtered += 1
            # Track per-tracker filtered count
            if r.source in filtered_out:
                filtered_out[r.source] += 1
            # Collect fallback candidate (for both best-mode and -m)
            excludes = filters.get('excludes', [])
            if not excludes or not is_excluded(d.get('title', ''), excludes):
                d['_quality'] = asdict(parse_quality(d.get('title', '')))
                d['_languages'] = parse_languages(d.get('title', ''))
                _fallback_candidates.append(d)
            # In verbose mode, show filtered-out items too
            if verbose:
                size_h_raw = bytes_to_human(d.get('size_bytes', 0))
                seed_raw = d.get('seeders', 0)
                # Short size: "151G" not "151.0 GiB"
                sz = '0'
                if size_h_raw:
                    parts = size_h_raw.split()
                    num = parts[0].split('.')[0] if '.' in parts[0] else parts[0]
                    unit = parts[1][0] if len(parts) > 1 else 'B'
                    sz = f'{num}{unit}'
                print(f'  \u2717 {sz} | {d.get("title", "")} | seeds:{seed_raw}', file=sys.stderr, flush=True)
            continue
        
        out['found'] += 1
        out['found_any'] = True
        # Capture best source on first match
        if best_src is None and r.source:
            best_src = r.source
            out['best_indices'].append(r.source)
        out['total_size'] += filtered.get('size_bytes', 0)
        magnet = filtered.get('magnet', '')
        if magnet:
            out['magnets'].append(magnet)
        title = filtered.get('title', '')
        size_bytes = filtered.get('size_bytes', 0)
        seeders = filtered.get('seeders', 0)
        source = filtered.get('source', '')
        q = filtered.get('_quality', {})
        qlabel = q.get('quality_label', '')
        size_h = bytes_to_human(size_bytes)
        
        out['display_lines'].append(f"  \u2713 {title}")
        out['display_lines'].append(f"    {qlabel} ({size_h}) [{source}] seeds:{seeders}")
        # Only show magnet on terminal when no -o (to avoid clutter)
        if magnet and not output_file:
            out['display_lines'].append(f"    {magnet}")
        out['torrents'].append({
            'title': title,
            'size_h': size_h,
            'size_bytes': size_bytes,
            'source': source,
            'seeders': seeders,
            'quality_label': qlabel,
            'magnet': magnet if magnet else '',
            '_quality': q,
        })
        
        # qb_add is handled below (best-mode or fallback)
    
    out['filtered_count'] = all_filtered
    
    # ── Not best-mode: sort all results by score ──
    if not best_mode and out['torrents']:
        scored = [(t, _score_result(t)) for t in out['torrents']]
        scored.sort(key=lambda x: (x[0].get('seeders', 0) == 0, -x[1]))
        out['torrents'] = [t for t, _ in scored]
        out['magnets'] = [t.get('magnet', '') for t in out['torrents'] if t.get('magnet')]
        out['display_lines'] = []
        for t in out['torrents']:
            title = t.get('title', '')
            size_h = t.get('size_h', '')
            qlabel = t.get('quality_label', '')
            seeders = t.get('seeders', 0)
            out['display_lines'].append(f"  \u2713 {title}")
            out['display_lines'].append(f"    {qlabel} ({size_h}) seeds:{seeders}")
            if t.get('magnet') and not output_file:
                out['display_lines'].append(f"    {t['magnet']}")
    
    # --- Best mode: select single best result ---
    if best_mode and out['torrents']:
        scored = [(_score_result(t), t) for t in out['torrents']]
        scored.sort(key=lambda x: (x[1].get('seeders', 0) == 0, -x[0]))
        best_score, best = scored[0]
        
        # Replace all torrents with just the best one
        out['torrents'] = [best]
        out['magnets'] = [best.get('magnet', '')] if best.get('magnet') else []
        out['found'] = 1
        out['total_size'] = best.get('size_bytes', 0)
        
        # Update display lines
        title = best.get('title', '')
        size_h = best.get('size_h', '')
        qlabel = best.get('quality_label', '')
        seeders = best.get('seeders', 0)
        out['display_lines'] = [
            f"  \u2713 {title}",
            f"    {qlabel} ({size_h}) [best, score: {best_score:.0f}] seeds:{seeders}",
        ]
        # Only show magnet on terminal when no -o
        if best.get('magnet') and not output_file:
            out['display_lines'].append(f"    {best['magnet']}")
        
        # Add best torrent to qB
        out['added'] = 0
        if qb_add and best.get('magnet'):
            _qb_add_simple(best['magnet'], qb_url, category, tags)
            out['added'] = 1
    
    # ── NOT best-mode: add all filtered to qB ──
    if not best_mode and qb_add:
        for t in out['torrents']:
            if t.get('magnet'):
                _qb_add_simple(t['magnet'], qb_url, category, tags)
                out['added'] += 1
    
        
    # ── Fallback: no results passed filters → return filtered-out items ──
    # best_mode: pick single best;  not best_mode: return all (‑m behaviour)
    if not out['torrents'] and _fallback_candidates:
        # Score all candidates
        scored = [(t, _score_result(t)) for t in _fallback_candidates]
        scored.sort(key=lambda x: (x[0].get('seeders', 0) == 0, -x[1]))
        
        if best_mode:
            # Single best result
            best, raw_score = scored[0]
            size_bytes = best.get('size_bytes', 0)
            seeders = best.get('seeders', 0)
            source = best.get('source', '')
            q = best.get('_quality', {})
            qlabel = q.get('quality_label', 'Unknown')
            size_h = bytes_to_human(size_bytes)
            title = best.get('title', '')
            magnet = best.get('magnet', '')
            
            out['torrents'] = [{
                'title': title, 'size_h': size_h, 'size_bytes': size_bytes,
                'source': source, 'seeders': seeders,
                'quality_label': qlabel, 'magnet': magnet if magnet else '',
                '_fallback': True,
            }]
            out['found'] = 1
            out['found_any'] = True
            out['magnets'] = [magnet] if magnet else []
            out['total_size'] = size_bytes
            out['display_lines'] = [
                f"  \u26a0 {title} (fallback)",
                f"    {qlabel} ({size_h}) [{source}] seeds:{seeders}",
            ]
            if magnet and not output_file:
                out['display_lines'].append(f"    {magnet}")
            
            out['added'] = 0
            if qb_add and magnet:
                _qb_add_simple(magnet, qb_url, category, tags)
                out['added'] = 1
            
            if source:
                best_src = source
                out['best_indices'].append(source)
        else:
            # All results mode (‑m): return all fallback candidates
            fb_list = []
            out['display_lines'] = [f"  \u26a0 {len(scored)} fallback results (filters did not match)"]
            out['found_any'] = True
            out['magnets'] = []
            out['total_size'] = 0
            
            for t, raw_score in scored:
                size_bytes = t.get('size_bytes', 0)
                seeders = t.get('seeders', 0)
                source = t.get('source', '')
                q = t.get('_quality', {})
                qlabel = q.get('quality_label', 'Unknown')
                size_h = bytes_to_human(size_bytes)
                title = t.get('title', '')
                magnet = t.get('magnet', '')
                
                fb_list.append({
                    'title': title, 'size_h': size_h, 'size_bytes': size_bytes,
                    'source': source, 'seeders': seeders,
                    'quality_label': qlabel, 'magnet': magnet if magnet else '',
                    '_fallback': True,
                })
                if magnet:
                    out['magnets'].append(magnet)
                out['total_size'] += size_bytes
                out['display_lines'].append(f"  \u26a0 {title}")
                out['display_lines'].append(f"    {qlabel} ({size_h}) [{source}] seeds:{seeders}")
            
            out['torrents'] = fb_list
            out['found'] = len(fb_list)
            
            out['added'] = 0
            if qb_add:
                for t in fb_list:
                    if t.get('magnet'):
                        _qb_add_simple(t['magnet'], qb_url, category, tags)
                        out['added'] += 1
    
    # best_src is captured during the filter loop
    # It remains set for the status chars below
    
    # Update status chars after filtering
    for i, name in enumerate(TRACKER_ORDER):
        current = status_chars[i]
        if current == '!':
            continue  # keep error marker
        raw = raw_counts.get(name, 0)
        filt = filtered_out.get(name, 0)
        passed = raw - filt
        if passed > 0:
            if name == best_src:
                status_chars[i] = 'O'
            else:
                status_chars[i] = 'o'
        elif raw > 0:
            status_chars[i] = ':'  # all filtered
        elif current == '?':
            # Tracker had no results but no error either
            status_chars[i] = ':'
    
    # Print final line
    if not verbose:
        qdisp = query[:50] + '...' if len(query) > 50 else query
        chars = ''.join(status_chars)
        print(f'\r[{query_num}/{total_queries}] {qdisp}  {chars}\033[K', file=sys.stderr, flush=True)
    else:
        # Verbose footer: summary line
        total_raw = len(results)
        total_found = out['found']
        total_filtered = out['filtered_count']
        print(f'  \u2192 {total_found} matches after filters  ({total_raw} total, {total_filtered} removed)',
              file=sys.stderr)
    
    
    return out
