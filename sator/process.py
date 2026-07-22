#!/usr/bin/env python3
"""Internal process-query orchestration."""

import sys
import time
from dataclasses import asdict
from typing import Optional
from sator.indexer import search_all, TorrentResult
from sator.filter import filter_result_json
from sator.qb_client import _qb_add_simple
from sator.size import bytes_to_human

# Human-readable tracker names
TRACKER_LABELS = {
    'nyaa': 'Nyaa',
    'tpb': 'PirateBay',
    'limetorrents': 'LimeTorrents',
}

# Fixed order for compact status chars
TRACKER_ORDER = ['nyaa', 'tpb', 'limetorrents']

def _make_progress_cb(query_num: int, total_queries: int, query: str,
                       verbose: bool, status_chars: list,
                       tracker_results: dict, tracker_errors: dict):
    """Create a progress callback for search_all()."""
    tracker_count = len(TRACKER_ORDER)
    
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
                           qb_url: str = 'http://localhost:8090',
                           category: str = '', tags: str = '',
                           output_file: str = '',
                           verbose: bool = False,
                           show_tracker_titles: bool = False,
                           query_num: int = 1,
                           total_queries: int = 1,
                           start_time: float = 0.0,
                           trackers: list = None) -> dict:
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
    results = search_all(query, trackers=trackers, progress_cb=progress_cb)
    
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
    for r in results:
        d = asdict(r)
        d['quality'] = asdict(r.quality)
        d['languages'] = r.languages
        filtered = filter_result_json(d, filters)
        if not filtered:
            all_filtered += 1
            # Track per-tracker filtered count
            if r.source in filtered_out:
                filtered_out[r.source] += 1
            continue
        
        out['found'] += 1
        out['found_any'] = True
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
        out['display_lines'].append(f"    {qlabel} ({size_h}) [{source}] \U0001f9f2:{seeders}")
        if magnet:
            out['display_lines'].append(f"    {magnet}")
        out['torrents'].append({
            'title': title,
            'size_h': size_h,
            'source': source,
            'seeders': seeders,
            'quality_label': qlabel,
            'magnet': magnet if magnet else '',
        })
        
        if qb_add and magnet:
            _qb_add_simple(magnet, qb_url, category, tags)
            out['added'] += 1
    
    out['filtered_count'] = all_filtered
    
    # Determine best result (top by seeders among filtered)
    best_src = None
    if out['found'] > 0:
        # Find source with most seeders in the first result
        for r in results:
            d = asdict(r)
            d['quality'] = asdict(r.quality)
            d['languages'] = r.languages
            filtered = filter_result_json(d, filters)
            if filtered:
                out['best_indices'].append(r.source if r.source else '')
                best_src = r.source
                break
    
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
    
    if output_file and out['magnets']:
        try:
            with open(output_file, 'w') as f:
                for m in out['magnets']:
                    f.write(m + '\n')
        except OSError as e:
            print(f"Error writing {output_file}: {e}", file=sys.stderr)
    
    return out
