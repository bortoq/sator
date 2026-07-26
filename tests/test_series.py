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

from sator.series import expand_series_queries


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
