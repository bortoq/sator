"""Tests for concurrent search, disk cache, and pack-first strategy."""

import sys
import os
import json
import time
import threading
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.indexer import (
    search_all, _search_cache_key, _search_cache_dir,
    _search_cache_load, _search_cache_save, _search_one_tracker,
    INDEXERS, TorrentResult,
)
from sator.queries import _build_queries
from sator.runner import _run_search

# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_torrent(title="Test", seeders=10, size=1_000_000_000):
    return TorrentResult(
        title=title, magnet="magnet:?xt=urn:btih:test123",
        size_bytes=size, seeders=seeders, source="test",
    )


class MockIndexer:
    """A mock indexer that returns controlled results."""
    def __init__(self, results=None, delay=0):
        self.results = results or [_make_torrent()]
        self.delay = delay
        self.search_calls = []
    
    def search(self, query):
        self.search_calls.append(query)
        if self.delay:
            import time
            time.sleep(self.delay)
        return self.results


class MockParsed:
    """Minimal argparse.Namespace for _build_queries."""
    def __init__(self, search_strings=None, season_number=None, verbose=False,
                 tmdb_key='', no_episode_expansion=False, tracker_titles=False,
                 enrich=True, exclude=''):
        self.search_strings = search_strings or ["Test Show"]
        self.season_number = season_number
        self.verbose = verbose
        self.tmdb_key = tmdb_key
        self.no_episode_expansion = no_episode_expansion
        self.tracker_titles = tracker_titles
        self.enrich = enrich
        self.exclude = exclude
        self.rl = None
        self.rb = None
        self.zl = None
        self.zb = None
        self.lang = []
        self.subs = None
        self.output = ''
        self.qb_url = 'http://localhost:8090'
        self.category = ''
        self.tags = None
        self.more = False


# ═══════════════════════════════════════════════════════════════════════════════
# Concurrent Search Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchAllConcurrent:
    """search_all with ThreadPoolExecutor runs trackers in parallel."""

    def test_empty_trackers_returns_empty(self):
        """Empty tracker list returns empty list without error."""
        result = search_all("test", trackers=[])
        assert isinstance(result, list)
        assert len(result) == 0

    def test_unknown_tracker_skipped(self):
        """Unknown tracker names are silently skipped."""
        result = search_all("test", trackers=['__nonexistent__'])
        assert isinstance(result, list)
        assert len(result) == 0

    def test_mixed_known_and_unknown(self, monkeypatch):
        """Known trackers work alongside unknown ones."""
        monkeypatch.setattr('sator.indexer._search_cache_load', lambda: {})
        orig = dict(INDEXERS)
        try:
            for name in list(INDEXERS.keys()):
                INDEXERS[name] = MockIndexer()
            result = search_all("__test_mixed_" + str(id({})), trackers=['nyaa', '__fake__', 'tpb'])
            assert isinstance(result, list)
        finally:
            INDEXERS.clear()
            INDEXERS.update(orig)

    def test_progress_cb_called_for_each_tracker(self, monkeypatch):
        """progress_cb is called for each valid tracker."""
        monkeypatch.setattr('sator.indexer._search_cache_load', lambda: {})
        calls = []
        def cb(name, status, count, error_msg=''):
            calls.append((name, status))
        
        orig = dict(INDEXERS)
        try:
            for name in list(INDEXERS.keys()):
                INDEXERS[name] = MockIndexer()
            search_all("__test_progress_" + str(id({})), trackers=['nyaa', 'tpb'], progress_cb=cb)
            assert len(calls) >= 2
            names = set(c[0] for c in calls)
            assert 'nyaa' in names
            assert 'tpb' in names
        finally:
            INDEXERS.clear()
            INDEXERS.update(orig)

    def test_progress_cb_reports_requesting_then_ok(self, monkeypatch):
        """Each tracker gets 'requesting' and then 'ok'."""
        monkeypatch.setattr('sator.indexer._search_cache_load', lambda: {})
        calls = []
        def cb(name, status, count, error_msg=''):
            calls.append((name, status))
        
        orig = dict(INDEXERS)
        try:
            for name in ['nyaa', 'tpb']:
                INDEXERS[name] = MockIndexer()
            search_all("__test_ok_" + str(id({})), trackers=['nyaa', 'tpb'], progress_cb=cb)
            # Each tracker should have requesting + ok
            nyaa_statuses = [s for n, s in calls if n == 'nyaa']
            assert 'requesting' in nyaa_statuses
            assert 'ok' in nyaa_statuses
        finally:
            INDEXERS.clear()
            INDEXERS.update(orig)

    def test_progress_cb_reports_error_on_failure(self, monkeypatch):
        """If a tracker raises, progress_cb reports 'error'."""
        # Mock cache to avoid stale hits
        monkeypatch.setattr('sator.indexer._search_cache_load', lambda: {})
        
        calls = []
        def cb(name, status, count, error_msg=''):
            calls.append((name, status))
        
        class FailingIndexer:
            def search(self, query):
                raise RuntimeError("Network error")
        
        orig = dict(INDEXERS)
        try:
            INDEXERS['nyaa'] = FailingIndexer()
            # Use unique query to avoid any cache hit
            search_all("__test_fail_" + str(id({})), trackers=['nyaa'], progress_cb=cb)
            statuses = [s for n, s in calls if n == 'nyaa']
            assert 'requesting' in statuses
            assert 'error' in statuses
        finally:
            INDEXERS.clear()
            INDEXERS.update(orig)

    def test_parallel_execution(self, monkeypatch):
        """Multiple trackers are searched concurrently (not sequentially)."""
        monkeypatch.setattr('sator.indexer._search_cache_load', lambda: {})
        orig = dict(INDEXERS)
        try:
            for name in ['a', 'b', 'c']:
                INDEXERS[name] = MockIndexer(delay=0.2)
            
            import time
            start = time.time()
            search_all("__test_parallel_" + str(id({})), trackers=['a', 'b', 'c'])
            elapsed = time.time() - start
            # Should be much less than 600ms if parallel
            assert elapsed < 0.5, f"Took {elapsed:.2f}s, expected <0.5s for parallel"
        finally:
            INDEXERS.clear()
            INDEXERS.update(orig)


# ═══════════════════════════════════════════════════════════════════════════════
# Disk Cache Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchDiskCache:
    """Disk cache for search results (per query+tracker, TTL 5min)."""

    def test_cache_key_deterministic(self):
        """Same query+tracker produces same key."""
        k1 = _search_cache_key("Breaking Bad S01", "nyaa")
        k2 = _search_cache_key("Breaking Bad S01", "nyaa")
        assert k1 == k2

    def test_cache_key_differs_for_different_trackers(self):
        """Different tracker → different key."""
        k1 = _search_cache_key("test", "nyaa")
        k2 = _search_cache_key("test", "tpb")
        assert k1 != k2

    def test_cache_key_differs_for_different_queries(self):
        """Different query → different key."""
        k1 = _search_cache_key("show S01", "nyaa")
        k2 = _search_cache_key("show S02", "nyaa")
        assert k1 != k2

    def test_cache_dir_creates_path(self):
        """_search_cache_dir returns a valid path."""
        d = _search_cache_dir()
        assert isinstance(d, str)
        assert 'search_cache' in d

    def test_cache_load_returns_dict(self):
        """_search_cache_load returns dict even with no cache file."""
        result = _search_cache_load()
        assert isinstance(result, dict)

    def test_cache_save_and_load_roundtrip(self, tmpdir):
        """Saved cache entry is loadable."""
        cache = {'test_key': {'results': [], '_ts': time.time()}}
        
        # Override cache dir to temp
        import sator.indexer as idx
        orig_dir = idx._search_cache_dir
        
        def mock_dir():
            return str(tmpdir)
        idx._search_cache_dir = mock_dir
        
        try:
            _search_cache_save(cache)
            loaded = _search_cache_load()
            assert 'test_key' in loaded
        finally:
            idx._search_cache_dir = orig_dir

    def test_cache_hit_returns_cached_results(self, tmpdir):
        """_search_one_tracker returns cached results without calling indexer."""
        import sator.indexer as idx
        
        # Override cache dir to temp
        orig_dir = idx._search_cache_dir
        orig_indexers = dict(idx.INDEXERS)
        
        def mock_dir():
            return str(tmpdir)
        idx._search_cache_dir = mock_dir
        
        try:
            # Set up cache with pre-cached data
            cache = {}
            ck = _search_cache_key("test query", "mock_tracker")
            cache[ck] = {
                'results': [{'title': 'Cached Result', 'magnet': 'magnet:...',
                             'size_bytes': 500, 'seeders': 5, 'source': 'mock',
                             'info_url': '', 'languages': []}],
                '_ts': time.time(),
            }
            
            # Create a tracker that should NOT be called
            tracker_mock = MagicMock()
            idx.INDEXERS['mock_tracker'] = tracker_mock
            
            results_list = []
            lock = threading.Lock()
            count = _search_one_tracker("test query", "mock_tracker",
                                         cache, results_list, lock)
            
            assert count == 1
            assert len(results_list) == 1
            assert results_list[0].title == 'Cached Result'
            # The mock should NOT have been called (cache hit)
            tracker_mock.search.assert_not_called()
        finally:
            idx._search_cache_dir = orig_dir
            idx.INDEXERS.clear()
            idx.INDEXERS.update(orig_indexers)

    def test_cache_miss_calls_indexer(self, tmpdir):
        """_search_one_tracker calls indexer.search on cache miss."""
        import sator.indexer as idx
        
        orig_dir = idx._search_cache_dir
        orig_indexers = dict(idx.INDEXERS)
        
        def mock_dir():
            return str(tmpdir)
        idx._search_cache_dir = mock_dir
        
        try:
            cache = {}  # empty cache
            tracker_mock = MagicMock()
            tracker_mock.search.return_value = [
                _make_torrent(title="Live Result", seeders=42)
            ]
            idx.INDEXERS['mock_tracker'] = tracker_mock
            
            results_list = []
            lock = threading.Lock()
            count = _search_one_tracker("test query", "mock_tracker",
                                         cache, results_list, lock)
            
            assert count == 1
            assert results_list[0].title == 'Live Result'
            tracker_mock.search.assert_called_once_with("test query")
        finally:
            idx._search_cache_dir = orig_dir
            idx.INDEXERS.clear()
            idx.INDEXERS.update(orig_indexers)

    def test_cache_expired_re_fetches(self, tmpdir):
        """Expired cache entries are re-fetched."""
        import sator.indexer as idx
        
        orig_dir = idx._search_cache_dir
        orig_indexers = dict(idx.INDEXERS)
        
        def mock_dir():
            return str(tmpdir)
        idx._search_cache_dir = mock_dir
        
        try:
            # Cache with old timestamp
            cache = {}
            ck = _search_cache_key("test query", "mock_tracker")
            cache[ck] = {
                'results': [{'title': 'Stale', 'magnet': 'magnet:...',
                             'size_bytes': 500, 'seeders': 5, 'source': 'mock',
                             'info_url': '', 'languages': []}],
                '_ts': time.time() - 9999,  # very old
            }
            
            tracker_mock = MagicMock()
            tracker_mock.search.return_value = [
                _make_torrent(title="Fresh Result", seeders=99)
            ]
            idx.INDEXERS['mock_tracker'] = tracker_mock
            
            results_list = []
            lock = threading.Lock()
            count = _search_one_tracker("test query", "mock_tracker",
                                         cache, results_list, lock)
            
            # Should have re-fetched
            assert count == 1
            assert results_list[0].title == 'Fresh Result'
            tracker_mock.search.assert_called_once()
        finally:
            idx._search_cache_dir = orig_dir
            idx.INDEXERS.clear()
            idx.INDEXERS.update(orig_indexers)

    def test_cache_save_prunes_expired(self, tmpdir):
        """_search_cache_save removes expired entries."""
        import sator.indexer as idx
        
        orig_dir = idx._search_cache_dir
        def mock_dir():
            return str(tmpdir)
        idx._search_cache_dir = mock_dir
        
        try:
            cache = {
                'fresh': {'results': [], '_ts': time.time()},
                'stale': {'results': [], '_ts': time.time() - 9999},
            }
            _search_cache_save(cache)
            # Stale should be pruned
            assert 'fresh' in cache
            assert 'stale' not in cache
        finally:
            idx._search_cache_dir = orig_dir


# ═══════════════════════════════════════════════════════════════════════════════
# Pack-First Strategy Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildQueriesPackFirst:
    """_build_queries generates only pack queries (Phase 1), no episode queries."""

    def test_bare_sn_adds_pack_queries(self, monkeypatch):
        """bare -sn generates one pack query per season, no episode queries."""
        # Mock Wikidata to avoid network calls
        monkeypatch.setattr('sator.queries.get_series_season_count_wikidata',
                             lambda q, c: 3)  # 3 seasons
        monkeypatch.setattr('sator.queries.get_season_episode_count',
                             lambda q, s, c: 10)  # 10 eps per season
        monkeypatch.setattr('sator.queries.tmdb_get_series_season_count',
                             lambda q, k: 0)  # no TMDB
        
        parsed = MockParsed(
            search_strings=["Test Show"],
            season_number=[[]],  # bare -sn
        )
        queries, meta, plan, cache_dir = _build_queries(parsed)
        
        # Should have 3 pack queries (S01, S02, S03)
        assert len(queries) == 3
        assert "Test Show S01" in queries
        assert "Test Show S02" in queries
        assert "Test Show S03" in queries
        
        # No episode queries should exist
        for q in queries:
            assert "E" not in q.split("S")[-1] if "S" in q else True
        
        # Plan should have 3 seasons with ep_count
        assert len(plan) == 3
        for sn, p in plan.items():
            assert p['ep_count'] == 10
            assert 'clean_q' in p
            assert p['clean_q'] == 'Test Show'

    def test_sn_with_number_adds_pack_only(self, monkeypatch):
        """-sn N generates one pack query, no episode queries."""
        monkeypatch.setattr('sator.queries.get_season_episode_count',
                             lambda q, s, c: 7)
        # Need expand_series_queries to add S01 first
        from sator.series import expand_series_queries
        # _build_queries will call expand_series_queries internally
        
        monkeypatch.setattr('sator.queries.tmdb_get_series_season_count',
                             lambda q, k: 0)
        
        parsed = MockParsed(
            search_strings=["Test Show"],
            season_number=[['1']],  # -sn 1
        )
        queries, meta, plan, cache_dir = _build_queries(parsed)
        
        # After expansion: "Test Show S01" → pack query
        assert len(queries) == 1
        assert "Test Show S01" in queries
        assert "E" not in queries[0]
        
        # Plan should have season 1
        assert 1 in plan
        assert plan[1]['ep_count'] == 7

    def test_no_sn_no_expansion(self):
        """Without -sn, queries pass through unchanged."""
        parsed = MockParsed(
            search_strings=["Test Movie 2024"],
            season_number=None,
        )
        queries, meta, plan, cache_dir = _build_queries(parsed)
        assert queries == ["Test Movie 2024"]
        assert not plan

    def test_complete_seasons_removed_after_expansion(self, monkeypatch):
        """'complete seasons' query is removed after being expanded."""
        monkeypatch.setattr('sator.queries.get_series_season_count_wikidata',
                             lambda q, c: 2)
        monkeypatch.setattr('sator.queries.get_season_episode_count',
                             lambda q, s, c: 5)
        monkeypatch.setattr('sator.queries.tmdb_get_series_season_count',
                             lambda q, k: 0)
        
        parsed = MockParsed(
            search_strings=["Test Show"],
            season_number=[[]],  # bare -sn → "complete seasons"
        )
        queries, meta, plan, cache_dir = _build_queries(parsed)
        
        # 'complete seasons' should be removed
        for q in queries:
            assert 'complete seasons' not in q.lower()
        
        # Should have 2 pack queries
        assert "Test Show S01" in queries
        assert "Test Show S02" in queries

    def test_series_meta_only_has_pack_entries(self, monkeypatch):
        """_series_meta only contains pack entries after _build_queries."""
        monkeypatch.setattr('sator.queries.get_series_season_count_wikidata',
                             lambda q, c: 2)
        monkeypatch.setattr('sator.queries.get_season_episode_count',
                             lambda q, s, c: 5)
        monkeypatch.setattr('sator.queries.tmdb_get_series_season_count',
                             lambda q, k: 0)
        
        parsed = MockParsed(
            search_strings=["Test Show"],
            season_number=[[]],
        )
        queries, meta, plan, cache_dir = _build_queries(parsed)
        
        for q, m in meta.items():
            assert m['type'] == 'pack', f"{q} has type={m['type']}"


class TestRunSearchPackFirst:
    """_run_search Phase 2 generates episode queries only for weak packs."""

    def test_adaptive_skip_strong_pack(self, monkeypatch):
        """If pack has >= threshold seeders, Phase 2 generates no episode queries."""
        def mock_process(q, filters, qb_add, qb_url, category, tags, output,
                         verbose=False, show_tracker_titles=False,
                         query_num=1, total_queries=1, trackers=None, best_mode=True):
            return {
                'found_any': True, 'found': 1, 'added': 0,
                'total_size': 0, 'torrents': [
                    {'seeders': 100, 'title': q, 'magnet': '',
                     'size_bytes': 0, 'source': 'test'}
                ],
                'display_lines': [],
            }
        monkeypatch.setattr('sator.runner._process_query_internal', mock_process)
        
        parsed = MockParsed(search_strings=["Test"], season_number=[])
        queries = ["Test S01"]
        meta = {"Test S01": {'type': 'pack', 'spec_idx': 1}}
        plan = {1: {'pack_q': 'Test S01', 'clean_q': 'Test', 'ep_count': 10, 'spec_idx': 1}}
        
        result = _run_search(parsed, queries, meta, plan,
                             tags_str='', auto_add=False,
                             lang_filters=[], subs_filters=[],
                             orig_lang_map={}, has_original_subs=False)
        
        # Phase 2 should NOT add episode queries (pack has 100 seeders >= 10)
        # _series_ep_results should be empty
        ep_results = result.get('_series_ep_results', {})
        assert not ep_results, "Phase 2 should be skipped for strong pack"

    def test_weak_pack_triggers_phase2(self, monkeypatch):
        """If pack has < threshold seeders, Phase 2 generates episode queries."""
        phase2_calls = []
        
        def mock_process(q, filters, qb_add, qb_url, category, tags, output,
                         verbose=False, show_tracker_titles=False,
                         query_num=1, total_queries=1, trackers=None, best_mode=True):
            phase2_calls.append(q)
            return {
                'found_any': True, 'found': 1, 'added': 0,
                'total_size': 0, 'torrents': [
                    {'seeders': 1, 'title': q, 'magnet': '',
                     'size_bytes': 0, 'source': 'test'}
                ],
                'display_lines': [],
            }
        
        monkeypatch.setattr('sator.runner._process_query_internal', mock_process)
        
        parsed = MockParsed(search_strings=["Test"], season_number=[])
        queries = ["Test S01"]
        meta = {"Test S01": {'type': 'pack', 'spec_idx': 1}}
        plan = {1: {'pack_q': 'Test S01', 'clean_q': 'Test', 'ep_count': 3, 'spec_idx': 1}}
        
        result = _run_search(parsed, queries, meta, plan,
                             tags_str='', auto_add=False,
                             lang_filters=[], subs_filters=[],
                             orig_lang_map={}, has_original_subs=False)
        
        # Phase 2 should generate 3 episode queries
        expected_eps = ['Test S01E01', 'Test S01E02', 'Test S01E03']
        for ep_q in expected_eps:
            assert ep_q in phase2_calls, f"{ep_q} not found in Phase 2 calls"
        
        # _series_ep_results should have 3 entries
        ep_results = result.get('_series_ep_results', {})
        assert 1 in ep_results
        assert len(ep_results[1]) == 3

    def test_phase2_skipped_if_no_ep_count(self, monkeypatch):
        """Phase 2 is skipped if ep_count is 0."""
        def mock_process(q, filters, qb_add, qb_url, category, tags, output,
                         verbose=False, show_tracker_titles=False,
                         query_num=1, total_queries=1, trackers=None, best_mode=True):
            return {
                'found_any': True, 'found': 1, 'added': 0,
                'total_size': 0, 'torrents': [
                    {'seeders': 2, 'title': q, 'magnet': '',
                     'size_bytes': 0, 'source': 'test'}
                ],
                'display_lines': [],
            }
        monkeypatch.setattr('sator.runner._process_query_internal', mock_process)
        
        parsed = MockParsed(search_strings=["Test"], season_number=[])
        queries = ["Test S01"]
        meta = {"Test S01": {'type': 'pack', 'spec_idx': 1}}
        # ep_count = 0 → Phase 2 should be skipped
        plan = {1: {'pack_q': 'Test S01', 'clean_q': 'Test', 'ep_count': 0, 'spec_idx': 1}}
        
        result = _run_search(parsed, queries, meta, plan,
                             tags_str='', auto_add=False,
                             lang_filters=[], subs_filters=[],
                             orig_lang_map={}, has_original_subs=False)
        
        ep_results = result.get('_series_ep_results', {})
        assert not ep_results

    def test_series_comparison_pack_wins(self, monkeypatch):
        """When pack beats episodes, pack torrents are selected."""
        _process_calls = {}
        
        def mock_process(q, filters, qb_add, qb_url, category, tags, output,
                         verbose=False, show_tracker_titles=False,
                         query_num=1, total_queries=1, trackers=None, best_mode=True):
            res = {
                'found_any': True, 'found': 1, 'added': 0,
                'total_size': 1000, 'torrents': [
                    {'seeders': 5, 'title': q, 'magnet': '',
                     'size_bytes': 1000, 'source': 'test'}
                ],
                'display_lines': [],
            }
            _process_calls[q] = res
            return res
        
        monkeypatch.setattr('sator.runner._process_query_internal', mock_process)
        
        parsed = MockParsed(search_strings=["Test"], season_number=[])
        queries = ["Test S01"]
        meta = {"Test S01": {'type': 'pack', 'spec_idx': 1}}
        plan = {1: {'pack_q': 'Test S01', 'clean_q': 'Test', 'ep_count': 2, 'spec_idx': 1}}
        
        result = _run_search(parsed, queries, meta, plan,
                             tags_str='', auto_add=False,
                             lang_filters=[], subs_filters=[],
                             orig_lang_map={}, has_original_subs=False)
        
        # Pack has 5 seeders, episodes have 5 seeders each → pack wins (tie goes to pack)
        assert result['found_count'] >= 1
        # all_torrents should contain pack torrent
        assert len(result['all_torrents']) > 0

    def test_non_series_query_accumulates(self, monkeypatch):
        """Non-series queries are accumulated in found_count/all_torrents."""
        call_count = [0]
        def mock_process(q, filters, qb_add, qb_url, category, tags, output,
                         verbose=False, show_tracker_titles=False,
                         query_num=1, total_queries=1, trackers=None, best_mode=True):
            call_count[0] += 1
            return {
                'found_any': True, 'found': 2, 'added': 1,
                'total_size': 2000, 'torrents': [
                    {'seeders': 10, 'title': q, 'magnet': 'magnet:test',
                     'size_bytes': 2000, 'source': 'test'}
                ],
                'display_lines': [],
            }
        
        monkeypatch.setattr('sator.runner._process_query_internal', mock_process)
        
        parsed = MockParsed(search_strings=["Movie A", "Movie B"], season_number=[])
        queries = ["Movie A", "Movie B"]
        
        result = _run_search(parsed, queries, {}, {},
                             tags_str='', auto_add=False,
                             lang_filters=[], subs_filters=[],
                             orig_lang_map={}, has_original_subs=False)
        
        assert result['found_count'] == 4  # 2 per query × 2 queries
        assert result['total_size'] == 4000
        assert len(result['all_torrents']) == 2
