#!/usr/bin/env python3
"""Tests for Wikidata helpers (_clean_query)."""

import pytest
from sator.wikidata import _clean_query


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
    ])
    def test_clean_query(self, raw, expected):
        assert _clean_query(raw) == expected
