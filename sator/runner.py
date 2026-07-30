#!/usr/bin/env python3
"""Search runner: Phase 1 (packs) + Phase 2 (episodes for weak packs) + series comparison."""

import re
import sys
import time

from sator import settings
from sator.process import _process_query_internal
from sator.qb_client import _qb_add_simple
from sator.series import pick_series_best, make_series_tag
from sator.size import bytes_to_human

# Need parse_size for _size_bytes helper
from sator.size import parse_size


def _run_search(parsed, queries, _series_meta, _series_plan,
                tags_str, auto_add,
                lang_filters, subs_filters, orig_lang_map, has_original_subs) -> dict:
    """Run Phase 1 (packs) + Phase 2 (weak pack episodes) + series comparison.

    Returns dict with:
      found_count, added_count, total_size, all_torrents,
      not_found_items, start_time, _series_pack_results, _series_ep_results
    """
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

    total = len(queries)
    found_count = 0
    not_found_items = []
    total_size_val = 0
    added_count = 0
    all_torrents = []
    _series_pack_results = {}
    _series_ep_results = {}
    _series_tag_added = set()
    start_time = time.time()

    # Track which seasons have good packs (skip episode expansion)
    _seasons_with_good_pack = set()

    # ── Phase 1: process all queries (non-series + pack queries) ──
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
        total_size_val += result['total_size']
        all_torrents.extend(result.get('torrents', []))

        # Attach series context to torrents for output / normalization
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

    # ── Phase 2: episode queries for weak packs ──────────────────────────
    if _series_plan:
        _ep_queries_to_run = []  # list of (query, season_num, ep_num)
        for season_num, plan in _series_plan.items():
            if season_num in _seasons_with_good_pack:
                continue  # pack is good, skip episode expansion
            clean_q = plan.get('clean_q', '')
            ep_count = plan.get('ep_count', 0)
            if not clean_q or not ep_count:
                continue
            for ep in range(1, ep_count + 1):
                ep_q = f"{clean_q} S{season_num:02d}E{ep:02d}"
                _series_meta[ep_q] = {'type': 'episode', 'spec_idx': season_num, 'ep_num': ep}
                _ep_queries_to_run.append((ep_q, season_num, ep))

        if _ep_queries_to_run:
            _total_ep = len(_ep_queries_to_run)
            for _j, (_ep_q, _sn, _ep) in enumerate(_ep_queries_to_run):
                _num = total + _j + 1
                _total_all = total + _total_ep
                # Build filters (same as Phase 1)
                _ep_lang = list(lang_filters)
                if _ep_q in orig_lang_map and orig_lang_map[_ep_q]:
                    _ep_lang.append(orig_lang_map[_ep_q])
                _ep_subs = list(subs_filters)
                if has_original_subs and _ep_q in orig_lang_map and orig_lang_map[_ep_q]:
                    _ep_subs.append(orig_lang_map[_ep_q])
                _ep_filters = {}
                rl = _res_int(parsed.rl)
                rb = _res_int(parsed.rb)
                zl = _size_bytes(parsed.zl)
                zb = _size_bytes(parsed.zb)
                if rl is not None: _ep_filters['rl'] = rl
                if rb is not None: _ep_filters['rb'] = rb
                if zl is not None: _ep_filters['zl'] = zl
                if zb is not None: _ep_filters['zb'] = zb
                if _ep_lang: _ep_filters['lang'] = _ep_lang
                if _ep_subs: _ep_filters['subs'] = _ep_subs
                if parsed.exclude: _ep_filters['excludes'] = [x.strip() for x in parsed.exclude.split(',') if x.strip()]
                if parsed.tmdb_key: _ep_filters['tmdb_key'] = parsed.tmdb_key
                _ep_filters['tmdb_enrich'] = parsed.enrich

                _ep_result = _process_query_internal(
                    _ep_q, _ep_filters, False, parsed.qb_url,
                    parsed.category, tags_str, parsed.output,
                    verbose=parsed.verbose,
                    show_tracker_titles=parsed.tracker_titles,
                    query_num=_num, total_queries=_total_all,
                    best_mode=not parsed.more,
                )
                if _ep_result.get('found_any'):
                    _ep_result['added'] = 0
                _series_ep_results.setdefault(_sn, {})[_ep] = _ep_result

    # ── Compare series: pack vs episodes ──────────────────────────────────
    if _series_plan:
        for season_num, plan in _series_plan.items():
            ep_count = plan['ep_count']
            if not ep_count:
                # No episode data, use pack as-is
                pack_result = _series_pack_results.get(season_num)
                if pack_result and pack_result.get('found_any'):
                    found_count += pack_result['found']
                    total_size_val += pack_result['total_size']
                    all_torrents.extend(pack_result.get('torrents', []))
                    added_count += pack_result['added']
                continue
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
                found_count += ep_count
                for ep_res in ep_results.values():
                    if ep_res.get('found_any'):
                        added_count += ep_res['added']
                        total_size_val += ep_res['total_size']
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
                    added_count += ep_added

                if not parsed.verbose:
                    print(f'  \u2192 Using {ep_count} episodes (better than season pack)', file=sys.stderr)
            else:
                if pack_ok:
                    found_count += ep_count
                    total_size_val += pack_result['total_size']
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
                        added_count += pack_added
                    else:
                        added_count += pack_result['added']

    return {
        'found_count': found_count,
        'added_count': added_count,
        'total_size': total_size_val,
        'all_torrents': all_torrents,
        'not_found_items': not_found_items,
        'start_time': start_time,
        '_series_pack_results': _series_pack_results,
        '_series_ep_results': _series_ep_results,
    }
