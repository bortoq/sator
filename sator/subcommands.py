#!/usr/bin/env python3
"""Sub-commands for sator CLI — extracted from cli.py for modularity."""

import json
import sys
from dataclasses import asdict
from typing import List

from sator.iso_langs import iso_lookup, iso_name
from sator.language import parse_languages
from sator.quality import parse_quality
from sator.title import parse_title
from sator.size import parse_size, bytes_to_human
from sator.wikidata import get_wikidata_original_lang
from sator.filter import filter_result_json
from sator.indexer import search_all, INDEXERS
from sator.process import _process_query_internal, TRACKER_LABELS
from sator.qb_client import QBClient, QBConfig
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
