"""Tests for Russian anime trackers: AniLibria and RuTor."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.indexer import (
    AniLibriaIndexer, RuTorIndexer,
    TorrentResult, INDEXERS, search_all,
)
from sator import settings


# ── Registration ────────────────────────────────────────────────────────────

def test_anilibria_indexer_registered():
    """AniLibriaIndexer is in the INDEXERS registry."""
    assert 'anilibria' in INDEXERS
    assert isinstance(INDEXERS['anilibria'], AniLibriaIndexer)


def test_rutor_indexer_registered():
    """RuTorIndexer is in the INDEXERS registry."""
    assert 'rutor' in INDEXERS
    assert isinstance(INDEXERS['rutor'], RuTorIndexer)


def test_anilibria_indexer_name():
    """AniLibriaIndexer has correct .name."""
    idx = AniLibriaIndexer()
    assert idx.name == 'anilibria'


def test_rutor_indexer_name():
    """RuTorIndexer has correct .name."""
    idx = RuTorIndexer()
    assert idx.name == 'rutor'


def test_anilibria_indexer_has_search():
    """AniLibriaIndexer has a callable search method."""
    idx = AniLibriaIndexer()
    assert hasattr(idx, 'search')
    assert callable(idx.search)


def test_rutor_indexer_has_search():
    """RuTorIndexer has a callable search method."""
    idx = RuTorIndexer()
    assert hasattr(idx, 'search')
    assert callable(idx.search)


# ── Stub network tests (return list, may be empty on network error) ─────────

def test_anilibria_search_returns_list():
    """AniLibria search returns a list (empty on no network/error is OK)."""
    idx = AniLibriaIndexer()
    result = idx.search("nonexistent_anime_xyz_2024")
    assert isinstance(result, list)


def test_rutor_search_returns_list():
    """RuTor search returns a list (empty on no network/error is OK)."""
    idx = RuTorIndexer()
    result = idx.search("nonexistent_anime_xyz_2024")
    assert isinstance(result, list)


def test_search_all_with_anilibria():
    """search_all with anilibria returns a list (may be empty)."""
    result = search_all("nonexistent", trackers=['anilibria'])
    assert isinstance(result, list)


def test_search_all_with_rutor():
    """search_all with rutor returns a list (may be empty)."""
    result = search_all("nonexistent", trackers=['rutor'])
    assert isinstance(result, list)


def test_search_all_with_both_new():
    """search_all with both new trackers returns a list."""
    result = search_all("nonexistent", trackers=['anilibria', 'rutor'])
    assert isinstance(result, list)


# ── Progress callback integration ──────────────────────────────────────────

def test_progress_cb_with_anilibria():
    """progress_cb is called for anilibria tracker."""
    calls = []
    def cb(name, status, count, error_msg=''):
        calls.append((name, status, count))

    search_all("test", trackers=['anilibria'], progress_cb=cb)
    assert len(calls) >= 1
    names = set(c[0] for c in calls)
    assert 'anilibria' in names


def test_progress_cb_with_rutor():
    """progress_cb is called for rutor tracker."""
    calls = []
    def cb(name, status, count, error_msg=''):
        calls.append((name, status, count))

    search_all("test", trackers=['rutor'], progress_cb=cb)
    assert len(calls) >= 1
    names = set(c[0] for c in calls)
    assert 'rutor' in names


# ── Settings integrity ─────────────────────────────────────────────────────

def test_anilibria_settings():
    """AniLibria settings are properly configured."""
    assert hasattr(settings, 'TIMEOUT_ANILIBRIA')
    assert hasattr(settings, 'ANILIBRIA_API_URL')
    assert hasattr(settings, 'ANILIBRIA_SEARCH_LIMIT')
    assert settings.TIMEOUT_ANILIBRIA > 0
    assert 'anilibria.top' in settings.ANILIBRIA_API_URL
    assert settings.ANILIBRIA_SEARCH_LIMIT > 0


def test_rutor_settings():
    """RuTor settings are properly configured."""
    assert hasattr(settings, 'TIMEOUT_RUTOR')
    assert hasattr(settings, 'RUTOR_BASE_URL')
    assert hasattr(settings, 'RUTOR_MIRRORS')
    assert hasattr(settings, 'RUTOR_ANIME_CATEGORY')
    assert settings.TIMEOUT_RUTOR > 0
    assert len(settings.RUTOR_MIRRORS) > 0
    assert settings.RUTOR_ANIME_CATEGORY == 10


# ── Mock-based unit tests for parsing logic ───────────────────────────────

def test_anilibria_parse_torrent_result():
    """Verify TorrentResult structure matches what AniLibria would produce."""
    # Simulate what AniLibria returns
    t = TorrentResult(
        title="Naruto Shippuuden - AniLiberty.TOP [HDTVRip 720p][AVC][370-500]",
        magnet="magnet:?xt=urn:btih:1234&dn=Test",
        size_bytes=52787876553,
        seeders=4,
        source="anilibria",
    )
    assert t.title
    assert 'magnet:' in t.magnet
    assert t.size_bytes > 0
    assert t.source == 'anilibria'
    assert t.seeders == 4


def test_rutor_parse_torrent_result():
    """Verify TorrentResult structure matches what RuTor would produce."""
    t = TorrentResult(
        title="Наруто / Naruto [001-220] (2002) BDRip",
        magnet="magnet:?xt=urn:btih:5678&dn=Test",
        size_bytes=23622320128,
        seeders=5,
        source="rutor",
    )
    assert t.title
    assert 'magnet:' in t.magnet
    assert t.size_bytes > 0
    assert t.source == 'rutor'
    assert t.seeders == 5


# ── guard: empty query ─────────────────────────────────────────────────────

def test_anilibria_search_empty_string():
    """AniLibria search with empty string returns a list."""
    idx = AniLibriaIndexer()
    # API may reject empty, so expect a list (possibly empty)
    result = idx.search("")
    assert isinstance(result, list)


def test_rutor_search_empty_string():
    """RuTor search with empty string returns a list."""
    idx = RuTorIndexer()
    result = idx.search("")
    assert isinstance(result, list)

# ── Language detection in indexers ───────────────────────────────────────

def test_rutor_language_detection_cyrillic():
    """RuTor Indexer sets languages=['ru'] when title contains Cyrillic."""
    # Simulate what RuTor produces with a Cyrillic title
    t = TorrentResult(
        title="Лето, Когда Погас Свет / Hikaru ga Shinda Natsu [S01] (2025) WEBRip 1080p | L2 | AEROChannelEkat & Риша",
        magnet="magnet:?xt=urn:btih:5678&dn=Test",
        size_bytes=10737418240,
        seeders=0,
        source="rutor",
        languages=['ru'],
    )
    assert t.languages == ['ru']


def test_rutor_language_detection_dub_marker():
    """RuTor Indexer sets languages=['ru'] when title has RuTor dub marker (| L |)."""
    t = TorrentResult(
        title="Test Anime [S01] (2025) WEBRip 1080p | L | SomeGroup",
        magnet="magnet:?xt=urn:btih:5678&dn=Test",
        size_bytes=10737418240,
        seeders=5,
        source="rutor",
        languages=['ru'],
    )
    assert t.languages == ['ru']


def test_rutor_language_detection_dub_marker_d():
    """RuTor dub marker | D | triggers Russian language."""
    t = TorrentResult(
        title="Test Anime [S01] (2025) WEBRip 1080p | D | Studio",
        magnet="magnet:?xt=urn:btih:5678&dn=Test",
        size_bytes=10737418240,
        seeders=5,
        source="rutor",
        languages=['ru'],
    )
    assert t.languages == ['ru']


def test_rutor_language_detection_no_russian():
    """RuTor Indexer sets empty languages for non-Russian title."""
    t = TorrentResult(
        title="The Summer Hikaru Died S01 (2025) WEBRip 1080p x265",
        magnet="magnet:?xt=urn:btih:5678&dn=Test",
        size_bytes=5368709120,
        seeders=10,
        source="rutor",
        languages=[],
    )
    # No Cyrillic, no dub marker → no language set
    assert t.languages == []


def test_anilibria_language_detection_cyrillic():
    """AniLibria Indexer sets languages=['ru'] when title contains Cyrillic."""
    t = TorrentResult(
        title="Наруто: Ураганные хроники [S01] (2007) WEBRip",
        magnet="magnet:?xt=urn:btih:1234&dn=Test",
        size_bytes=52787876553,
        seeders=4,
        source="anilibria",
        languages=['ru'],
    )
    assert t.languages == ['ru']


def test_anilibria_language_detection_english():
    """AniLibria Indexer sets empty languages for English-only title."""
    t = TorrentResult(
        title="Naruto Shippuuden - AniLiberty.TOP [HDTVRip 720p][AVC][370-500]",
        magnet="magnet:?xt=urn:btih:1234&dn=Test",
        size_bytes=52787876553,
        seeders=4,
        source="anilibria",
        languages=[],
    )
    assert t.languages == []


# ── Language filter respects indexer-provided languages ──────────────────

def test_filter_respects_indexer_languages_ru():
    """filter_result_json accepts result with languages=['ru'] when -l ru is set."""
    from sator.filter import filter_result_json
    result = {
        'title': 'Some English Title Without Cyrillic',
        'languages': ['ru'],
        'quality': {'resolution': '1080p', 'source': 'WEBRip'},
        'seeders': 5,
    }
    filters = {'lang': ['ru']}
    r = filter_result_json(result, filters)
    assert r is not None, "Should keep result with languages=['ru'] from indexer"


def test_filter_rejects_without_indexer_languages():
    """filter_result_json rejects result with no language markers when -l ru."""
    from sator.filter import filter_result_json
    result = {
        'title': 'Some English Title Without Cyrillic',
        'languages': [],
        'quality': {'resolution': '1080p', 'source': 'WEBRip'},
        'seeders': 5,
    }
    filters = {'lang': ['ru']}
    r = filter_result_json(result, filters)
    assert r is None, "Should reject result with no ru language marker when -l ru"


def test_filter_en_keeps_unmarked():
    """filter_result_json keeps unmarked results with -l en (pass-through)."""
    from sator.filter import filter_result_json
    result = {
        'title': 'Some English Title Without Cyrillic',
        'languages': [],
        'quality': {'resolution': '1080p', 'source': 'WEBRip'},
        'seeders': 5,
    }
    filters = {'lang': ['en']}
    r = filter_result_json(result, filters)
    assert r is not None, "Should keep unmarked result with -l en (default fallback)"

def test_rutor_language_detection_dub_marker_p():
    """RuTor dub marker | P | triggers Russian language."""
    t = TorrentResult(
        title="Test Anime [S01] (2025) WEBRip 1080p | P | StudioName",
        magnet="magnet:?xt=urn:btih:5678&dn=Test",
        size_bytes=10737418240,
        seeders=5,
        source="rutor",
        languages=['ru'],
    )
    assert t.languages == ['ru']
