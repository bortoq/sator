"""Tests for exclude/blacklist module."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.exclude import is_excluded, _DEFAULT_EXCLUDES


def test_default_excludes_loaded():
    """_DEFAULT_EXCLUDES should contain known low-quality patterns."""
    assert 'CAM' in _DEFAULT_EXCLUDES
    assert 'TS' in _DEFAULT_EXCLUDES
    assert 'SCR' in _DEFAULT_EXCLUDES


def test_exclude_short_pattern_token_match():
    """Short patterns (<5 chars) match as word tokens."""
    assert is_excluded('Movie.Name.2019.CAM.1080p', ['CAM'])
    assert is_excluded('Movie 2022 TS READNFO', ['TS'])
    assert is_excluded('Avatar-2009-SCR-DVDRip', ['SCR'])
    assert is_excluded('The.Matrix.1999.HDCAM.Rip', ['HDCAM'])


def test_exclude_long_pattern_substring():
    """Long patterns (5+ chars) match as substring."""
    assert is_excluded('TELESYNC Movie 2022', ['TELESYNC'])
    assert is_excluded('Movie 2022 DVDSCR x264', ['DVDSCR'])
    assert is_excluded('SUBBED Movie 2022', ['SUBBED'])


def test_exclude_case_insensitive():
    """Pattern matching is case-insensitive."""
    assert is_excluded('movie cam 2022', ['cam'])
    assert is_excluded('MOVIE CAM 2022', ['cam'])
    assert is_excluded('Movie CAM 2022', ['Cam'])


def test_exclude_no_match():
    """Clean title should not match any exclude pattern."""
    assert not is_excluded('Movie.2022.1080p.BluRay.x264-FLUX', ['CAM', 'TS'])
    assert not is_excluded('The.Matrix.1999.1080p.WEB-DL', ['CAM', 'TS', 'SCR'])
    assert not is_excluded('正常电影 2022', ['CAM', 'TS'])


def test_exclude_multiple_patterns():
    """Multiple exclude patterns - match any."""
    assert is_excluded('Movie CAM', ['TS', 'CAM', 'SCR'])
    assert not is_excluded('Movie WEB-DL', ['TS', 'CAM', 'SCR'])


def test_exclude_empty_patterns():
    """Empty patterns list should never exclude."""
    assert not is_excluded('Movie CAM 2022', [])


def test_exclude_empty_title():
    """Empty title with patterns."""
    assert not is_excluded('', ['CAM', 'TS'])
