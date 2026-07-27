"""Tests for modifier parsing in quality.py."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.quality import parse_quality, QualityInfo, strip_modifiers


# ── Modifier detection ──────────────────────────────────────────────────────

def test_no_modifiers():
    qi = parse_quality('Show.S01E01.1080p.WEB-DL.FLUX.mkv')
    assert qi.modifiers == []


def test_extended_modifier():
    qi = parse_quality('Movie.Extended.1080p.BluRay.FLUX.mkv')
    assert 'Extended' in qi.modifiers


def test_extended_cut_modifier():
    qi = parse_quality('Movie.Extended.Cut.1080p.BluRay.FLUX.mkv')
    assert 'Extended Cut' in qi.modifiers or 'Extended' in qi.modifiers


def test_directors_cut_modifier():
    qi = parse_quality("Movie.Director's.Cut.1080p.BluRay.FLUX.mkv")
    assert 'Director\'s Cut' in qi.modifiers


def test_dc_abbreviation():
    qi = parse_quality('Movie.DC.1080p.BluRay.FLUX.mkv')
    assert 'DC' in qi.modifiers


def test_unrated_modifier():
    qi = parse_quality('Movie.Unrated.1080p.BluRay.FLUX.mkv')
    assert 'Unrated' in qi.modifiers


def test_remastered_modifier():
    qi = parse_quality('Movie.Remastered.1080p.BluRay.FLUX.mkv')
    assert 'Remastered' in qi.modifiers


def test_proper_modifier():
    qi = parse_quality('Show.S01E01.1080p.WEB-DL.FLUX.PROPER.mkv')
    assert 'Proper' in qi.modifiers


def test_multiple_modifiers():
    qi = parse_quality('Movie.Extended.Unrated.1080p.BluRay.FLUX.mkv')
    assert 'Extended' in qi.modifiers
    assert 'Unrated' in qi.modifiers


def test_imax_modifier():
    qi = parse_quality('Movie.IMAX.1080p.BluRay.FLUX.mkv')
    assert 'IMAX' in qi.modifiers


def test_uhd_not_modifier():
    """UHD is a resolution marker, not a modifier."""
    qi = parse_quality('Movie.2160p.UHD.BluRay.FLUX.mkv')
    # UHD should not be in modifiers list
    assert 'UHD' not in qi.modifiers


# ── strip_modifiers ─────────────────────────────────────────────────────────

def test_strip_modifiers_removes_them():
    result = strip_modifiers('Show Extended Unrated 1080p')
    assert 'Extended' not in result
    assert 'Unrated' not in result


def test_strip_modifiers_keeps_rest():
    result = strip_modifiers('Show 1080p WEB-DL FLUX')
    assert 'Show' in result
    assert '1080p' in result  # only modifiers are stripped, not quality tokens


# ── Quality label includes modifiers ────────────────────────────────────────

def test_quality_label_includes_modifiers():
    qi = parse_quality('Movie.Extended.Unrated.1080p.BluRay.FLUX.mkv')
    assert 'Extended' in qi.quality_label or 'Unrated' in qi.quality_label
