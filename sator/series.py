"""Series search: expand queries with season/episode number enrichment.

The ``-sn`` flag accepts multiple values:
  -sn              → all seasons (``complete seasons``)
  -sn N            → season N, all episodes (``S{N:02d}``)
  -sn N E1 E2 …    → season N, episodes E1, E2, … (``S{N:02d}E{E:02d}``)

Repeat ``-sn`` for multiple independent season/episode blocks.
"""


def expand_series_queries(base_query: str, season_specs: list) -> list:
    """Expand *base_query* with season/episode specs from ``-sn``.

    *season_specs* is a list of sublists, one per ``-sn`` invocation:

    =========================================  ================================
    *season_specs*                             Result
    =========================================  ================================
    ``None`` or ``[]``                         ``[base_query]`` (no change)
    ``[[]]``                                   ``['… complete seasons']``
    ``[['2']]``                                ``['… S02']``
    ``[['2', '1', '4']]``                      ``['… S02E01', '… S02E04']``
    ``[['2'], ['3']]``                         ``['… S02', '… S03']``
    ``[['2', '1'], ['3', '5']]``               ``['… S02E01', '… S03E05']``
    =========================================  ================================

    Returns a list of one or more expanded query strings.
    """
    if not season_specs:
        return [base_query]

    queries = []
    for spec in season_specs:
        if not spec:
            # -sn (no arguments) → all seasons
            queries.append(f'{base_query} complete seasons')
            continue

        season = spec[0]
        episodes = spec[1:]

        if not episodes:
            # -sn N → season N, all episodes
            queries.append(f'{base_query} S{int(season):02d}')
        else:
            # -sn N E1 E2 … → specific episodes of season N
            for ep in episodes:
                queries.append(f'{base_query} S{int(season):02d}E{int(ep):02d}')

    return queries


def pick_series_best(pack_torrents: list, episode_torrents_by_num: dict,
                      episode_count: int) -> dict:
    """Compare season pack vs individual episodes and pick the better option.

    Args:
        pack_torrents: List of torrent dicts from the season pack query.
        episode_torrents_by_num: Dict of ``{ep_num: [torrent_dict, ...]}``.
        episode_count: Expected number of episodes in the season.

    Returns:
        ``{'choice': 'pack'|'episodes'|'none', 'torrents': [...]}``
    """
    pack_ok = bool(pack_torrents)

    # Check if all episodes are present
    eps_ok = True
    ep_torrents = []
    for ep in range(1, episode_count + 1):
        ep_res = episode_torrents_by_num.get(ep, [])
        if not ep_res:
            eps_ok = False
            break
        ep_torrents.extend(ep_res)

    if not pack_ok and not eps_ok:
        return {'choice': 'none', 'torrents': []}

    if eps_ok and not pack_ok:
        return {'choice': 'episodes', 'torrents': ep_torrents}

    if not eps_ok and pack_ok:
        return {'choice': 'pack', 'torrents': pack_torrents}

    # Both available - compare by average seeders
    pack_seeders = max((t.get('seeders', 0) for t in pack_torrents), default=0)
    ep_seeders = sum(t.get('seeders', 0) for t in ep_torrents) // episode_count

    if ep_seeders > pack_seeders:
        return {'choice': 'episodes', 'torrents': ep_torrents}
    return {'choice': 'pack', 'torrents': pack_torrents}


def make_series_tag(show_name: str) -> str:
    """Generate a qBittorrent tag for a series from the show name.

    Example: 'Breaking Bad' becomes 'series:breaking-bad'
    """
    import re
    clean = re.sub(r'[^a-z0-9]+', '-', show_name.strip().lower()).strip('-')
    return f"{clean}"
