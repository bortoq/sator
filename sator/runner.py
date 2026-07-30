#!/usr/bin/env python3
"""Search runner: Phase 1 (packs) + Phase 2 (episodes for weak packs) + series comparison."""

import re
import sys
import time

from sator import settings
from sator.process import _process_query_internal
from sator.qb_client import _qb_add_simple
from sator.series import pick_series_best, make_series_tag
from sator.size import parse_size


def _res_int(val):
    """Convert resolution string to numeric constant."""
    if not val:
        return None
    v = val.lower()
    if '2160' in v or '4k' in v: return settings.RES_4K
    if '1080' in v or 'fhd' in v: return settings.RES_FHD
    if '720' in v or 'hd' in v: return settings.RES_HD
    if '480' in v or 'sd' in v: return settings.RES_SD
    return None


def _size_bytes(val):
    """Convert size string to bytes."""
    if not val:
        return None
    return parse_size(val)


def _build_filters(parsed, q, orig_lang_map, lang_filters, subs_filters, has_original_subs):
    """Build filters dict from parsed args and language context."""
    current_lang = list(lang_filters)
    if q in orig_lang_map and orig_lang_map[q]:
        current_lang.append(orig_lang_map[q])
    current_subs = list(subs_filters)
    if has_original_subs and q in orig_lang_map and orig_lang_map[q]:
        current_subs.append(orig_lang_map[q])

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
    if parsed.exclude:
        filters['excludes'] = [x.strip() for x in parsed.exclude.split(',') if x.strip()]
    if parsed.tmdb_key:
        filters['tmdb_key'] = parsed.tmdb_key
    filters['tmdb_enrich'] = parsed.enrich
    return filters


def _attach_series_context(q, result):
    """Attach show name, season, episode to each torrent in result."""
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


def _process_pack_query(parsed, q, i, total, _series_meta, tags_str, auto_add,
                         _seasons_with_good_pack,
                         found_count, not_found_items, total_size_val,
                         added_count, all_torrents,
                         _series_pack_results, _series_ep_results,
                         orig_lang_map, lang_filters, subs_filters, has_original_subs):
    """Process a single Phase 1 query. Returns updated accumulator values."""
    num = i + 1
    filters = _build_filters(parsed, q, orig_lang_map, lang_filters,
                              subs_filters, has_original_subs)

    qb_add = auto_add and q not in _series_meta
    result = _process_query_internal(q, filters, qb_add, parsed.qb_url,
                                    parsed.category, tags_str, parsed.output,
                                    verbose=parsed.verbose,
                                    show_tracker_titles=parsed.tracker_titles,
                                    query_num=num, total_queries=total,
                                    best_mode=not parsed.more)

    if not result.get('found_any'):
        not_found_items.append(q)
        return

    if parsed.verbose and result.get('display_lines'):
        for line in result['display_lines']:
            print(line, file=sys.stderr)

    meta = _series_meta.get(q)
    if meta is not None:
        if meta['type'] == 'pack':
            _series_pack_results[meta['spec_idx']] = result
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
        return

    found_count.append(result['found'])
    added_count.append(result['added'])
    total_size_val.append(result['total_size'])
    all_torrents.extend(result.get('torrents', []))
    _attach_series_context(q, result)


def _run_phase2(parsed, total, _series_meta, _series_plan, _seasons_with_good_pack,
                _series_ep_results, tags_str,
                orig_lang_map, lang_filters, subs_filters, has_original_subs):
    """Phase 2: search episodes for seasons without a good pack."""
    if not _series_plan:
        return
    _ep_queries_to_run = []
    for season_num, plan in _series_plan.items():
        if season_num in _seasons_with_good_pack:
            continue
        clean_q = plan.get('clean_q', '')
        ep_count = plan.get('ep_count', 0)
        if not clean_q or not ep_count:
            continue
        for ep in range(1, ep_count + 1):
            ep_q = f"{clean_q} S{season_num:02d}E{ep:02d}"
            _series_meta[ep_q] = {'type': 'episode', 'spec_idx': season_num, 'ep_num': ep}
            _ep_queries_to_run.append((ep_q, season_num, ep))

    if not _ep_queries_to_run:
        return
    _total_ep = len(_ep_queries_to_run)
    for _j, (_ep_q, _sn, _ep) in enumerate(_ep_queries_to_run):
        _num = total + _j + 1
        _total_all = total + _total_ep
        _ep_filters = _build_filters(parsed, _ep_q, orig_lang_map, lang_filters,
                                      subs_filters, has_original_subs)
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


def _compare_seasons(parsed, _series_plan, _series_pack_results, _series_ep_results,
                     found_count, total_size_val, all_torrents,
                     added_count, tags_str, auto_add):
    """Phase 3: compare pack vs episodes for each season and pick best."""
    if not _series_plan:
        return
    for season_num, plan in _series_plan.items():
        ep_count = plan['ep_count']
        if not ep_count:
            pack_result = _series_pack_results.get(season_num)
            if pack_result and pack_result.get('found_any'):
                found_count.append(pack_result['found'])
                total_size_val.append(pack_result['total_size'])
                all_torrents.extend(pack_result.get('torrents', []))
                added_count.append(pack_result['added'])
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
            found_count.append(ep_count)
            for ep_res in ep_results.values():
                if ep_res.get('found_any'):
                    added_count.append(ep_res['added'])
                    total_size_val.append(ep_res['total_size'])
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
                added_count.append(ep_added)
            if not parsed.verbose:
                print(f'  \u2192 Using {ep_count} episodes (better than season pack)', file=sys.stderr)
        else:
            if pack_ok:
                found_count.append(ep_count)
                total_size_val.append(pack_result['total_size'])
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
                    added_count.append(pack_added)
                else:
                    added_count.append(pack_result['added'])


def _run_search(parsed, queries, _series_meta, _series_plan,
                tags_str, auto_add,
                lang_filters, subs_filters, orig_lang_map, has_original_subs) -> dict:
    """Run Phase 1 (packs) + Phase 2 (weak pack episodes) + series comparison.

    Returns dict with:
      found_count, added_count, total_size, all_torrents,
      not_found_items, start_time, _series_pack_results, _series_ep_results
    """
    total = len(queries)
    start_time = time.time()

    # Use lists as mutable accumulators so sub-functions can update them
    found_count = []
    not_found_items = []
    total_size_val = []
    added_count = []
    all_torrents = []

    _series_pack_results = {}
    _series_ep_results = {}
    _seasons_with_good_pack = set()

    # ── Phase 1: process all queries ──
    for i, q in enumerate(queries):
        _process_pack_query(parsed, q, i, total, _series_meta, tags_str, auto_add,
                            _seasons_with_good_pack,
                            found_count, not_found_items, total_size_val,
                            added_count, all_torrents,
                            _series_pack_results, _series_ep_results,
                            orig_lang_map, lang_filters, subs_filters, has_original_subs)

    # ── Phase 2: episode queries for weak packs ──
    _run_phase2(parsed, total, _series_meta, _series_plan, _seasons_with_good_pack,
                _series_ep_results, tags_str,
                orig_lang_map, lang_filters, subs_filters, has_original_subs)

    # ── Phase 3: compare pack vs episodes ──
    _compare_seasons(parsed, _series_plan, _series_pack_results, _series_ep_results,
                     found_count, total_size_val, all_torrents,
                     added_count, tags_str, auto_add)

    return {
        'found_count': sum(found_count),
        'added_count': sum(added_count),
        'total_size': sum(total_size_val),
        'all_torrents': all_torrents,
        'not_found_items': not_found_items,
        'start_time': start_time,
        '_series_pack_results': _series_pack_results,
        '_series_ep_results': _series_ep_results,
    }
