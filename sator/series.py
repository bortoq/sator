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
