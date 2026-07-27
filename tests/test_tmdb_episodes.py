"""Tests for TMDB episode title lookup (mocked HTTP)."""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.tmdb import get_tv_show_id, get_season_episode_titles


class MockResponse:
    """Context-manager mock for urllib.request.urlopen return value."""
    def __init__(self, json_data: str):
        self._data = json_data.encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ── get_tv_show_id ───────────────────────────────────────────────────────────

def test_get_tv_show_id_found(monkeypatch):
    """TV show search returns a valid ID."""
    def mock_urlopen(req, timeout=10):
        return MockResponse(json.dumps({
            'results': [{'id': 1396, 'name': 'Breaking Bad'}],
        }))
    monkeypatch.setattr('urllib.request.urlopen', mock_urlopen)

    result = get_tv_show_id('Breaking Bad', 'fake_key')
    assert result == 1396


def test_get_tv_show_id_not_found(monkeypatch):
    def mock_urlopen(req, timeout=10):
        return MockResponse(json.dumps({'results': []}))
    monkeypatch.setattr('urllib.request.urlopen', mock_urlopen)

    result = get_tv_show_id('UnknownShowXYZ', 'fake_key')
    assert result is None


def test_get_tv_show_id_no_key():
    result = get_tv_show_id('Breaking Bad', '')
    assert result is None


# ── get_season_episode_titles ────────────────────────────────────────────────

def test_get_season_episode_titles_found(monkeypatch):
    """Season episode titles are returned correctly."""
    # Isolate from disk cache: use a clean temp directory
    import tempfile
    import sator.tmdb as tmdb_mod
    tmdb_mod._EPISODE_CACHE_PATH = os.path.join(tempfile.mkdtemp(), 'episodes.json')

    def mock_urlopen(req, timeout=10):
        if 'search/tv' in req.full_url:
            return MockResponse(json.dumps({
                'results': [{'id': 1396, 'name': 'Breaking Bad'}],
            }))
        elif 'season' in req.full_url:
            return MockResponse(json.dumps({
                'episodes': [
                    {'episode_number': 1, 'name': 'Pilot'},
                    {'episode_number': 2, 'name': "Cat's in the Bag..."},
                    {'episode_number': 3, 'name': "...And the Bag's in the River"},
                ]
            }))
        raise ValueError(f"Unexpected URL: {req.full_url}")
    monkeypatch.setattr('urllib.request.urlopen', mock_urlopen)

    result = get_season_episode_titles('Breaking Bad', 1, 'fake_key')
    assert result == {1: 'Pilot', 2: "Cat's in the Bag...", 3: "...And the Bag's in the River"}


def test_get_season_episode_titles_not_found(monkeypatch):
    import tempfile
    import sator.tmdb as tmdb_mod
    tmdb_mod._EPISODE_CACHE_PATH = os.path.join(tempfile.mkdtemp(), 'episodes.json')

    def mock_urlopen(req, timeout=10):
        return MockResponse(json.dumps({'results': []}))
    monkeypatch.setattr('urllib.request.urlopen', mock_urlopen)

    result = get_season_episode_titles('UnknownShow', 1, 'fake_key')
    assert result == {}


def test_get_season_episode_titles_no_key():
    result = get_season_episode_titles('Breaking Bad', 1, '')
    assert result == {}


def test_get_season_episode_titles_uses_cache(monkeypatch, tmp_path):
    """Second call for same show/season uses cache, no HTTP request."""
    import sator.tmdb as tmdb_mod
    tmdb_mod._EPISODE_CACHE_PATH = str(tmp_path / 'episodes.json')

    call_count = [0]
    def mock_urlopen(req, timeout=10):
        call_count[0] += 1
        if 'search/tv' in req.full_url:
            return MockResponse(json.dumps({
                'results': [{'id': 1396, 'name': 'Breaking Bad'}],
            }))
        elif 'season' in req.full_url:
            return MockResponse(json.dumps({
                'episodes': [{'episode_number': 1, 'name': 'Pilot'}]
            }))
        raise ValueError(f"Unexpected URL: {req.full_url}")
    monkeypatch.setattr('urllib.request.urlopen', mock_urlopen)

    # First call — makes HTTP (2 requests)
    r1 = get_season_episode_titles('Breaking Bad', 1, 'fake_key')
    assert r1 == {1: 'Pilot'}
    assert call_count[0] == 2

    # Second call — should use disk cache, no HTTP
    r2 = get_season_episode_titles('Breaking Bad', 1, 'fake_key')
    assert r2 == {1: 'Pilot'}
    assert call_count[0] == 2  # no additional calls
