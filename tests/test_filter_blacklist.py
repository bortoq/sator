"""Tests for blacklist filtering in filter_result_json."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.filter import filter_result_json


def _make_result(title='Test Movie 2022 1080p', size_bytes=4_000_000_000):
    return {
        'title': title,
        'size_bytes': size_bytes,
        'seeders': 50,
        'source': 'tpb',
        'magnet': 'magnet:?xt=urn:btih:test',
    }


def test_blacklist_cam_is_excluded():
    """CAM pattern should be excluded."""
    r = _make_result(title='Movie.CAM.2022.1080p')
    assert filter_result_json(r, {'excludes': ['CAM']}) is None


def test_blacklist_ts_is_excluded():
    """TS pattern should be excluded."""
    r = _make_result(title='Movie.2022.TS.READNFO')
    assert filter_result_json(r, {'excludes': ['TS']}) is None


def test_blacklist_clean_title_passes():
    """Clean title should pass blacklist."""
    r = _make_result(title='Movie.2022.1080p.BluRay.x264-FLUX')
    result = filter_result_json(r, {'excludes': ['CAM', 'TS', 'SCR']})
    assert result is not None


def test_blacklist_empty_excludes_passes():
    """Empty excludes list should not filter anything."""
    r = _make_result(title='Movie.CAM.2022')
    assert filter_result_json(r, {'excludes': []}) is not None


def test_blacklist_no_excludes_key():
    """No excludes key in filters should not filter."""
    r = _make_result(title='Movie.CAM.2022')
    assert filter_result_json(r, {}) is not None


def test_blacklist_with_resolution_filter():
    """Blacklist + resolution filter work together."""
    r = _make_result(title='Movie.CAM.2022.1080p')
    # Should be excluded by blacklist first
    assert filter_result_json(r, {'excludes': ['CAM'], 'rl': 720}) is None
    
    # Clean title should still respect resolution filter
    r2 = _make_result(title='Movie.2022.1080p.BluRay')
    assert filter_result_json(r2, {'excludes': ['CAM'], 'rl': 720}) is None
