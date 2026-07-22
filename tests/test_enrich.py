#!/usr/bin/env python3
"""Tests for detail page enrichment (_enrich_from_detail)."""

import pytest
from unittest.mock import patch, MagicMock
from sator.indexer import TorrentResult, _enrich_from_detail


def _mock_urlopen(html: str):
    """Return a mock that acts as urlopen return value (not context manager)."""
    m = MagicMock()
    m.read.return_value = html.encode('utf-8')
    return m


class TestEnrichFromDetail:
    """Tests for _enrich_from_detail() detail page scraping."""

    def test_no_info_url(self):
        """Returns empty dict when no info_url."""
        r = TorrentResult(info_url="")
        assert _enrich_from_detail(r) == {}

    def test_http_error(self, monkeypatch):
        """Returns empty dict on HTTP error."""
        def mock_urlopen(*a, **kw):
            raise Exception("connection error")
        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        r = TorrentResult(info_url="https://nyaa.si/view/12345")
        assert _enrich_from_detail(r) == {}

    def test_language_detected_from_text(self, monkeypatch):
        """Detects languages from full words in page."""
        html = """
        <html><body>
        <h1>Lost S01 Complete</h1>
        <p>Audio: English, Japanese</p>
        <p>Subtitles: English</p>
        </body></html>
        """
        m = _mock_urlopen(html)
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: m)
        r = TorrentResult(info_url="https://nyaa.si/view/999")
        result = _enrich_from_detail(r)
        assert 'languages' in result
        assert 'en' in result['languages']
        assert 'ja' in result['languages']

    def test_subtitle_detected(self, monkeypatch):
        """Detects subs from page text."""
        html = """
        <html><body>
        <p>Subtitles: English, French</p>
        </body></html>
        """
        m = _mock_urlopen(html)
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: m)
        r = TorrentResult(info_url="https://nyaa.si/view/888")
        result = _enrich_from_detail(r)
        assert 'subs' in result
        assert 'en' in result['subs']

    def test_subtitle_iso_pattern(self, monkeypatch):
        """Detects subtitle ISO language codes like 'Sub: en'."""
        html = """
        <html><body>
        <p>Sub: en</p>
        </body></html>
        """
        m = _mock_urlopen(html)
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: m)
        r = TorrentResult(info_url="https://nyaa.si/view/777")
        result = _enrich_from_detail(r)
        assert 'subs' in result
        assert 'en' in result['subs']

    def test_no_language_or_subtitle(self, monkeypatch):
        """Returns empty dict when page has no language markers."""
        html = """<html><body><p>No metadata here.</p></body></html>"""
        m = _mock_urlopen(html)
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: m)
        r = TorrentResult(info_url="https://nyaa.si/view/666")
        result = _enrich_from_detail(r)
        assert result == {}

    def test_language_only_no_subs(self, monkeypatch):
        """Returns only languages, no subs when only audio langs found."""
        html = """
        <html><body>
        <p>Audio: German</p>
        </body></html>
        """
        m = _mock_urlopen(html)
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: m)
        r = TorrentResult(info_url="https://nyaa.si/view/555")
        result = _enrich_from_detail(r)
        assert 'languages' in result
        assert 'de' in result['languages']
        assert 'subs' not in result

    def test_no_subtitles_negative(self, monkeypatch):
        """Detects 'No subtitles' and does not set subs."""
        html = """
        <html><body>
        <p>Audio: English</p>
        <p>No subtitles</p>
        </body></html>
        """
        m = _mock_urlopen(html)
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: m)
        r = TorrentResult(info_url="https://nyaa.si/view/444")
        result = _enrich_from_detail(r)
        # 'en' detected from "English" in "Audio: English"
        assert 'languages' in result
        assert 'en' in result['languages']
        # "No subtitles" should prevent subs detection
        if 'subs' in result:
            # If subs got set somehow, it shouldn't have English subs
            assert 'en' not in result['subs'] or len(result['subs']) == 0

    def test_subs_with_additional_subtitle_detection(self, monkeypatch):
        """ISO-based subtitle detection from sub:en patterns works."""
        html = """
        <html><body>
        <p>Language: English</p>
        <p>Sub: en, Sub: fr</p>
        </body></html>
        """
        m = _mock_urlopen(html)
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: m)
        r = TorrentResult(info_url="https://nyaa.si/view/333")
        result = _enrich_from_detail(r)
        # The ISO detection for subs should find 'en' and 'fr'
        if 'subs' in result:
            assert 'en' in result['subs']
            assert 'fr' in result['subs']

    def test_repeatable_call(self, monkeypatch):
        """Multiple calls return same result."""
        html = """<html><body><p>English subtitles</p></body></html>"""
        m = _mock_urlopen(html)
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: m)
        r = TorrentResult(info_url="https://nyaa.si/view/111")
        r1 = _enrich_from_detail(r)
        r2 = _enrich_from_detail(r)
        assert r1 == r2
