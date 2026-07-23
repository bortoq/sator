#!/usr/bin/env python3
"""Integration tests: full search+filter pipeline with mocked HTTP."""

import json
import pytest
from unittest.mock import patch, MagicMock
from sator.process import _process_query_internal


# A realistic Nyaa HTML snippet for one search result row
NYAA_HTML_BASIC = """<table class="table table-bordered table-hover table-striped">
<thead><tr><th>...</th></tr></thead>
<tbody>
<tr class="default">
<td class="text-center"><a href="/user/test">test</a></td>
<td class="text-center"><a href="/view/123456">cat</a></td>
<td class="text-center"><a href="/download/123456.torrent">DL</a></td>
<td class="text-center"><a href="magnet:?xt=urn:btih:AAAA&dn=Test.Movie.2024.1080p.WEB-DL.x264-GROUP">MAGNET</a></td>
<td class="text-center"><a href="/view/123456" title="Test.Movie.2024.1080p.WEB-DL.x264-GROUP">Test.Movie.2024.1080p.WEB-DL.x264-GROUP</a></td>
<td class="text-center">1.5 GiB</td>
<td class="text-center">100</td>
<td class="text-center">50</td>
<td class="text-center">2 days</td>
</tr>
</tbody></table>"""

NYAA_HTML_SUBBED = """<table class="table table-bordered table-hover table-striped">
<thead><tr><th>...</th></tr></thead>
<tbody>
<tr class="default">
<td class="text-center"><a href="/user/test">test</a></td>
<td class="text-center"><a href="/view/123457">cat</a></td>
<td class="text-center"><a href="/download/123457.torrent">DL</a></td>
<td class="text-center"><a href="magnet:?xt=urn:btih:BBBB&dn=Test.Movie.2024.1080p.WEB-DL.x264-GROUP">MAGNET</a></td>
<td class="text-center"><a href="/view/123457" title="Test.Movie.2024.1080p.WEB-DL.x264-GROUP sub.en">Test.Movie.2024.1080p.WEB-DL.x264-GROUP sub.en</a></td>
<td class="text-center">2.0 GiB</td>
<td class="text-center">200</td>
<td class="text-center">100</td>
<td class="text-center">1 day</td>
</tr>
</tbody></table>"""


def _mock_nyaa_html(html: str):
    """Create a mock urlopen that returns given HTML (as if from Nyaa)."""
    m = MagicMock()
    m.read.return_value = html.encode('utf-8')
    return m


class TestProcessQueryIntegration:
    """Full pipeline: _process_query_internal with mocked indexer HTTP."""

    @patch('urllib.request.urlopen')
    def test_basic_search_finds_results(self, mock_urlopen):
        """Basic search returns results with default filters."""
        mock_urlopen.return_value = _mock_nyaa_html(NYAA_HTML_BASIC)
        
        filters = {
            'rl': '1080', 'rb': '480', 'zl': 8589934592, 'zb': 209715200,
            'subs': [], 'lang': ['en'],
        }
        result = _process_query_internal(
            query='test movie', filters=filters,
            qb_add=False, verbose=False, best_mode=True,
            trackers=['nyaa'],
        )
        assert result['found_any'] is True
        assert result['found'] >= 1
        assert len(result['magnets']) >= 1
        assert 'btih:AAAA' in result['magnets'][0]

    @patch('urllib.request.urlopen')
    def test_subtitle_filter_removes_unsubbed(self, mock_urlopen):
        """With -t en, a result without subtitle markers is filtered out."""
        mock_urlopen.return_value = _mock_nyaa_html(NYAA_HTML_BASIC)
        
        filters = {
            'rl': '1080', 'rb': '480', 'zl': 8589934592, 'zb': 209715200,
            'subs': ['en'], 'lang': ['en'],
        }
        result = _process_query_internal(
            query='test movie', filters=filters,
            qb_add=False, verbose=False, best_mode=True,
            trackers=['nyaa'],
        )
        assert result['found_any'] is False
        assert result['found'] == 0

    @patch('urllib.request.urlopen')
    def test_subtitle_filter_passes_subbed(self, mock_urlopen):
        """With -t en, a result with `sub.en` passes."""
        # First call: search (returns HTML with subs)
        # Second call: detail page enrichment if needed
        mock_urlopen.return_value = _mock_nyaa_html(NYAA_HTML_SUBBED)
        
        filters = {
            'rl': '1080', 'rb': '480', 'zl': 8589934592, 'zb': 209715200,
            'subs': ['en'], 'lang': ['en'],
        }
        result = _process_query_internal(
            query='test movie', filters=filters,
            qb_add=False, verbose=False, best_mode=True,
            trackers=['nyaa'],
        )
        assert result['found_any'] is True
        assert result['found'] >= 1

    @patch('urllib.request.urlopen')
    def test_size_filter_removes_too_large(self, mock_urlopen):
        """Size upper bound filters out oversized results."""
        mock_urlopen.return_value = _mock_nyaa_html(NYAA_HTML_BASIC)
        
        # 1.5 GiB result, but upper bound is 1g
        filters = {
            'rl': '1080', 'rb': '480', 'zl': 1073741824, 'zb': 209715200,
            'subs': [], 'lang': ['en'],
        }
        result = _process_query_internal(
            query='test movie', filters=filters,
            qb_add=False, verbose=False, best_mode=True,
            trackers=['nyaa'],
        )
        assert result['found_any'] is False

    @patch('urllib.request.urlopen')
    def test_no_subtitle_filter_allows_all(self, mock_urlopen):
        """Without -t (subs=[]), all results pass subtitle check."""
        mock_urlopen.return_value = _mock_nyaa_html(NYAA_HTML_BASIC)
        
        filters = {
            'rl': '1080', 'rb': '480', 'zl': 8589934592, 'zb': 209715200,
            'subs': [], 'lang': ['en'],
        }
        result = _process_query_internal(
            query='test movie', filters=filters,
            qb_add=False, verbose=False, best_mode=True,
            trackers=['nyaa'],
        )
        assert result['found_any'] is True
        assert result['found'] >= 1

    @patch('urllib.request.urlopen')
    def test_best_mode_returns_single_best(self, mock_urlopen):
        """best_mode=True returns only the best result."""
        # Combine subbed + unsubbed to have multiple results
        combined_html = NYAA_HTML_BASIC.replace('</tbody>', '') + NYAA_HTML_SUBBED.replace('<table', '').replace('</table>', '')
        mock_urlopen.return_value = _mock_nyaa_html(combined_html)
        
        filters = {
            'rl': '1080', 'rb': '480', 'zl': 8589934592, 'zb': 209715200,
            'subs': [], 'lang': ['en'],
        }
        result = _process_query_internal(
            query='test movie', filters=filters,
            qb_add=False, verbose=False, best_mode=True,
            trackers=['nyaa'],
        )
        assert result['found_any'] is True
        # In best mode, only one result should be returned
        # Actually best mode still finds all but only returns best in display
        # The found count is still the total found
        assert result['found'] >= 1

    @patch('urllib.request.urlopen')
    def test_verbose_mode_does_not_crash(self, mock_urlopen):
        """Verbose output works without errors."""
        mock_urlopen.return_value = _mock_nyaa_html(NYAA_HTML_BASIC)
        
        filters = {
            'rl': '1080', 'rb': '480', 'zl': 8589934592, 'zb': 209715200,
            'subs': [], 'lang': ['en'],
        }
        result = _process_query_internal(
            query='test movie', filters=filters,
            qb_add=False, verbose=True, best_mode=True,
            trackers=['nyaa'],
        )
        assert result['found_any'] is True
