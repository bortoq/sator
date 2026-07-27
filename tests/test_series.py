"""Unit tests for sator/series.py — season/episode query expansion.

Test coverage for -sn with nargs='*' (Variant 2):
  -sn              → all seasons
  -sn N            → season N, all episodes
  -sn N E1 E2 …    → specific episodes of season N
  Repeat -sn for multiple independent season blocks.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.series import expand_series_queries, pick_series_best, make_series_tag


# ── No flags ───────────────────────────────────────────────────────────

def test_no_sn():
    """No -sn flag → single unchanged query."""
    assert expand_series_queries('Show', None) == ['Show']
    assert expand_series_queries('Show', []) == ['Show']


# ── -sn (no values) = all seasons ──────────────────────────────────────

def test_all_seasons():
    """-sn → 'complete seasons'."""
    assert expand_series_queries('Show', [[]]) == ['Show complete seasons']


# ── -sn N = season N all episodes ──────────────────────────────────────

def test_single_season():
    """-sn 2 → 'S02'."""
    assert expand_series_queries('Show', [['2']]) == ['Show S02']


def test_large_season_number():
    """-sn 123 → 'S123'."""
    assert expand_series_queries('Show', [['123']]) == ['Show S123']


def test_zero_padded_season():
    """-sn 1 → 'S01' (zero-padded)."""
    assert expand_series_queries('Show', [['1']]) == ['Show S01']


def test_season_zero():
    """-sn 0 → 'S00'."""
    assert expand_series_queries('Show', [['0']]) == ['Show S00']


# ── -sn N E1 E2 … = specific episodes ──────────────────────────────────

def test_single_episode():
    """-sn 2 5 → 'S02E05'."""
    assert expand_series_queries('Show', [['2', '5']]) == ['Show S02E05']


def test_multiple_episodes():
    """-sn 2 1 4 → 'S02E01', 'S02E04'."""
    result = expand_series_queries('Show', [['2', '1', '4']])
    assert result == ['Show S02E01', 'Show S02E04']


def test_large_episode_number():
    """-sn 2 100 → 'S02E100'."""
    assert expand_series_queries('Show', [['2', '100']]) == ['Show S02E100']


def test_many_episodes():
    """-sn 3 1 2 3 4 5 → five queries for S03E01..S03E05."""
    result = expand_series_queries('Show', [['3', '1', '2', '3', '4', '5']])
    assert result == [
        'Show S03E01', 'Show S03E02', 'Show S03E03',
        'Show S03E04', 'Show S03E05',
    ]


# ── Multiple -sn invocations ───────────────────────────────────────────

def test_two_seasons_all_episodes():
    """-sn 2 -sn 3 → 'S02', 'S03' (two queries)."""
    result = expand_series_queries('Show', [['2'], ['3']])
    assert result == ['Show S02', 'Show S03']


def test_two_seasons_with_episodes():
    """-sn 2 1 -sn 3 5 → 'S02E01', 'S03E05'."""
    result = expand_series_queries('Show', [['2', '1'], ['3', '5']])
    assert result == ['Show S02E01', 'Show S03E05']


def test_mixed_all_and_specific():
    """-sn -sn 2 1 → all seasons + S02E01."""
    result = expand_series_queries('Show', [[], ['2', '1']])
    assert result == ['Show complete seasons', 'Show S02E01']


def test_multiple_all_seasons():
    """-sn -sn → 'complete seasons' appears once per invocation."""
    result = expand_series_queries('Show', [[], []])
    assert result == ['Show complete seasons', 'Show complete seasons']


def test_season_and_episode_mix():
    """-sn 2 -sn 3 1 4 → S02 all + S03E01 + S03E04."""
    result = expand_series_queries('Show', [['2'], ['3', '1', '4']])
    assert result == ['Show S02', 'Show S03E01', 'Show S03E04']


# ── Query preservation ─────────────────────────────────────────────────

def test_query_with_year():
    """Year in query is preserved."""
    assert expand_series_queries('Show 2020', [['2']]) == ['Show 2020 S02']
    assert expand_series_queries('Show 2020', [['2', '3']]) == ['Show 2020 S02E03']


def test_query_with_spaces():
    """Multi-word query is preserved."""
    assert expand_series_queries('Rick and Morty', [['2']]) == ['Rick and Morty S02']
    assert expand_series_queries('The Wire', [['2', '11']]) == ['The Wire S02E11']


# ── Edge cases ─────────────────────────────────────────────────────────

def test_multiple_base_queries():
    """Each base query gets expanded independently."""
    base_queries = ['Show A', 'Show B']
    expanded = []
    for q in base_queries:
        expanded.extend(expand_series_queries(q, [['2', '5']]))
    assert expanded == ['Show A S02E05', 'Show B S02E05']


def test_empty_base_query():
    """Empty base query with -sn 2 → ' S02'."""
    result = expand_series_queries('', [['2']])
    assert result == [' S02']


def test_very_large_numbers():
    """Season 999 episode 999."""
    assert expand_series_queries('Show', [['999', '999']]) == ['Show S999E999']

# ── pick_series_best ────────────────────────────────────────────────────────

def test_pack_wins_episodes_incomplete():
    """If some episodes are missing, pack wins."""
    pack = [{'seeders': 10, 'title': 'Show S01'}]
    ep_results = {1: [{'seeders': 5, 'title': 'Show S01E01'}]}  # only ep 1 of 3
    result = pick_series_best(pack, ep_results, 3)
    assert result['choice'] == 'pack'
    assert result['torrents'] == pack


def test_episodes_win_all_found_no_pack():
    """If pack is empty but all episodes found, episodes win."""
    pack = []
    ep_results = {
        1: [{'seeders': 5, 'title': 'Show S01E01'}],
        2: [{'seeders': 8, 'title': 'Show S01E02'}],
    }
    result = pick_series_best(pack, ep_results, 2)
    assert result['choice'] == 'episodes'
    assert len(result['torrents']) == 2


def test_pack_wins_better_seeders():
    """If both available and pack has more seeders, pack wins."""
    pack = [{'seeders': 100, 'title': 'Show S01'}]
    ep_results = {
        1: [{'seeders': 10, 'title': 'Show S01E01'}],
        2: [{'seeders': 10, 'title': 'Show S01E02'}],
    }
    result = pick_series_best(pack, ep_results, 2)
    assert result['choice'] == 'pack'


def test_episodes_win_better_seeders():
    """If both available and episodes have better avg seeders, episodes win."""
    pack = [{'seeders': 5, 'title': 'Show S01'}]
    ep_results = {
        1: [{'seeders': 50, 'title': 'Show S01E01'}],
        2: [{'seeders': 60, 'title': 'Show S01E02'}],
    }
    result = pick_series_best(pack, ep_results, 2)
    assert result['choice'] == 'episodes'
    assert len(result['torrents']) == 2


def test_none_found():
    """If nothing found, choice is 'none'."""
    result = pick_series_best([], {}, 5)
    assert result['choice'] == 'none'
    assert result['torrents'] == []


def test_pack_wins_empty_ep_results():
    """ep_results dict completely empty but pack exists."""
    pack = [{'seeders': 10, 'title': 'Show S01'}]
    result = pick_series_best(pack, {}, 3)
    assert result['choice'] == 'pack'


# ── make_series_tag ─────────────────────────────────────────────────────────

def test_tag_simple_name():
    """Simple show name becomes series:show-name."""
    tag = make_series_tag('Breaking Bad')
    assert tag == 'breaking-bad'


def test_tag_with_year():
    """Show name with year."""
    tag = make_series_tag('The Wire 2002')
    assert tag == 'the-wire-2002'


def test_tag_special_chars():
    """Special characters stripped."""
    tag = make_series_tag("Stranger Things (2016)")
    assert tag == 'stranger-things-2016'


def test_tag_multi_word():
    """Multi-word show."""
    tag = make_series_tag('Better Call Saul')
    assert tag == 'better-call-saul'

# ── get_season_episode_count (mocked) ────────────────────────────────────────

def test_get_season_episode_count_found(monkeypatch):
    """Wikidata lookup succeeds for Breaking Bad season 1."""
    import json
    responses = iter([
        # 1. Wikipedia search for "Breaking Bad"
        json.dumps({'query': {'search': [{'title': 'Breaking Bad'}]}}),
        # 2. Get Wikidata ID from Wikipedia page
        json.dumps({'query': {'pages': {'1': {'pageprops': {'wikibase_item': 'Q1079'}}}}}),
        # 3. Get series Wikidata entity
        json.dumps({
            'entities': {
                'Q1079': {
                    'claims': {
                        'P527': [
                            {'mainsnak': {'datavalue': {'value': {'id': 'Q1582890'}}}},
                        ]
                    }
                }
            }
        }),
        # 4. Get season 1 entity
        json.dumps({
            'entities': {
                'Q1582890': {
                    'labels': {'en': {'value': 'Breaking Bad, season 1'}},
                    'claims': {
                        'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q3464665'}}}}],
                        'P1113': [{'mainsnak': {'datavalue': {'value': {'amount': '+7', 'unit': '1'}}}}],
                    }
                }
            }
        }),
    ])
    
    def mock_urlopen(req, timeout=10):
        class MockResponse:
            def read(self):
                return next(responses).encode()
        return MockResponse()
    
    monkeypatch.setattr('urllib.request.urlopen', mock_urlopen)
    
    from sator.wikidata import get_season_episode_count
    result = get_season_episode_count('Breaking Bad', 1)
    assert result == 7


def test_get_season_episode_count_not_found(monkeypatch):
    """Wikidata lookup returns 0 for unknown show."""
    import json
    responses = iter([
        json.dumps({'query': {'search': []}}),  # No Wikipedia results
    ])
    
    def mock_urlopen(req, timeout=10):
        class MockResponse:
            def read(self):
                return next(responses).encode()
        return MockResponse()
    
    monkeypatch.setattr('urllib.request.urlopen', mock_urlopen)
    
    from sator.wikidata import get_season_episode_count
    result = get_season_episode_count('UnknownShowXYZ', 1)
    assert result == 0
