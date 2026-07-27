#!/usr/bin/env python3
"""Command-line interface for sator."""

import argparse
import json
import os
import re
import sys
import time
from typing import List
from dataclasses import asdict
from sator.iso_langs import iso_lookup, iso_name
from sator.language import parse_languages
from sator.quality import parse_quality
from sator.title import parse_title
from sator.size import parse_size, bytes_to_human
from sator.wikidata import get_wikidata_original_lang, get_season_episode_count
from sator.filter import filter_result_json
from sator.indexer import search_all, INDEXERS
from sator.process import _process_query_internal, TRACKER_LABELS
from sator.qb_client import _qb_add_simple
from sator import settings
from sator.series import expand_series_queries

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
    # If --cache not found, query is all args
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
        # Human to bytes
        if val.isdigit():
            result = int(val)
        else:
            result = parse_size(val)
        if result is not None:
            print(json.dumps({"bytes": result, "human": bytes_to_human(result)}))
        else:
            print(json.dumps({"error": f"Invalid size: {val}"}))
    else:
        # Bytes to human
        try:
            b = int(val)
            print(json.dumps({"bytes": b, "human": bytes_to_human(b)}))
        except ValueError:
            print(json.dumps({"error": f"Invalid number: {val}"}))


def cmd_filter(args: List[str]):
    """Usage: filter <json-result|--> --rl <res> --rb <res> --zl <bytes> --zb <bytes> --lang <code> [--lang <code>] --subs <code>
    Use '-' as json-result to read from stdin."""
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

    # Read JSON from arg or stdin
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
    """Usage: search-all <query>
    Search all available trackers, return combined JSON array."""
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
    """CLI wrapper for _process_query_internal.
    Usage: process-query <query> [--rl N] [--rb N] [--zl N] [--zb N]
              [--lang L] [--subs S] [--qb-add] [--qb-url URL]
              [--category CAT] [--tags TAGS] [-o FILE]"""
    import argparse as _ap
    parser = _ap.ArgumentParser()
    parser.add_argument('query', nargs='+')
    parser.add_argument('--rl', type=int, default=None)
    parser.add_argument('--rb', type=int, default=None)
    parser.add_argument('--zl', type=int, default=None)
    parser.add_argument('--zb', type=int, default=None)
    parser.add_argument('--lang', action='append', default=[])
    parser.add_argument('--subs', nargs='?', const='__original__', default=[], action='append',
                       help='Subtitle language (ISO 639-1 code or name)')
    parser.add_argument('--qb-add', action='store_true', default=False)
    parser.add_argument('--qb-url', default=settings.DEFAULT_QB_URL)
    parser.add_argument('--category', default='')
    parser.add_argument('--tags', nargs='+', default=None)
    parser.add_argument('-o', '--output', default='')
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
    parser.add_argument('--tmdb-key', type=str, default='',
                       help='TMDB API key (overrides config file)')
    # Normalize -help to --help
    args = ['--help' if a == '-help' else a for a in args]
    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        sys.exit(e.code)

    tags_str = ' '.join(parsed.tags) if parsed.tags else ''
    query = ' '.join(parsed.query)
    # Series enrichment
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
    # Merge results from multiple expanded queries
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



def _parse_magnet_file(path: str) -> list:
    """Extract magnet URIs from sator-format file (with # comments)."""
    if not os.path.exists(path):
        print(f'\u2716 File not found: {path}', file=sys.stderr)
        sys.exit(1)
    magnets = []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            if s.startswith('magnet:'):
                magnets.append(s)
            else:
                raise ValueError(f"Unexpected line in magnet file: {s[:80]!r}")
    return magnets


# ── Built-in defaults ──────────────────────────────────────────────
# DEFAULTS moved to sator/settings.py

def apply_defaults(args: argparse.Namespace) -> argparse.Namespace:
    """Fill in built-in defaults for args that were not explicitly provided.
    CLI args always take priority over defaults."""
    # Resolution bounds: None → default string
    if args.rl is None:
        args.rl = settings.DEFAULT_RL
    if args.rb is None:
        args.rb = settings.DEFAULT_RB
    if args.zl is None:
        args.zl = settings.DEFAULT_ZL
    if args.zb is None:
        args.zb = settings.DEFAULT_ZB
    
    # Language: None (not provided) → ['__original__']
    if args.lang is None:
        args.lang = list(settings.DEFAULT_LANG)
    
    # Subtitles: None (not provided) → [] (no filter)
    if args.subs is None:
        args.subs = list(settings.DEFAULT_SUBS)
    
    # Trackers: None (not provided) → ['nyaa', 'tpb']
    if getattr(args, 'trackers', None) is None:
        args.trackers = list(settings.DEFAULT_TRACKERS)
    
    return args


def cmd_run(args: List[str]):
    """Main entry point: replaces the bash script entirely.
    Usage: run <sator-args>  (same CLI as the original sator bash script)
    
    sator -s <query|file> -a [-rl RES] [-rb RES] [-zl SIZE] [-zb SIZE] 
          [-l [LANG]] [-t LANG] [-o FILE] [--category CAT] [--tags TAGS]
    """
    # No args → show help (mimics original bash behavior)
    if not args:
        args = ['--help']
    # Normalize -help to --help (argparse chokes on '-help' as '-h'+'elp')
    args = ['--help' if a == '-help' else a for a in args]
    import argparse as ap
    parser = ap.ArgumentParser(prog='sator', add_help=False)
    
    # Search sources
    parser.add_argument('-s', '--search', action='append', default=[], dest='search_strings')
    
    # Auto-add mode
    parser.add_argument('-a', '--auto-add', nargs='?', const='__flag__', default=None,
                       help='Auto-add to qBittorrent. Optional: path to magnet file')
    
    # Resolution filters (each at most once)
    parser.add_argument('-rl', type=str, default=None)
    parser.add_argument('-rb', type=str, default=None)
    
    # Size filters (each at most once)
    parser.add_argument('-zl', type=str, default=None)
    parser.add_argument('-zb', type=str, default=None)
    
    # Language filters (repeatable)
    parser.add_argument('-l', '--lang', nargs='?', const='__original__', default=None, action='append')
    parser.add_argument('-t', '--subs', nargs='?', const='__original__', default=None, action='append',
                       help='Subtitle language (ISO 639-1 code or name)')
    
    # Tracker selection
    parser.add_argument('-T', '--trackers', nargs='+', default=None,
                       help='Trackers: nyaa tpb yts solidtorrents eztv tgx (space-separated)')
    
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
    parser.add_argument('--tmdb-key', type=str, default='',
                       help='TMDB API key (overrides config file)')
    parser.add_argument('-h', '--help', action='store_true')
    # Help
    
    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        sys.exit(e.code)
    
    # Apply built-in defaults to unset args
    parsed = apply_defaults(parsed)
    tags_str = ' '.join(parsed.tags) if parsed.tags else ''
    
    if parsed.help:
        print(__doc__)
        print("""
SATOR. multi-tracker torrent search with qBittorrent integration

Usage: sator [options]

Search:
  -s, --search QUERY|FILE   Search by query string or file path
  -sn [S] [E] [E] .. [E]    Season number (repeatable, no value = all seasons)
  -e, --exclude PATTERNS    Exclude patterns, comma-separated (CAM,TS,SCR...)
  -l [LANG]                 Audio language (ISO 639-1 code or name).
                            Without value = auto-detect original language via Wikidata
  -t [LANG]                 Subtitle language (ISO 639-1 code or name)
                            Without value = auto-detect original language via Wikidata
  -a, --auto-add [FILE]     Auto-add to qBittorrent.
                            Optional FILE = direct magnet links (no search)
  -m, --more                Show all filtered results (default: best only)
  -o, --output FILE         Save magnet links to FILE
  -v, --verbose             Show per-tracker results during search
  -T, --trackers TRACKERS   Trackers: nyaa tpb yts solidtorrents eztv tgx (space-separated)
  -tt, --tracker-titles     Show tracker names before first search
  --category CAT            Category for added torrents
  --tags TAGS               Space-separated tags
  --qb-url URL              qBittorrent WebUI URL (default: http://localhost:8090)
  --no-enrich               Disable TMDB enrichment
  --tmdb-key KEY            TMDB API key (overrides config)

Filters (each at most once):
  -rl RES                   Resolution upper bound, e.g. 1080p
  -rb RES                   Resolution lower bound, e.g. 720p
  -zl SIZE                  Size upper bound, suffixes k/m/g/t
  -zb SIZE                  Size lower bound, suffixes k/m/g/t
""")
        sys.exit(0)
    
    # ── Resolve modes ──────────────────────────────────────────────────────
    has_search = bool(parsed.search_strings)
    auto_add = parsed.auto_add is not None
    auto_file = ""
    if auto_add and parsed.auto_add != '__flag__':
        auto_file = parsed.auto_add
    
    # ── Direct download mode ───────────────────────────────────────────────
    if not has_search and auto_file:
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
        
        magnets = _parse_magnet_file(auto_file)
        added = 0
        for m in magnets:
            _qb_add_simple(m, parsed.qb_url, parsed.category, tags_str)
            added += 1
        
        print(f'\u2022 Added to qBittorrent: {added} links', file=sys.stderr)
        sys.exit(0)
    
    # ── Build queries ──────────────────────────────────────────────────────
    queries = []
        
    for s in parsed.search_strings:
        if os.path.isfile(s):
            # Argument is an existing file → read queries from it
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
            # Regular query string
            queries.append(s)
    
    # ── Series enrichment ─────────────────────────────────────────────────
    if parsed.season_number:
        expanded = []
        for q in queries:
            expanded.extend(expand_series_queries(q, parsed.season_number))
        queries = expanded
    
    # ── Episode-level expansion ──────────────────────────────────────────────
    # For season-only -sn specs, try to get episode count from Wikidata
    # and generate individual episode queries alongside the pack query.
    # Results are compared later; the better option (pack vs episodes) wins.
    # ── Cache dir ──────────────────────────────────────────────────────────
    cache_dir = os.path.expanduser(settings.CACHE_DIR)
    wiki_cache = os.path.join(cache_dir, 'seriess.json')
    os.makedirs(cache_dir, exist_ok=True)
    
    _series_meta = {}     # query -> meta dict
    _series_plan = {}     # spec_idx -> {pack_q, [ep_queries], ep_count}
    _series_orig = list(queries)  # save queries before episode expansion
    
    if parsed.season_number:
        for spec in parsed.season_number:
            if spec and len(spec) == 1:
                season_num = int(spec[0])
                # Find the original query (before series expansion)
                for orig_q in _series_orig:
                    # Reconstruct original query by stripping season suffix
                    clean_q = re.sub(r'\s+S\d{2}(E\d{2})?$', '', orig_q).strip()
                    if not clean_q or clean_q == orig_q:
                        continue
                    ep_count = get_season_episode_count(clean_q, season_num, wiki_cache)
                    if not ep_count:
                        continue
                    pack_q = f"{clean_q} S{season_num:02d}"
                    if pack_q not in queries:
                        continue  # pack query wasn't in the expansion → skip
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
    
    if not queries:
        if parsed.tracker_titles:
            for label in TRACKER_LABELS.values():
                print(label, file=sys.stderr)
            sys.exit(0)
        
        print('\u2716 No search queries provided', file=sys.stderr)
        sys.exit(1)
    
    # ── Cache dir ──────────────────────────────────────────────────────────
    # (cache_dir already initialized above for series cache)
    
    # ── Wikidata language cache (separate from series cache) ──────────────
    lang_cache = os.path.join(cache_dir, 'wikilang.json')
    
    # ── Wikidata language / subtitle resolution ──────────────────────────
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
            iso = get_wikidata_original_lang(q, lang_cache)
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
    _series_pack_results = {}   # season_num -> result dict for pack query
    _series_ep_results = {}     # season_num -> {ep_num -> result dict}
    _series_tag_added = set()   # track which season we've tagged for auto-add
    start_time = time.time()
    
    for i, q in enumerate(queries):
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
        # Call internal processing
        result = _process_query_internal(q, filters, auto_add, parsed.qb_url,
                                        parsed.category, tags_str, parsed.output,
                                        verbose=parsed.verbose,
                                        show_tracker_titles=parsed.tracker_titles,
                                        query_num=num, total_queries=total,
                                        trackers=parsed.trackers,
                                        best_mode=not parsed.more)
        
        if not result.get('found_any'):
            if not parsed.verbose:
                print(f'  Not found', file=sys.stderr)
            not_found_items.append(q)
            continue

        if parsed.verbose and result.get('display_lines'):
            for line in result['display_lines']:
                print(line, file=sys.stderr)
        elif not parsed.verbose:
            f = result['found']
            print(f'  Found: {f}', file=sys.stderr)

        # Redirect series sub-queries to separate tracking
        meta = _series_meta.get(q)
        if meta is not None:
            if meta['type'] == 'pack':
                _series_pack_results[meta['spec_idx']] = result
            elif meta['type'] == 'episode':
                # Don't add to qB yet — comparison/tagging comes later
                result['added'] = 0
                _series_ep_results.setdefault(meta['spec_idx'], {})[meta['ep_num']] = result
            # Don't add to all_torrents yet — comparison comes after the loop
            continue

        found_count += result['found']
        added_count += result['added']
        total_size += result['total_size']
        all_torrents.extend(result.get('torrents', []))
    
    
    # ── Compare series: pack vs episodes ──────────────────────────────────
    if _series_plan:
        for season_num, plan in _series_plan.items():
            pack_result = _series_pack_results.get(season_num)
            ep_results = _series_ep_results.get(season_num, {})
            ep_count = plan['ep_count']
            
            # Evaluate pack
            pack_ok = pack_result and pack_result.get('found_any')
            pack_torrents = pack_result.get('torrents', []) if pack_ok else []
            
            # Evaluate episodes: all must be found
            eps_ok = True
            ep_torrents = []
            for ep in range(1, ep_count + 1):
                ep_res = ep_results.get(ep)
                if not ep_res or not ep_res.get('found_any'):
                    eps_ok = False
                    break
                ep_torrents.extend(ep_res.get('torrents', []))
            
            # Decide winner
            use_episodes = False
            if eps_ok and not pack_ok:
                use_episodes = True
            elif eps_ok and pack_ok:
                # Compare: episodes win if avg score higher than pack score
                # Use seeders as a proxy when no score is available
                pack_seeders = max((t.get('seeders', 0) for t in pack_torrents), default=0)
                ep_seeders = sum(t.get('seeders', 0) for t in ep_torrents) // ep_count
                # Prefer episodes if average seeders > pack seeders
                if ep_seeders > pack_seeders:
                    use_episodes = True
            
            if use_episodes:
                # Episodes win
                for ep_res in ep_results.values():
                    if ep_res.get('found_any'):
                        found_count += ep_res['found']
                        added_count += ep_res['added']
                        total_size += ep_res['total_size']
                        all_torrents.extend(ep_res.get('torrents', []))
                        for t in ep_res.get('torrents', []):
                            t['_episode'] = True
                # Tag episodes in qB if auto-add
                if auto_add and parsed.qb_url:
                    clean_name = re.sub(r'[^a-z0-9]+', '-', 
                        re.sub(r'\s+S\d{2}(E\d{2})?$', '', plan['pack_q']).strip().lower()).strip('-')
                    ep_tag = f"{settings.SERIES_TAG_PREFIX}{clean_name}"
                    ep_added = 0
                    for t in ep_torrents:
                        if t.get('magnet'):
                            ep_tags = tags_str + ',' + ep_tag if tags_str else ep_tag
                            _qb_add_simple(t['magnet'], parsed.qb_url,
                                          parsed.category, ep_tags, paused=False)
                            ep_added += 1
                    added_count += ep_added
                
                if not parsed.verbose:
                    print(f'  \u2192 Using {ep_count} episodes (better than season pack)', file=sys.stderr)
            else:
                # Pack wins (or only pack available)
                if pack_ok:
                    found_count += pack_result['found']
                    added_count += pack_result['added']
                    total_size += pack_result['total_size']
                    all_torrents.extend(pack_result.get('torrents', []))
    
    # ── Report ─────────────────────────────────────────────────────────────
    duration = int(time.time() - start_time)
    print(f'Report:', file=sys.stderr)
    print(f'  Found:        {found_count}', file=sys.stderr)
    print(f'  Not found:    {len(not_found_items)}', file=sys.stderr)
    if auto_add:
        size_h = bytes_to_human(total_size)
        print(f'  Added to QB:  {added_count} ({size_h})', file=sys.stderr)
    print(f'  Time:         {duration // 60}m {duration % 60}s', file=sys.stderr)
    
    # ── Output magnets ─────────────────────────────────────────────────────
    # To stdout (if not auto-add and no -o file)
    if not auto_add and not parsed.output:
        for t in all_torrents:
            if t.get('magnet'):
                print(t['magnet'])
    
    # To file (if -o specified) — always truncate/creates file,
    # write magnets+metadata only if results exist
    if parsed.output:
        try:
            with open(parsed.output, 'w') as f:
                for t in all_torrents:
                    if not t.get('magnet'):
                        continue
                    f.write(f"# [{t.get('source', '?')}] {t.get('title', '')}\n")
                    f.write(f"# Size: {t.get('size_h', '?')} | {t.get('quality_label', '')} | seeders: {t.get('seeders', 0)}\n")
                    f.write(f"{t['magnet']}\n\n")
        except OSError as e:
            print(f'\u2716 Failed to write {parsed.output}: {e}', file=sys.stderr)
            sys.exit(1)


def main():
    try:
        _main()
    except KeyboardInterrupt:
        print('', file=sys.stderr)
        sys.exit(130)

def _main():
    # If first arg is a flag or no args, dispatch to run (the full CLI workflow)
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

    # If it looks like a flag (starts with -), dispatch to run
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