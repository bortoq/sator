#!/usr/bin/env python3
"""Command-line interface for sator."""

import argparse
import json
import os
import re
import sys
from typing import List
from dataclasses import asdict
from sator.iso_langs import iso_lookup, iso_name, iso_code
from sator.language import parse_languages
from sator.quality import parse_quality
from sator.title import parse_title, ParsedTitle
from sator.size import parse_size, bytes_to_human
from sator.wikidata import get_wikidata_original_lang
from sator.filter import filter_result_json
from sator.indexer import search_all, TorrentResult, INDEXERS
from sator.qb_client import _qb_add_simple
from sator.process import _process_query_internal, TRACKER_LABELS
import time

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
    parser.add_argument('--tags', default='')
    parser.add_argument('--ratio', type=float, default=-1)
    parser.add_argument('--seed-time', type=int, default=-1)
    parser.add_argument('--url', default='http://localhost:8090')
    parser.add_argument('--username', default='')
    parser.add_argument('--password', default='')
    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        sys.exit(e.code)

    config = QBConfig(url=parsed.url, username=parsed.username, password=parsed.password)
    client = QBClient(config)
    result = client.add_torrent(parsed.magnet, parsed.category, parsed.tags,
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
    parser.add_argument('--subs', action='append', default=[])
    parser.add_argument('--qb-add', action='store_true', default=False)
    parser.add_argument('--qb-url', default='http://localhost:8090')
    parser.add_argument('--category', default='')
    parser.add_argument('--tags', default='')
    parser.add_argument('-o', '--output', default='')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                       help='Verbose output: per-tracker details')
    parser.add_argument('-tt', '--tracker-titles', action='store_true', default=False,
                       help='Show tracker names at start')
    # Normalize -help to --help
    args = ['--help' if a == '-help' else a for a in args]
    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        sys.exit(e.code)

    query = ' '.join(parsed.query)
    filters = {
        'rl': parsed.rl,
        'rb': parsed.rb,
        'zl': parsed.zl,
        'zb': parsed.zb,
        'lang': parsed.lang,
        'subs': parsed.subs,
    }
    
    out = _process_query_internal(query, filters, parsed.qb_add, parsed.qb_url,
                                  parsed.category, parsed.tags, parsed.output,
                                  verbose=parsed.verbose,
                                  show_tracker_titles=parsed.tracker_titles)
    print(json.dumps(out))



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
DEFAULTS = {
    'rb': '480',        # resolution lower bound (not below 480p)
    'rl': '1080',       # resolution upper bound (not above 1080p)
    'zb': '200m',       # size lower bound (not smaller than 200 MiB)
    'zl': '8g',         # size upper bound (not larger than 8 GiB)
    'lang': ['__original__'],  # audio language: original via Wikidata
    'subs': ['en'],     # subtitle language: English
    'trackers': ['nyaa', 'tpb'],  # active trackers only
}

def apply_defaults(args: argparse.Namespace) -> argparse.Namespace:
    """Fill in built-in defaults for args that were not explicitly provided.
    CLI args always take priority over defaults."""
    # Resolution bounds: None → default string
    if args.rl is None:
        args.rl = DEFAULTS['rl']
    if args.rb is None:
        args.rb = DEFAULTS['rb']
    if args.zl is None:
        args.zl = DEFAULTS['zl']
    if args.zb is None:
        args.zb = DEFAULTS['zb']
    
    # Language: None (not provided) → ['__original__']
    if args.lang is None:
        args.lang = list(DEFAULTS['lang'])
    
    # Subtitles: None (not provided) → ['en']
    if args.subs is None:
        args.subs = list(DEFAULTS['subs'])
    
    # Trackers: None (not provided) → ['nyaa', 'tpb']
    if getattr(args, 'trackers', None) is None:
        args.trackers = list(DEFAULTS['trackers'])
    
    return args


def cmd_run(args: List[str]):
    """Main entry point: replaces the bash script entirely.
    Usage: run <sator-args>  (same CLI as the original sator bash script)
    
    sator -f <file> -s <string> -a [-rl RES] [-rb RES] [-zl SIZE] [-zb SIZE] 
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
    parser.add_argument('-f', '--file', action='append', default=[], dest='search_files')
    parser.add_argument('-s', '--string', action='append', default=[], dest='search_strings')
    
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
    parser.add_argument('-t', '--subs', action='append', default=None)
    
    # Tracker selection
    parser.add_argument('-T', '--trackers', nargs='+', default=None,
                       help='Trackers to search (space-separated, e.g. nyaa tpb)')
    
    # qBittorrent options
    parser.add_argument('--category', default='')
    parser.add_argument('--tags', default='')
    parser.add_argument('--qb-url', default='http://localhost:8090')
    
    # Output file for magnet links
    parser.add_argument('-o', '--output', default='')
    
    # Progress display
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                       help='Verbose output: per-tracker details')
    parser.add_argument('-tt', '--tracker-titles', action='store_true', default=False,
                       help='Show tracker names at start')
    parser.add_argument('-h', '--help', action='store_true')
    # Help
    
    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        sys.exit(e.code)
    
    # Apply built-in defaults to unset args
    parsed = apply_defaults(parsed)
    
    if parsed.help:
        print(__doc__)
        print("""
Usage: sator [options]

Search:
  -f, --file FILE          Search queries from file (one per line)
  -s, --string QUERY       Search by query string

Auto-add:
  -a, --auto-add [FILE]    Auto-add to qBittorrent.
                           Optional FILE = direct magnet links (no search)

Filters (each at most once):
  -rl RES    Resolution upper bound, e.g. 1080p
  -rb RES    Resolution lower bound, e.g. 720p
  -zl SIZE   Size upper bound, suffixes k/m/g/t
  -zb SIZE   Size lower bound, suffixes k/m/g/t

Filters (repeatable):
  -l [LANG]  Audio language (ISO 639-1 code or name).
             Without value = auto-detect original language via Wikidata
  -t LANG    Subtitle language (ISO 639-1 code or name)

Output:
  -o, --output FILE   Save magnet links to FILE

Progress:
  -v, --verbose       Show per-tracker results during search
  -tt, --tracker-titles  Show tracker names before first search

qBittorrent:
  --category CAT      Category for added torrents
  --tags TAGS         Comma-separated tags
  --qb-url URL        qBittorrent WebUI URL (default: http://localhost:8090)
""")
        sys.exit(0)
    
    # ── Resolve modes ──────────────────────────────────────────────────────
    has_search = bool(parsed.search_files or parsed.search_strings)
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
            _qb_add_simple(m, parsed.qb_url, parsed.category, parsed.tags)
            added += 1
        
        print(f'\u2022 Added to qBittorrent: {added} links', file=sys.stderr)
        sys.exit(0)
    
    # ── Build queries ──────────────────────────────────────────────────────
    queries = []
    for f in parsed.search_files:
        if not os.path.exists(f):
            print(f'\u2716 File not found: {f}', file=sys.stderr)
            continue
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Extract year
                year = ''
                ym = re.search(r'([12]\d{3})', line)
                if ym:
                    year = ym.group(1)
                # Clean title from format: N. **Title** -- Year
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
    
    for s in parsed.search_strings:
        queries.append(s)
    
    if not queries:
        if parsed.tracker_titles:
            for label in TRACKER_LABELS.values():
                print(label, file=sys.stderr)
            sys.exit(0)
        
        print('\u2716 No search queries provided', file=sys.stderr)
        sys.exit(1)
    
    # ── Cache dir ──────────────────────────────────────────────────────────
    cache_dir = os.path.expanduser('~/.cache/sator')
    wiki_cache = os.path.join(cache_dir, 'wikilang.json')
    os.makedirs(cache_dir, exist_ok=True)
    
    # ── Wikidata language resolution ───────────────────────────────────────
    orig_lang_map = {}
    has_original = '__original__' in parsed.lang
    lang_filters = [l for l in parsed.lang if l != '__original__']
    subs_filters = parsed.subs
    
    if has_original:
        print('\u2022 Resolving original languages via Wikidata...', file=sys.stderr)
        for q in queries:
            if q in orig_lang_map:
                continue
            iso = get_wikidata_original_lang(q, wiki_cache)
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
        if '2160' in v or '4k' in v: return 2160
        if '1080' in v or 'fhd' in v: return 1080
        if '720' in v or 'hd' in v: return 720
        if '480' in v or 'sd' in v: return 480
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
    start_time = time.time()
    
    for i, q in enumerate(queries):
        num = i + 1
        
        # Build current language filters
        current_lang = list(lang_filters)
        if q in orig_lang_map and orig_lang_map[q]:
            current_lang.append(orig_lang_map[q])
        
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
        if subs_filters: filters['subs'] = subs_filters
        # Call internal processing
        result = _process_query_internal(q, filters, auto_add, parsed.qb_url,
                                        parsed.category, parsed.tags,
                                        verbose=parsed.verbose,
                                        show_tracker_titles=parsed.tracker_titles,
                                        query_num=num, total_queries=total,
                                        trackers=parsed.trackers)
        
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

        found_count += result['found']
        added_count += result['added']
        total_size += result['total_size']
        all_torrents.extend(result.get('torrents', []))
    
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
    
    # To file (if -o specified)
    if parsed.output and all_torrents:
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
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help', 'help'):
        print(__doc__)
        print("""
Commands:
  parse-title <title>        Parse torrent title (name, year, quality, languages)
  parse-languages <title>    Detect languages in torrent title
  parse-quality <title>      Detect quality (resolution, source, codec, HDR)
  iso-lookup <code|name>     Look up ISO 639 language info
  qb-add <magnet>            Add magnet to qBittorrent [--category] [--tags]
  search <tracker|all> <q>   Search torrents on tracker
  search-all <query>         Search all trackers, return combined results
  process-query <query>      Search all + filter [--rl] [--rb] [--zl] [--zb] [--lang] [--subs]
  run <args>                 Full sator workflow (replaces bash script)
  wikilang <query>           Get original language via Wikidata
  size <val>                 Convert size (human↔bytes)
  filter <json>              Filter a result against criteria
  help                       Show this help
""")
        sys.exit(0)

    command = sys.argv[1]
    cmd_args = sys.argv[2:]

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
        print(json.dumps({"error": f"Unknown command: {command}. Use 'help' for usage."}),
              file=sys.stderr)
        sys.exit(1)


