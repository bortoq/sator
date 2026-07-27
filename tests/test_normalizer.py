"""Tests for normalizer.py — file name generation and sidecar."""

import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.normalizer import (
    compute_new_name,
    _parse_season_episode,
    _clean_show_name,
    _extract_release_group,
    build_sidecar,
    write_sidecar,
)
from sator.quality import parse_quality


# ── _parse_season_episode ───────────────────────────────────────────────────

def test_parse_season_episode_standard():
    s, e = _parse_season_episode('Show.S01E02.1080p.mkv')
    assert s == 1
    assert e == 2


def test_parse_season_only():
    s, e = _parse_season_episode('Show.S01.1080p.mkv')
    assert s == 1
    assert e is None


def test_parse_season_episode_multi_digit():
    s, e = _parse_season_episode('Show.S12E34.1080p.mkv')
    assert s == 12
    assert e == 34


def test_parse_no_season():
    s, e = _parse_season_episode('Movie.2020.1080p.mkv')
    assert s is None
    assert e is None


# ── _clean_show_name ────────────────────────────────────────────────────────

def test_clean_show_simple():
    name = _clean_show_name('Show.Name.2020.1080p.WEB-DL.FLUX.mkv')
    assert 'Show Name' in name


def test_clean_show_with_episode():
    name = _clean_show_name('Show.Name.S01E02.1080p.WEB-DL.FLUX.mkv')
    assert 'Show Name' in name
    assert 'S01' not in name


def test_clean_show_strips_quality():
    name = _clean_show_name('Show.1080p.WEB-DL.BluRay.x264.FLUX.mkv')
    assert 'Show' == name or name == 'Show'


def test_clean_show_strips_group():
    name = _clean_show_name('Show.2020.1080p.BluRay.x264-FLUX.mkv')
    # Group should be stripped
    assert 'FLUX' not in name.upper() or name.upper() == 'SHOW'


def test_clean_show_multi_word():
    name = _clean_show_name('The.Show.Name.2020.1080p.WEB-DL.FLUX.mkv')
    assert 'The Show Name' in name


# ── compute_new_name (movie template) ───────────────────────────────────────

TEMPLATE_MOVIE = '{title} ({year}) [{quality}] [{group}].{ext}'
TEMPLATE_SERIES = '{show} - S{season:02d}E{episode:02d} [{quality}].{ext}'


def test_movie_new_name():
    new_name, meta = compute_new_name(
        'Movie.2020.1080p.WEB-DL.FLUX.mkv',
        template_movie=TEMPLATE_MOVIE,
        template_series=TEMPLATE_SERIES,
    )
    assert 'Movie' in new_name
    assert '(2020)' in new_name
    assert '.mkv' in new_name
    assert meta['year'] == 2020


def test_movie_new_name_no_year():
    new_name, meta = compute_new_name(
        'Movie.1080p.WEB-DL.FLUX.mkv',
        template_movie=TEMPLATE_MOVIE,
        template_series=TEMPLATE_SERIES,
    )
    assert 'Movie' in new_name
    assert meta['year'] == 0


def test_series_new_name():
    new_name, meta = compute_new_name(
        'Show.S01E02.1080p.WEB-DL.FLUX.mkv',
        template_movie=TEMPLATE_MOVIE,
        template_series=TEMPLATE_SERIES,
    )
    assert 'S01E02' in new_name
    assert '.mkv' in new_name
    assert meta['season'] == 1
    assert meta['episode'] == 2


def test_series_new_name_with_known_season():
    new_name, meta = compute_new_name(
        'Show.E02.1080p.WEB-DL.FLUX.mkv',  # unusual name
        template_movie=TEMPLATE_MOVIE,
        template_series=TEMPLATE_SERIES,
        known_season=1,
        known_episode=2,
    )
    assert 'S01E02' in new_name


def test_series_new_name_known_show():
    new_name, meta = compute_new_name(
        'Random.Name.S01E02.1080p.WEB-DL.FLUX.mkv',
        template_movie=TEMPLATE_MOVIE,
        template_series=TEMPLATE_SERIES,
        known_show='Breaking Bad',
    )
    # The clean show name from file is "Random Name", but we override with "Breaking Bad"
    assert meta['show'] == 'Breaking Bad' or 'Breaking Bad' in new_name or 'Breaking' in new_name


def test_new_name_empty_brackets_removed():
    """Empty {group} should not leave [] in filename."""
    new_name, meta = compute_new_name(
        'Movie.2020.1080p.WEB-DL.mkv',  # no group in name
        template_movie='{title} ({year}) [{quality}] [{group}].{ext}',
        template_series=TEMPLATE_SERIES,
    )
    assert '[]' not in new_name
    assert '()' not in new_name or '(2020)' in new_name  # year brackets should remain


def test_new_name_with_modifiers_in_label():
    new_name, meta = compute_new_name(
        'Movie.Extended.1080p.BluRay.FLUX.mkv',
        template_movie='{title} ({year}) [{quality}].{ext}',
        template_series=TEMPLATE_SERIES,
    )
    # quality label should include Extended
    assert 'Extended' in meta['quality'] or 'Extended' in new_name


# ── build_sidecar / write_sidecar ───────────────────────────────────────────

def test_build_sidecar_structure():
    sc = build_sidecar(
        torrent_hash='abc123',
        torrent_name='Test Torrent',
        file_map=[{'original': 'old.mkv', 'renamed': 'new.mkv'}],
        template_used='{title}.{ext}',
        metadata={'title': 'Test', 'ext': 'mkv'},
    )
    assert sc['torrent_hash'] == 'abc123'
    assert sc['torrent_name'] == 'Test Torrent'
    assert sc['renamed'] is True
    assert len(sc['files']) == 1
    assert sc['files'][0]['original'] == 'old.mkv'
    assert sc['files'][0]['renamed'] == 'new.mkv'


def test_write_sidecar_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_sidecar(
            save_path=tmpdir,
            torrent_hash='abc123',
            torrent_name='Test Torrent',
            file_map=[{'original': 'old.mkv', 'renamed': 'new.mkv'}],
            template_used='{title}.{ext}',
            metadata={'title': 'Test', 'ext': 'mkv'},
        )
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data['torrent_hash'] == 'abc123'
        assert data['torrent_name'] == 'Test Torrent'
