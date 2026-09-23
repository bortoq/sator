#!/usr/bin/env python3
"""Tests for Wikidata helpers (_clean_query)."""

import pytest
from sator.wikidata import _clean_query, get_wikidata_original_lang


class TestCleanQuery:
    """Tests for _clean_query noise word removal."""

    @pytest.mark.parametrize("raw,expected", [
        ("Lost Complete Series", "lost"),
        ("Game of Thrones S01", "game of thrones"),
        ("The Matrix 1999 1080p BluRay x265", "the matrix 1999"),
        ("Inception 2010 MULTi 1080p", "inception 2010"),
        ("Interstellar 4K UHD", "interstellar"),
        ("The.Wire.S01.1080p.BluRay.x264", "the.wire...."),
        ("", ""),
        ("Pure Title", "pure title"),
        ("FLUX release group", "release group"),  # FLUX stripped
        ("Complete Series", "Complete Series"),   # fallback to raw
        ("  spaces   and  noise  here  ", "spaces and noise here"),
        (r"John\ wick\ \(2014\)", "john wick (2014)"),
    ])
    def test_clean_query(self, raw, expected):
        assert _clean_query(raw) == expected


def test_language_found_without_english_wikipedia_page(monkeypatch, tmp_path):
    calls = []

    def fake_api(params, deadline):
        calls.append(params['action'])
        if params['action'] == 'wbsearchentities':
            return {'search': [{'id': 'Q136482125', 'label': 'Slide',
                                'description': '2023 film directed by Bill Plympton'}]}
        return {'entities': {'Q136482125': {
            'labels': {'en': {'value': 'Slide'}},
            'descriptions': {'en': {'value': '2023 film directed by Bill Plympton'}},
            'claims': {
                'P577': [{'mainsnak': {'datavalue': {'value': {'time': '+2023-01-01T00:00:00Z'}}}}],
                'P364': [{'mainsnak': {'datavalue': {'value': {'id': 'Q1860'}}}}],
            },
        }}}

    monkeypatch.setattr('sator.wikidata._wikidata_api', fake_api)
    cache = str(tmp_path / 'langs.json')
    assert get_wikidata_original_lang('Slide 2023', cache) == 'en'
    assert get_wikidata_original_lang('Slide 2023', cache) == 'en'
    assert calls == ['wbsearchentities', 'wbgetentities']


def test_language_lookup_rejects_wrong_release_year(monkeypatch):
    def fake_api(params, deadline):
        if params['action'] == 'wbsearchentities':
            return {'search': [{'id': 'Q1', 'label': 'Slide',
                                'description': '2000 film'}]}
        if params['action'] == 'query':
            return {'query': {'search': [{'title': 'Q1'}]}}
        return {'entities': {'Q1': {
            'labels': {'en': {'value': 'Slide'}},
            'descriptions': {'en': {'value': '2000 film'}},
            'claims': {'P364': [{'mainsnak': {'datavalue': {'value': {'id': 'Q1860'}}}}]},
        }}}

    monkeypatch.setattr('sator.wikidata._wikidata_api', fake_api)
    assert get_wikidata_original_lang('Slide 2023') == ''
