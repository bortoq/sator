"""Detail-page enrichment is bounded and only used for language metadata."""

from sator.indexer import TorrentResult
from sator.process import _filter_and_score_results
from sator import settings


def _empty_output():
    return {'found': 0, 'added': 0, 'total_size': 0,
            'magnets': [], 'torrents': [], 'display_lines': [],
            'found_any': False, 'filtered_count': 0, 'best_indices': []}


def test_detail_fetch_is_bounded_and_skips_other_filter_failures(monkeypatch):
    fetched = []

    def fake_enrich(result, timeout=None):
        fetched.append((result.info_url, timeout))
        return {}

    monkeypatch.setattr('sator.process._enrich_from_detail', fake_enrich)
    results = [TorrentResult(title='Film 1080p', size_bytes=100,
                             seeders=n, source='nyaa', info_url=f'https://example.test/{n}')
               for n in range(12)]
    results.append(TorrentResult(title='Film 1080p', size_bytes=1,
                                 seeders=100, source='nyaa',
                                 info_url='https://example.test/too-small'))
    _filter_and_score_results(results, {'lang': ['ja'], 'zb': 10}, 'Film', '',
                              _empty_output(), False, '', {'nyaa': 0}, {})
    assert len(fetched) == settings.DETAIL_ENRICH_MAX_PAGES
    assert all(url != 'https://example.test/too-small' for url, _ in fetched)
    assert all(timeout <= settings.DETAIL_ENRICH_REQUEST_TIMEOUT for _, timeout in fetched)
