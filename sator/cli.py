#!/usr/bin/env python3
"""Command-line interface for sator."""

import argparse
import json
import os
import re
import sys
import time
from typing import List, Optional
from dataclasses import asdict
from sator.iso_langs import iso_lookup, iso_name
from sator.language import parse_languages
from sator.quality import parse_quality
from sator.title import parse_title
from sator.size import parse_size, bytes_to_human
from sator.wikidata import get_wikidata_original_lang, get_season_episode_count, get_series_season_count_wikidata
from sator.tmdb import get_series_season_count as tmdb_get_series_season_count
from sator.filter import filter_result_json
from sator.indexer import search_all, INDEXERS
from sator.process import _process_query_internal, TRACKER_LABELS
from sator.qb_client import _qb_add_simple, QBClient, QBConfig
from sator import settings
from sator.series import expand_series_queries, pick_series_best, make_series_tag
from sator.normalizer import compute_new_name, write_sidecar, _parse_season_episode
from sator.cli_utils import _extract_info_hash, _find_torrent_by_hash, _parse_sator_file, _normalize_torrents

def cmd_parse_languages(args: List[str]):
    """Usage: parse-languages <title>"""
    if len(args) < 1:
        print(json.dumps({"error": "Missing title argument"}))
        sys.exit(1)
    langs = parse_languages(' '.join(args))
    print(json.dumps({"languages": langs, "names": [iso_name(l) for l in langs]}))


def cmd_parse_quality(args: List[str]):
    """Usage: parse-quality <title>"""
    if len(args) < 1:
        print(json.dumps({"error": "Missing title argument"}))
        sys.exit(1)
    qi = parse_quality(' '.join(args))
    print(json.dumps(asdict(qi)))


def cmd_parse_title(args: List[str]):
    """Usage: parse-title <title>"""
    if len(args) < 1:
        print(json.dumps({"error": "Missing title argument"}))
        sys.exit(1)
    pt = parse_title(' '.join(args))
    d = asdict(pt)
    d['quality'] = asdict(pt.quality)
    d['languages'] = pt.languages
    print(json.dumps(d))


def cmd_iso_lookup(args: List[str]):
    """Usage: iso-lookup <code_or_name>"""
    if len(args) < 1:
        print(json.dumps({"error": "Missing code or name argument"}))
        sys.exit(1)
    entry = iso_lookup(' '.join(args))
    if entry:
        print(json.dumps(entry))
    else:
        print(json.dumps({"error": f"Language not found: {' '.join(args)}"}))


def cmd_qb_add(args: List[str]):
    """Usage: qb-add <magnet> [--category <cat>] [--tags <tags>] [--ratio <ratio>] [--seed-time <minutes>]"""
    import argparse as ap
    parser = ap.ArgumentParser()
    parser.add_argument('magnet')
    parser.add_argument('--category', default='')
    parser.add_argument('--tags', nargs='+', default=None)
    parser.add_argument('--ratio', type=float, default=-1)
    parser.add_argument('--seed-time', type=int, default=-1)
    parser.add_argument('--url', default=settings.DEFAULT_QB_URL)
    parser.add_argument('--username', default='')
    parser.add_argument('--password', default='')
    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        sys.exit(e.code)

    tags_str = ' '.join(parsed.tags) if parsed.tags else ''
    config = QBConfig(url=parsed.url, username=parsed.username, password=parsed.password)
    client = QBClient(config)
    result = client.add_torrent(parsed.magnet, parsed.category, tags_str,
                                parsed.ratio, parsed.seed_time)
    print(json.dumps(result))


def cmd_search(args: List[str]):
    """Usage: search <tracker> <query>"""
    if len(args) < 2:
        print(json.dumps({"error": "Usage: search <tracker> <query>"}))
        sys.exit(1)
    tracker = args[0]
    query = ' '.join(args[1:])
    if tracker == 'all':
        results = search_all(query)
    else:
        indexer = INDEXERS.get(tracker)
        if not indexer:
            print(json.dumps({"error": f"Unknown tracker: {tracker}. Available: {list(INDEXERS.keys())}"}))
            sys.exit(1)
        results = indexer.search(query)

    out = []
    for r in results:
        d = asdict(r)
        d['quality'] = asdict(r.quality)
        d['languages'] = r.languages
        out.append(d)
    print(json.dumps(out))


def cmd_wikilang(args: List[str]):
    """Usage: wikilang <query> [--cache <path>]"""
    query = ' '.join(args)
    cache_file = ""
    for i, a in enumerate(args):
        if a == '--cache' and i + 1 < len(args):
            cache_file = args[i + 1]
            query = ' '.join(args[:i] + args[i+2:])
            break
    if not cache_file:
        for i, a in enumerate(args):
            if a == '--cache':
                break
        else:
            query = ' '.join(args)

    iso = get_wikidata_original_lang(query, cache_file)
    if iso:
        print(json.dumps({"iso": iso, "name": iso_name(iso)}))
    else:
        print(json.dumps({"iso": "", "name": ""}))


def cmd_size(args: List[str]):
    """Usage: size <bytes|human> [--to-bytes|--to-human]"""
    if len(args) < 1:
        print(json.dumps({"error": "Missing size argument"}))
        sys.exit(1)
    val = args[0]
    if '--to-bytes' in args or (val and not val.isdigit()):
        if val.isdigit():
            result = int(val)
        else:
            result = parse_size(val)
        if result is not None:
            print(json.dumps({"bytes": result, "human": bytes_to_human(result)}))
        else:
            print(json.dumps({"error": f"Invalid size: {val}"}))
    else:
        try:
            b = int(val)
            print(json.dumps({"bytes": b, "human": bytes_to_human(b)}))
        except ValueError:
            print(json.dumps({"error": f"Invalid number: {val}"}))


def cmd_filter(args: List[str]):
    """Usage: filter <json-result|--> --rl <res> --rb <res> --zl <bytes> --zb <bytes> --lang <code> [--lang <code>] --subs <code>"""
    import argparse as ap
    parser = ap.ArgumentParser()
    parser.add_argument('json_input', nargs='?', default='-')
    parser.add_argument('--rl', type=int, default=None)
    parser.add_argument('--rb', type=int, default=None)
    parser.add_argument('--zl', type=int, default=None)
    parser.add_argument('--zb', type=int, default=None)
    parser.add_argument('--lang', action='append', default=None)
    parser.add_argument('--subs', action='append', default=None)
    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        sys.exit(e.code)

    json_str = parsed.json_input
    if json_str == '-' or json_str is None:
        json_str = sys.stdin.read().strip()

    if not json_str:
        print(json.dumps({"error": "Missing JSON result"}))
        sys.exit(1)

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    filters = {
        'rl': parsed.rl,
        'rb': parsed.rb,
        'zl': parsed.zl,
        'zb': parsed.zb,
        'lang': parsed.lang,
        'subs': parsed.subs,
    }
    filtered = filter_result_json(result, filters)
    if filtered:
        print(json.dumps(filtered))
    else:
        print(json.dumps(None))


def cmd_search_all(args: List[str]):
    """Usage: search-all <query>"""
    if len(args) < 1:
        print(json.dumps({"error": "Missing query argument"}))
        sys.exit(1)
    query = ' '.join(args)
    results = search_all(query)
    out = []
    for r in results:
        d = asdict(r)
        d['quality'] = asdict(r.quality)
        d['languages'] = r.languages
        out.append(d)
    print(json.dumps(out))


def cmd_process_query(args: List[str]):
    """CLI wrapper for _process_query_internal."""
    import argparse as _ap
    parser = _ap.ArgumentParser()
    parser.add_argument('query', nargs='+')
    parser.add_argument('--rl', type=int, default=None)
    parser.add_argument('--rb', type=int, default=None)
    parser.add_argument('--zl', type=int, default=None)
    parser.add_argument('--zb', type=int, default=None)
    parser.add_argument('--lang', action='append', default=[])
    parser.add_argument('--subs', nargs='?', const='__original__', default=[], action='append')
    parser.add_argument('--qb-add', action='store_true', default=False)
    parser.add_argument('--qb-url', default=settings.DEFAULT_QB_URL)
    parser.add_argument('--category', default='')
    parser.add_argument('--tags', nargs='+', default=None)
    parser.add_argument('-o', '--output', default='')
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    parser.add_argument('-tt', '--tracker-titles', action='store_true', default=False)
    parser.add_argument('-m', '--more', action='store_true', default=False)
    parser.add_argument('-e', '--exclude', type=str, default='')
    parser.add_argument('-sn', '--season-number', nargs='*', default=None, action='append')
    parser.add_argument('--no-enrich', action='store_false', dest='enrich', default=True)
    parser.add_argument('--tmdb-key', type=str, default='')
    args = ['--help' if a == '-help' else a for a in args]
    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        sys.exit(e.code)

    tags_str = ' '.join(parsed.tags) if parsed.tags else ''
    query = ' '.join(parsed.query)
    if parsed.season_number:
        queries = expand_series_queries(query, parsed.season_number)
    else:
        queries = [query]
    
    filters = {
        'rl': parsed.rl,
        'rb': parsed.rb,
        'zl': parsed.zl,
        'zb': parsed.zb,
        'lang': parsed.lang,
        'subs': parsed.subs,
    }
    if parsed.exclude:
        filters['excludes'] = [x.strip() for x in parsed.exclude.split(',') if x.strip()]
    if parsed.tmdb_key:
        filters['tmdb_key'] = parsed.tmdb_key
    filters['tmdb_enrich'] = parsed.enrich
    
    results_list = []
    for q in queries:
        out = _process_query_internal(q, filters, parsed.qb_add, parsed.qb_url,
                                      parsed.category, tags_str, parsed.output,
                                      verbose=parsed.verbose,
                                      show_tracker_titles=parsed.tracker_titles,
                                      best_mode=not parsed.more)
        results_list.append(out)
    merged = {
        'found': sum(r.get('found', 0) for r in results_list),
        'added': sum(r.get('added', 0) for r in results_list),
        'total_size': sum(r.get('total_size', 0) for r in results_list),
        'magnets': [],
        'torrents': [],
        'display_lines': [],
        'found_any': any(r.get('found_any', False) for r in results_list),
        'filtered_count': sum(r.get('filtered_count', 0) for r in results_list),
        'best_indices': [],
    }
    for r in results_list:
        merged['magnets'].extend(r.get('magnets', []))
        merged['torrents'].extend(r.get('torrents', []))
        merged['display_lines'].extend(r.get('display_lines', []))
    print(json.dumps(merged))


def apply_defaults(args: argparse.Namespace) -> argparse.Namespace:
    """Fill in built-in defaults for args that were not explicitly provided."""
    if args.rl is None:
        args.rl = settings.DEFAULT_RL
    if args.rb is None:
        args.rb = settings.DEFAULT_RB
    if args.zl is None:
        args.zl = settings.DEFAULT_ZL
    if args.zb is None:
        args.zb = settings.DEFAULT_ZB
    if args.lang is None:
        args.lang = list(settings.DEFAULT_LANG)
    if args.subs is None:
        args.subs = list(settings.DEFAULT_SUBS)
    # trackers: always use DEFAULT_TRACKERS (removed -T flag)
    return args


# ── Main run command ─────────────────────────────────────────────────────────


# ── Argument parsing (extracted from cmd_run) ─────────────────────────────────

def _parse_cmd_run_args(args: List[str]) -> tuple:
    """Parse CLI arguments, apply defaults. Returns (parsed, tags_str)."""
    if not args:
        args = ['--help']
    args = ['--help' if a == '-help' else a for a in args]
    import argparse as ap
    parser = ap.ArgumentParser(prog='sator', add_help=False)
    
    # Search sources
    parser.add_argument('-s', '--search', action='append', default=[], dest='search_strings')
    
    # Auto-add mode
    parser.add_argument('-a', '--auto-add', nargs='?', const='__flag__', default=None,
                       help='Auto-add to qBittorrent. Optional: path to magnet file')
    
    # Resolution filters
    parser.add_argument('-rl', type=str, default=None)
    parser.add_argument('-rb', type=str, default=None)
    
    # Size filters
    parser.add_argument('-zl', type=str, default=None)
    parser.add_argument('-zb', type=str, default=None)
    
    # Language filters (repeatable)
    parser.add_argument('-l', '--lang', nargs='?', const='__original__', default=None, action='append')
    parser.add_argument('-t', '--subs', nargs='?', const='__original__', default=None, action='append',
                       help='Subtitle language (ISO 639-1 code or name)')
    

    # qBittorrent options
    parser.add_argument('--category', default='')
    parser.add_argument('--tags', nargs='+', default=None)
    parser.add_argument('--qb-url', default=settings.DEFAULT_QB_URL)
    
    # Output file for magnet links
    parser.add_argument('-o', '--output', default='')
    
    # Progress display
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                       help='Verbose output: per-tracker details')
    parser.add_argument('-tt', '--tracker-titles', action='store_true', default=False,
                       help='Show tracker names at start')
    parser.add_argument('-m', '--more', action='store_true', default=False,
                       help='Show all filtered results instead of best one')
    parser.add_argument('-e', '--exclude', type=str, default='',
                       help='Exclude patterns (comma-separated, e.g. CAM,TS,SCR)')
    parser.add_argument('-sn', '--season-number', nargs='*', default=None, action='append',
                       help='Season number (repeatable, no value = all seasons)')
    parser.add_argument('--no-enrich', action='store_false', dest='enrich', default=True,
                       help='Disable TMDB enrichment')
    parser.add_argument('--no-episode-expansion', action='store_true', default=False,
                       help='Disable automatic episode-level expansion for -sn')
    parser.add_argument('--tmdb-key', type=str, default='',
                       help='TMDB API key (overrides config file)')
    parser.add_argument('-n', '--normalize', action='store_true', default=False,
                       help='Normalize file names in qBittorrent according to templates')
    parser.add_argument('-h', '--help', action='store_true')
    
    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        sys.exit(e.code)
    
    # Apply built-in defaults
    parsed = apply_defaults(parsed)
    tags_str = ' '.join(parsed.tags) if parsed.tags else ''
    
    return parsed, tags_str

# ── Direct download mode (extracted from cmd_run) ─────────────────────────────

def _direct_download_mode(parsed: argparse.Namespace, tags_str: str):
    """Handle direct download mode (-a file): read magnets from file and add to qB."""
    auto_file = parsed.auto_add if parsed.auto_add != '__flag__' else ''
    other_keys = []
    if parsed.rl: other_keys.append('-rl')
    if parsed.rb: other_keys.append('-rb')
    if parsed.zl: other_keys.append('-zl')
    if parsed.zb: other_keys.append('-zb')
    if parsed.lang: other_keys.append('-l')
    if parsed.subs: other_keys.append('-t')
    if other_keys:
        print(f'\u26a0 Direct download mode: ignoring {" ".join(other_keys)}', file=sys.stderr)
    if not os.path.exists(auto_file):
        print(f'\u2716 File not found: {auto_file}', file=sys.stderr)
        sys.exit(1)
    entries = _parse_sator_file(auto_file)
    added = 0
    for entry in entries:
        if _qb_add_simple(entry['magnet'], parsed.qb_url, parsed.category, tags_str):
            added += 1
    print(f'\u2022 Added to qBittorrent: {added} links', file=sys.stderr)
    if parsed.normalize and entries:
        added_magnets = []
        for e in entries:
            item = {'magnet': e['magnet'], 'title': '', 'show_name': e.get('show_name', ''), 'season': e.get('season'), 'episode': e.get('episode')}
            added_magnets.append(item)
        _normalize_torrents(parsed, added_magnets, [], len(added_magnets))
    sys.exit(0)

# ── Query building (extracted from cmd_run) ───────────────────────────────────

def _build_queries(parsed: argparse.Namespace) -> tuple:
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
                    # Try TMDB first, fall back to Wikidata
                    season_count = tmdb_get_series_season_count(clean_q, getattr(parsed, 'tmdb_key', ''))
                    if not season_count:
                        season_count = get_series_season_count_wikidata(clean_q, wiki_cache)
                    if not season_count:
                        if parsed.verbose:
                            print(f'  \u26a0 [{clean_q}] season count not found, using pack only',
                                  file=sys.stderr)
                        continue
                    # Build pack query for each season and add to queries
                    for sn in range(1, season_count + 1):
                        ep_count = get_season_episode_count(clean_q, sn, wiki_cache)
                        pack_q = f"{clean_q} S{sn:02d}"
                        if pack_q not in queries:
                            queries.append(pack_q)
                        _series_meta[pack_q] = {'type': 'pack', 'spec_idx': sn}
                        ep_qs = []
                        if ep_count:
                            for ep in range(1, ep_count + 1):
                                ep_q = f"{clean_q} S{sn:02d}E{ep:02d}"
                                queries.append(ep_q)
                                _series_meta[ep_q] = {'type': 'episode', 'spec_idx': sn, 'ep_num': ep}
                                ep_qs.append(ep_q)
                        _series_plan[sn] = {
                            'pack_q': pack_q, 'ep_queries': ep_qs, 'ep_count': ep_count or 0,
                        }
            elif len(spec) == 1:
                season_num = int(spec[0])
                for orig_q in _series_orig:
                    clean_q = re.sub(r'\s+S\d{2}(E\d{2})?$', '', orig_q).strip()
                    if not clean_q or clean_q == orig_q:
                        continue
                    ep_count = get_season_episode_count(clean_q, season_num, wiki_cache)
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
                    ep_qs = []
                    for ep in range(1, ep_count + 1):
                        ep_q = f"{clean_q} S{season_num:02d}E{ep:02d}"
                        queries.append(ep_q)
                        _series_meta[ep_q] = {'type': 'episode', 'spec_idx': season_num, 'ep_num': ep}
                        ep_qs.append(ep_q)
                    _series_plan[season_num] = {
                        'pack_q': pack_q, 'ep_queries': ep_qs, 'ep_count': ep_count,
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
            for label in TRACKER_LABELS.values():
                print(label, file=sys.stderr)
            sys.exit(0)
        print('\u2716 No search queries provided', file=sys.stderr)
        sys.exit(1)
    return queries, _series_meta, _series_plan, cache_dir


def cmd_run(args: List[str]):
    """Main entry point: replaces the bash script entirely."""
    parsed, tags_str = _parse_cmd_run_args(args)
    if parsed.help:
        print(__doc__)
        print("""
SATOR. multi-tracker torrent search with qBittorrent integration

Usage: sator [options]

Search:
  -s, --search QUERY|FILE   Search by query string or file path
  -sn [S] [E] [E] .. [E]    Season number (repeatable, no value = all seasons)
  -e, --exclude PATTERNS    Exclude patterns, comma-separated (CAM,TS,SCR...)
  -l [LANG]                 Audio language (ISO 639-1 code or name)
  -t [LANG]                 Subtitle language (ISO 639-1 code or name)
  -a, --auto-add [FILE]     Auto-add to qBittorrent
  -m, --more                Show all filtered results (default: best only)
  -o, --output FILE         Save magnet links to FILE
  -v, --verbose             Show per-tracker results during search
  -tt, --tracker-titles     Show tracker names before first search
  --category CAT            Category for added torrents
  --tags TAGS               Space-separated tags
  --qb-url URL              qBittorrent WebUI URL (default: http://localhost:8090)
  --no-enrich               Disable TMDB enrichment
  --no-episode-expansion    Disable automatic episode-level expansion
  --tmdb-key KEY            TMDB API key (overrides config)
  -n, --normalize           Normalize file names in qBittorrent (opt-in)

Filters (each at most once):
  -rl RES                   Resolution upper bound
  -rb RES                   Resolution lower bound
  -zl SIZE                  Size upper bound
  -zb SIZE                  Size lower bound
""")
        sys.exit(0)
    
    # ── Resolve modes ──────────────────────────────────────────────────────
    has_search = bool(parsed.search_strings)
    auto_add = parsed.auto_add is not None
    auto_file = ""
    if auto_add and parsed.auto_add != '__flag__':
        auto_file = parsed.auto_add
    
    # -n needs either -a (rename in qB) or -o (save names to file)
    if parsed.normalize and not auto_add and not parsed.output:
        print('  \u26a0 --normalize (-n) requires --auto-add (-a) or --output (-o); ignoring -n', file=sys.stderr)
        parsed.normalize = False
    
    # ── Direct download mode ───────────────────────────────────────────────
    if not has_search and auto_file:
        _direct_download_mode(parsed, tags_str)
    
    # ── Build queries ──────────────────────────────────────────────────────
    queries, _series_meta, _series_plan, cache_dir = _build_queries(parsed)
    if not queries:
        print('\u2716 No search queries provided', file=sys.stderr)
        sys.exit(1)
    
    # ── Wikidata language cache ────────────────────────────────────────────
    lang_cache = os.path.join(cache_dir, 'wikilang.json')
    
    # ── Wikidata language / subtitle resolution ────────────────────────────
    orig_lang_map = {}
    has_original = '__original__' in parsed.lang
    lang_filters = [l for l in parsed.lang if l != '__original__']
    has_original_subs = parsed.subs and '__original__' in parsed.subs
    subs_filters = [s for s in (parsed.subs or []) if s != '__original__']
    
    if has_original or has_original_subs:
        print('\u2022 Resolving original languages via Wikidata...', file=sys.stderr)
        for q in queries:
            if q in orig_lang_map:
                continue
            # Strip season/episode suffix for Wikidata lookup
            # e.g. "rick and morty S09E04" → "rick and morty"
            _clean_q = re.sub(r'\s+S\d{2,}(E\d{2,})?$', '', q).strip()
            if not _clean_q:
                _clean_q = q
            iso = get_wikidata_original_lang(_clean_q, lang_cache)
            if iso:
                orig_lang_map[q] = iso
                name = iso_name(iso) or iso
                print(f'  [{q}] \u2192 {iso} ({name})', file=sys.stderr)
            else:
                orig_lang_map[q] = ''
                print(f'  \u26a0 [{q}] \u2192 could not determine original language', file=sys.stderr)
    
    # ── Resolution helpers ─────────────────────────────────────────────────
    def _res_int(val):
        if not val:
            return None
        v = val.lower()
        if '2160' in v or '4k' in v: return settings.RES_4K
        if '1080' in v or 'fhd' in v: return settings.RES_FHD
        if '720' in v or 'hd' in v: return settings.RES_HD
        if '480' in v or 'sd' in v: return settings.RES_SD
        return None
    
    def _size_bytes(val):
        if not val:
            return None
        return parse_size(val)
    
    # ── Main search loop ───────────────────────────────────────────────────
    total = len(queries)
    found_count = 0
    not_found_items = []
    total_size = 0
    added_count = 0
    all_torrents = []
    _series_pack_results = {}
    _series_ep_results = {}
    _series_tag_added = set()
    start_time = time.time()
    
    # Track magnets added for optional normalization
    _added_magnets = []        # list of (magnet, show_name, season, episode, title)
    
    # Build index: which episode queries belong to which season (for adaptive skip)
    _ep_queries_by_season = {}
    for _q, _meta in _series_meta.items():
        if _meta['type'] == 'episode':
            _sn = _meta['spec_idx']
            _ep_queries_by_season.setdefault(_sn, []).append((_meta['ep_num'], _q))
    _seasons_with_good_pack = set()
    
    for i, q in enumerate(queries):
        # ── Adaptive skip: if season pack is good, skip episode queries ──
        _meta_check = _series_meta.get(q)
        if _meta_check and _meta_check['type'] == 'episode':
            _parent_season = _meta_check['spec_idx']
            if _parent_season in _seasons_with_good_pack:
                if parsed.verbose:
                    print(f'  \u2192 Skipping {q} (pack has >= {settings.PACK_SKIP_EPISODES_SEED_THRESHOLD} seeders)', file=sys.stderr)
                else:
                    qdisp = q[:50] + '...' if len(q) > 50 else q
                    print(f'\r[{num}/{total}] {qdisp}  \u2192 pack better\033[K', file=sys.stderr, flush=True)
                # Mark as empty result for _series_ep_results
                _series_ep_results.setdefault(_parent_season, {})[_meta_check['ep_num']] = None
                continue
        num = i + 1
        
        # Build current language / subtitle filters
        current_lang = list(lang_filters)
        if q in orig_lang_map and orig_lang_map[q]:
            current_lang.append(orig_lang_map[q])
        current_subs = list(subs_filters)
        if has_original_subs and q in orig_lang_map and orig_lang_map[q]:
            current_subs.append(orig_lang_map[q])
        
        # Build filters dict
        filters = {}
        rl = _res_int(parsed.rl)
        rb = _res_int(parsed.rb)
        zl = _size_bytes(parsed.zl)
        zb = _size_bytes(parsed.zb)
        if rl is not None: filters['rl'] = rl
        if rb is not None: filters['rb'] = rb
        if zl is not None: filters['zl'] = zl
        if zb is not None: filters['zb'] = zb
        if current_lang: filters['lang'] = current_lang
        if current_subs: filters['subs'] = current_subs
        if parsed.exclude: filters['excludes'] = [x.strip() for x in parsed.exclude.split(',') if x.strip()]
        if parsed.tmdb_key: filters['tmdb_key'] = parsed.tmdb_key
        filters['tmdb_enrich'] = parsed.enrich
        
        qb_add = auto_add and q not in _series_meta
        result = _process_query_internal(q, filters, qb_add, parsed.qb_url,
                                        parsed.category, tags_str, parsed.output,
                                        verbose=parsed.verbose,
                                        show_tracker_titles=parsed.tracker_titles,
                                        query_num=num, total_queries=total,
                                        best_mode=not parsed.more)
        
        if not result.get('found_any'):
            not_found_items.append(q)
            continue

        if parsed.verbose and result.get('display_lines'):
            for line in result['display_lines']:
                print(line, file=sys.stderr)

        meta = _series_meta.get(q)
        if meta is not None:
            if meta['type'] == 'pack':
                _series_pack_results[meta['spec_idx']] = result
                # Adaptive skip: if pack has enough seeders, skip episode expansion
                if result.get('found_any') and result.get('torrents'):
                    _best_seeds = result['torrents'][0].get('seeders', 0)
                    if _best_seeds >= settings.PACK_SKIP_EPISODES_SEED_THRESHOLD:
                        _seasons_with_good_pack.add(meta['spec_idx'])
                        if parsed.verbose:
                            print(f'  \u2192 Season pack has {_best_seeds} seeders '
                                  f'(>= threshold {settings.PACK_SKIP_EPISODES_SEED_THRESHOLD}), '
                                  f'skipping episode queries',
                                  file=sys.stderr)
            elif meta['type'] == 'episode':
                result['added'] = 0
                _series_ep_results.setdefault(meta['spec_idx'], {})[meta['ep_num']] = result
            continue

        found_count += result['found']
        added_count += result['added']
        total_size += result['total_size']
        all_torrents.extend(result.get('torrents', []))
        
        # Attach series context to torrents for output / normalization
        # Extract show_name from query by stripping season/episode suffix
        _clean_q = re.sub(r'\s+complete seasons$', '', q, flags=re.IGNORECASE).strip()
        _clean_q = re.sub(r'\s+S\d{2,}(E\d{2,})?$', '', _clean_q).strip()
        _t_season = None
        _t_episode = None
        _sn_match = re.search(r'S(\d{2,})(?:E(\d{2,}))?$', q)
        if _sn_match:
            _t_season = int(_sn_match.group(1))
            if _sn_match.group(2):
                _t_episode = int(_sn_match.group(2))
        for t in result.get('torrents', []):
            t['_show_name'] = _clean_q
            t['_season'] = _t_season
            t['_episode'] = _t_episode
        
        # Track added magnets for normalization
        if parsed.normalize and result.get('added', 0) > 0:
            for t in result.get('torrents', []):
                magnet = t.get('magnet', '')
                if magnet:
                    _added_magnets.append({
                        'magnet': magnet,
                        'show_name': _clean_q,
                        'title': t.get('title', ''),
                        'season': _t_season,
                        'episode': _t_episode,
                    })
    
    # ── Compare series: pack vs episodes ──────────────────────────────────
    if _series_plan:
        for season_num, plan in _series_plan.items():
            pack_result = _series_pack_results.get(season_num)
            ep_results = _series_ep_results.get(season_num, {})
            ep_count = plan['ep_count']
            
            pack_ok = pack_result and pack_result.get('found_any')
            pack_torrents = pack_result.get('torrents', []) if pack_ok else []
            
            eps_ok = True
            ep_torrents = []
            ep_results_dict = {}
            for ep in range(1, ep_count + 1):
                ep_res = ep_results.get(ep)
                if not ep_res or not ep_res.get('found_any'):
                    eps_ok = False
                    break
                ep_torrents.extend(ep_res.get('torrents', []))
                ep_results_dict[ep] = ep_res.get('torrents', [])
            
            winner = pick_series_best(pack_torrents, ep_results_dict, ep_count)
            use_episodes = winner['choice'] == 'episodes'
            
            if use_episodes:
                for ep_res in ep_results.values():
                    if ep_res.get('found_any'):
                        found_count += ep_res['found']
                        added_count += ep_res['added']
                        total_size += ep_res['total_size']
                        all_torrents.extend(ep_res.get('torrents', []))
                        for t in ep_res.get('torrents', []):
                            t['_episode'] = True
                if auto_add and parsed.qb_url:
                    clean_name = re.sub(r'\s+S\d{2}(E\d{2})?$', '', plan['pack_q']).strip()
                    ep_tag = f"{settings.SERIES_TAG_PREFIX}{make_series_tag(clean_name)}"
                    ep_added = 0
                    for t in ep_torrents:
                        if t.get('magnet'):
                            ep_tags = tags_str + ',' + ep_tag if tags_str else ep_tag
                            ok = _qb_add_simple(t['magnet'], parsed.qb_url,
                                                parsed.category, ep_tags, paused=False)
                            if ok:
                                ep_added += 1
                            # Track for normalization
                            if ok and parsed.normalize:
                                _added_magnets.append({
                                    'magnet': t['magnet'],
                                    'show_name': clean_name,
                                    'title': t.get('title', ''),
                                    'season': season_num,
                                    'episode': None,  # will detect from filename
                                })
                    added_count += ep_added

                if not parsed.verbose:
                    print(f'  \u2192 Using {ep_count} episodes (better than season pack)', file=sys.stderr)
            else:
                if pack_ok:
                    found_count += pack_result['found']
                    total_size += pack_result['total_size']
                    all_torrents.extend(pack_result.get('torrents', []))
                    if auto_add and parsed.qb_url:
                        clean_name = re.sub(r'\s+S\d{2}(E\d{2})?$', '', plan['pack_q']).strip()
                        pack_added = 0
                        for t in pack_result.get('torrents', []):
                            if t.get('magnet'):
                                ok = _qb_add_simple(t['magnet'], parsed.qb_url,
                                                    parsed.category, tags_str, paused=False)
                                if ok:
                                    pack_added += 1
                                # Track pack magnet for normalization
                                if ok and parsed.normalize:
                                    _added_magnets.append({
                                        'magnet': t['magnet'],
                                        'show_name': clean_name,
                                        'title': t.get('title', ''),
                                        'season': season_num,
                                        'episode': None,
                                    })
                        added_count += pack_added
                    else:
                        # If not auto-adding, still count the pack's previous added (should be 0 now)
                        added_count += pack_result['added']
    # ── Report ─────────────────────────────────────────────────────────────
    duration = int(time.time() - start_time)
    print(f'Found: {found_count}', file=sys.stderr)
    if auto_add:
        size_h = bytes_to_human(total_size)
        print(f'  Added to QB:  {added_count} ({size_h})', file=sys.stderr)
    print(f'  Time:         {duration // 60}m {duration % 60}s', file=sys.stderr)
    
    # ── Output magnets ─────────────────────────────────────────────────────
    if not auto_add and not parsed.output:
        for t in all_torrents:
            if t.get('magnet'):
                print(t['magnet'])
    
    if parsed.output:
        try:
            with open(parsed.output, 'w') as f:
                for i, t in enumerate(all_torrents):
                    if not t.get('magnet'):
                        continue

                    # Compute show_name, season, episode from context if available
                    _t_show = t.get('_show_name', '')
                    _t_season = t.get('_season')
                    _t_episode = t.get('_episode')

                    # Compute normalized name if -n
                    _normalized = ''
                    if parsed.normalize:
                        try:
                            _qi = parse_quality(t.get('title', ''))
                            _sn, _ep = _parse_season_episode(t.get('title', ''))
                            _show = _t_show or re.sub(r'\s+S\d{2}(E\d{2})?$', '', t.get('title', '')).strip()
                            nm, _ = compute_new_name(
                                t.get('title', ''),
                                template_movie=settings.TEMPLATE_MOVIE,
                                template_series=settings.TEMPLATE_SERIES,
                                quality=_qi,
                                known_season=_t_season or _sn,
                                known_episode=_t_episode or _ep,
                                known_show=_show,
                                ep_title='',
                            )
                            _normalized = nm
                        except Exception:
                            _normalized = ''

                    # Build metadata for re-ingestion
                    _meta = {}
                    if _t_show:
                        _meta['show_name'] = _t_show
                    if _t_season:
                        _meta['season'] = _t_season
                    if _t_episode:
                        _meta['episode'] = _t_episode
                    if _normalized:
                        _meta['normalized'] = _normalized
                    _meta_str = json.dumps(_meta, ensure_ascii=False) if _meta else ''

                    f.write(f"# [{t.get('source', '?')}] {t.get('title', '')}\n")
                    f.write(f"# Size: {t.get('size_h', '?')} | {t.get('quality_label', '')} | seeders: {t.get('seeders', 0)}\n")
                    if _normalized:
                        f.write(f"# Normalized: {_normalized}\n")
                    if _meta_str:
                        f.write(f"# Meta: {_meta_str}\n")
                    f.write(f"{t['magnet']}\n\n")
        except OSError as e:
            print(f'\u2716 Failed to write {parsed.output}: {e}', file=sys.stderr)
            sys.exit(1)
    
    # ── Normalize file names in qBittorrent ────────────────────────────────
    if parsed.normalize and _added_magnets:
        _normalize_torrents(parsed, _added_magnets, all_torrents, added_count)


# ── Normalization logic ──────────────────────────────────────────────────────


def main():
    try:
        _main()
    except KeyboardInterrupt:
        print('', file=sys.stderr)
        sys.exit(130)


def _main():
    if len(sys.argv) < 2:
        cmd_run(['--help'])
        return
    
    if sys.argv[1] in ('-h', '--help'):
        cmd_run(['--help'])
        return

    if sys.argv[1] == 'help':
        cmd_run(['--help'])
        return

    command = sys.argv[1]
    cmd_args = sys.argv[2:]

    if command.startswith('-'):
        cmd_run(sys.argv[1:])
        return

    commands = {
        'parse-languages': cmd_parse_languages,
        'parse-quality': cmd_parse_quality,
        'parse-title': cmd_parse_title,
        'iso-lookup': cmd_iso_lookup,
        'qb-add': cmd_qb_add,
        'search': cmd_search,
        'search-all': cmd_search_all,
        'process-query': cmd_process_query,
        'run': cmd_run,
        'wikilang': cmd_wikilang,
        'size': cmd_size,
        'filter': cmd_filter,
    }

    if command in commands:
        commands[command](cmd_args)
    else:
        print(json.dumps({"error": f"Unknown command: {command}. Use 'run --help' for usage."}),
              file=sys.stderr)
        sys.exit(1)
