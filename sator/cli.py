#!/usr/bin/env python3
"""Command-line interface for sator."""

import argparse
import json
import os
import re
import sys
import time
from typing import List, Optional
from sator.size import parse_size, bytes_to_human
from sator.wikidata import get_wikidata_original_lang
from sator.iso_langs import iso_name
from sator.qb_client import _qb_add_simple
from sator import settings
from sator.queries import _build_queries
from sator.runner import _run_search
from sator.normalizer import compute_new_name, _parse_season_episode
from sator.cli_utils import _parse_sator_file, _normalize_torrents
from sator.subcommands import (
    cmd_parse_languages, cmd_parse_quality, cmd_parse_title,
    cmd_iso_lookup, cmd_qb_add, cmd_search, cmd_wikilang,
    cmd_size, cmd_filter, cmd_search_all, cmd_process_query,
)

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
    print(f'Added to qBittorrent: {added} links', file=sys.stderr)
    if parsed.normalize and entries:
        added_magnets = []
        for e in entries:
            item = {'magnet': e['magnet'], 'title': '', 'show_name': e.get('show_name', ''), 'season': e.get('season'), 'episode': e.get('episode')}
            added_magnets.append(item)
        _normalize_torrents(parsed, added_magnets, [], len(added_magnets))
    sys.exit(0)

# ── Query building (extracted from cmd_run) ───────────────────────────────────



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
        print('Resolving original languages via Wikidata...', file=sys.stderr, end='', flush=True)
        _first_lang_shown = False
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
                if not _first_lang_shown:
                    print(f' {name}', file=sys.stderr, flush=True)
                    _first_lang_shown = True
            else:
                orig_lang_map[q] = ''
                if not _first_lang_shown:
                    print(file=sys.stderr)  # newline after header
                    _first_lang_shown = True
        if not _first_lang_shown:
            print(file=sys.stderr)  # ensure newline if no langs found
    
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
    
    # ── Run search (Phase 1 + Phase 2 + series comparison) ────────────────
    _search_result = _run_search(
        parsed, queries, _series_meta, _series_plan,
        tags_str, auto_add,
        lang_filters, subs_filters, orig_lang_map, has_original_subs,
    )
    found_count = _search_result['found_count']
    added_count = _search_result['added_count']
    total_size = _search_result['total_size']
    all_torrents = _search_result['all_torrents']
    _added_magnets = _search_result['_added_magnets']
    not_found_items = _search_result['not_found_items']
    start_time = _search_result['start_time']
    
    # ── Report ─────────────────────────────────────────────────────────────
    duration = int(time.time() - start_time)
    print(f'Found: {found_count}', file=sys.stderr)
    if auto_add:
        size_h = bytes_to_human(total_size)
        print(f'Added: {added_count} ({size_h})', file=sys.stderr)
    print(f'Time:  {duration // 60}m {duration % 60}s', file=sys.stderr)
    
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
