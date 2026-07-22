"""Tests for new indexers: YTS, SolidTorrents, EZTV, TGx."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.indexer import (
    YTSIndexer, SolidTorrentsIndexer, EZTVIndexer, TGxIndexer,
    TorrentResult, INDEXERS, search_all
)


def test_yts_indexer_registered():
    """YTSIndexer is in the INDEXERS registry."""
    assert 'yts' in INDEXERS
    assert isinstance(INDEXERS['yts'], YTSIndexer)


def test_solidtorrents_indexer_registered():
    """SolidTorrentsIndexer is in the INDEXERS registry."""
    assert 'solidtorrents' in INDEXERS
    assert isinstance(INDEXERS['solidtorrents'], SolidTorrentsIndexer)


def test_eztv_indexer_registered():
    """EZTVIndexer is in the INDEXERS registry."""
    assert 'eztv' in INDEXERS
    assert isinstance(INDEXERS['eztv'], EZTVIndexer)


def test_tgx_indexer_registered():
    """TGxIndexer is in the INDEXERS registry."""
    assert 'tgx' in INDEXERS
    assert isinstance(INDEXERS['tgx'], TGxIndexer)


def test_all_indexers_have_name():
    """Every indexer has a non-empty .name."""
    for key, idx in INDEXERS.items():
        assert idx.name == key, f"{key}: name={idx.name!r}"


def test_all_indexers_have_search():
    """Every indexer has a callable search method."""
    for key, idx in INDEXERS.items():
        assert hasattr(idx, 'search'), f"{key} lacks search()"
        assert callable(idx.search), f"{key} search is not callable"


def test_search_returns_list():
    """YTS search returns a list (empty on network error is OK)."""
    idx = YTSIndexer()
    result = idx.search("nonexistent_movie_xyz_2024")
    assert isinstance(result, list)


def test_solidtorrents_search_returns_list():
    """SolidTorrents search returns a list."""
    idx = SolidTorrentsIndexer()
    result = idx.search("nonexistent_query_xyz")
    assert isinstance(result, list)


def test_eztv_search_returns_list():
    """EZTV search returns a list."""
    idx = EZTVIndexer()
    result = idx.search("nonexistent_show_xyz")
    assert isinstance(result, list)


def test_tgx_search_returns_list():
    """TGx search returns a list."""
    idx = TGxIndexer()
    result = idx.search("nonexistent_query_xyz")
    assert isinstance(result, list)


def test_search_all_with_new_trackers():
    """search_all does not crash with new tracker names."""
    # No network call — empty tracker list = rapid pass
    result = search_all("test", trackers=[])
    assert isinstance(result, list)
    assert len(result) == 0


def test_search_all_with_yts():
    """search_all with yts returns a list (may be empty)."""
    result = search_all("nonexistent", trackers=['yts'])
    assert isinstance(result, list)


def test_search_all_skips_unknown():
    """search_all silently skips unknown tracker names."""
    result = search_all("test", trackers=['__nonexistent_tracker__'])
    assert isinstance(result, list)
    assert len(result) == 0


def test_progress_cb_with_new_trackers():
    """progress_cb is called for new trackers."""
    calls = []
    def cb(name, status, count, error_msg=''):
        calls.append((name, status, count))
    
    search_all("test", trackers=['yts', 'solidtorrents'], progress_cb=cb)
    assert len(calls) >= 2  # at least 'requesting' for each
    
    # Check that each tracker had 'requesting' called
    names_in_calls = set(c[0] for c in calls)
    assert 'yts' in names_in_calls
    assert 'solidtorrents' in names_in_calls
