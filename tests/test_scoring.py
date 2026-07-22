"""Tests for scoring and best-mode selection."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.process import _score_result


def test_score_seeders():
    """Seeders contribute to score (capped at 100)."""
    t1 = {'seeders': 50, 'size_bytes': 1, 'title': 'Test',
          '_quality': {'source': '', 'resolution': 0}}
    t2 = {'seeders': 200, 'size_bytes': 1, 'title': 'Test',
          '_quality': {'source': '', 'resolution': 0}}
    
    s1 = _score_result(t1)
    s2 = _score_result(t2)
    assert s2 > s1, "More seeders should score higher"
    assert s1 == 50.0, f"Expected 50.0, got {s1}"
    assert s2 == 100.0, f"Expected 100.0 (capped), got {s2}"


def test_score_source():
    """Source quality contributes to score."""
    t_base = {'seeders': 0, 'size_bytes': 1, 'title': 'Test',
              '_quality': {'resolution': 0}}
    
    t_bluray = {**t_base, '_quality': {'source': 'BluRay', 'resolution': 0}}
    t_webdl = {**t_base, '_quality': {'source': 'WEB-DL', 'resolution': 0}}
    t_hdtv = {**t_base, '_quality': {'source': 'HDTV', 'resolution': 0}}
    
    assert _score_result(t_bluray) > _score_result(t_webdl)
    assert _score_result(t_webdl) > _score_result(t_hdtv)


def test_score_resolution_match():
    """Preferred resolution (1080p) gets bonus."""
    t_base = {'seeders': 0, 'size_bytes': 1, 'title': 'Test',
              '_quality': {'source': ''}}
    
    t_1080 = {**t_base, '_quality': {'source': '', 'resolution': 1080}}
    t_720 = {**t_base, '_quality': {'source': '', 'resolution': 720}}
    t_2160 = {**t_base, '_quality': {'source': '', 'resolution': 2160}}
    
    assert _score_result(t_1080) > _score_result(t_720)
    assert _score_result(t_1080) > _score_result(t_2160)


def test_score_trusted_group():
    """Trusted release groups get bonus."""
    t_base = {'seeders': 0, 'size_bytes': 1,
              '_quality': {'source': '', 'resolution': 0}}
    
    t_flux = {**t_base, 'title': 'Movie.2022.1080p.FLUX'}
    t_ntb = {**t_base, 'title': 'Movie.2022.1080p.NTb'}
    t_unknown = {**t_base, 'title': 'Movie.2022.1080p.UNKNOWN'}
    
    assert _score_result(t_flux) > _score_result(t_unknown)
    assert _score_result(t_ntb) > _score_result(t_unknown)


def test_score_size_range():
    """Reasonable size (1-15 GB) gets bonus."""
    t_base = {'seeders': 0, 'title': 'Test',
              '_quality': {'source': '', 'resolution': 0}}
    
    t_small = {**t_base, 'size_bytes': 500_000_000}   # 0.5 GB
    t_good  = {**t_base, 'size_bytes': 4_000_000_000}  # 4 GB
    t_large = {**t_base, 'size_bytes': 20_000_000_000} # 20 GB
    
    assert _score_result(t_good) > _score_result(t_small)
    assert _score_result(t_good) > _score_result(t_large)


def test_score_bad_source_penalty():
    """Bad sources (CAM, TS) should have negative scores."""
    t_cam = {'seeders': 0, 'size_bytes': 1, 'title': 'Movie.CAM',
             '_quality': {'source': 'CAM', 'resolution': 0}}
    t_ts = {'seeders': 0, 'size_bytes': 1, 'title': 'Movie.TS',
            '_quality': {'source': 'TELESYNC', 'resolution': 0}}
    
    assert _score_result(t_cam) < 0
    assert _score_result(t_ts) < 0


def test_score_quality_beats_seeders():
    """A quality release should beat a CAM with many seeders."""
    t_ok = {'seeders': 10, 'size_bytes': 4_000_000_000,
            'title': 'Movie.2022.1080p.BluRay.x264-GROUP',
            '_quality': {'source': 'BluRay', 'resolution': 1080}}
    
    t_cam = {'seeders': 100, 'size_bytes': 500_000_000,
             'title': 'Movie.2022.CAM.READNFO',
             '_quality': {'source': 'CAM', 'resolution': 0}}
    
    assert _score_result(t_ok) > _score_result(t_cam), \
        "Quality release should outrank CAM despite fewer seeders"


def test_score_missing_fields():
    """Missing fields should not crash."""
    t = {'title': 'Test'}
    score = _score_result(t)
    assert isinstance(score, float)
    assert score >= 0
