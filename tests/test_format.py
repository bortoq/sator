"""Tests for -o output format and -a file parsing."""

import sys
import os
import tempfile
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.cli import _parse_sator_file


# ── _parse_sator_file (replaces _parse_magnet_file) ─────────────────────────

def test_parse_sator_file_basic():
    """Parse well-formed sator file (backward-compat: magnets only)."""
    content = """\
# [tpb] Seven Samurai 1954 1080p
# Size: 3.2 GiB | BluRay 1080p x264 | seeders: 0
magnet:?xt=urn:btih:aaa&...

# [nyaa] Some torrent
# Size: 1.0 GiB | WEB 720p | seeders: 5
magnet:?xt=urn:btih:bbb&...
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(content)
        path = f.name
    try:
        result = _parse_sator_file(path)
        assert len(result) == 2, f"Expected 2 entries, got {len(result)}"
        assert result[0]['magnet'] == 'magnet:?xt=urn:btih:aaa&...'
        assert result[1]['magnet'] == 'magnet:?xt=urn:btih:bbb&...'
    finally:
        os.unlink(path)


def test_parse_sator_file_with_meta():
    """Parse file with Meta: lines."""
    content = """\
# [tpb] Rick and Morty S09E04
# Size: 1.2 GiB | WEB-DL 1080p | seeders: 50
# Meta: {"show_name": "Rick and Morty", "season": 9, "episode": 4}
magnet:?xt=urn:btih:aaa
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(content)
        path = f.name
    try:
        result = _parse_sator_file(path)
        assert len(result) == 1
        assert result[0]['magnet'] == 'magnet:?xt=urn:btih:aaa'
        assert result[0]['show_name'] == 'Rick and Morty'
        assert result[0]['season'] == 9
        assert result[0]['episode'] == 4
    finally:
        os.unlink(path)


def test_parse_sator_file_with_normalized():
    """Parse file with Normalized: and Meta: lines."""
    content = """\
# [tpb] Rick and Morty S09E04
# Size: 1.2 GiB | WEB-DL 1080p | seeders: 50
# Normalized: Rick and Morty - S09E04 [WEB-DL 1080p].mkv
# Meta: {"show_name": "Rick and Morty", "season": 9, "episode": 4, "normalized": "Rick and Morty - S09E04 [WEB-DL 1080p].mkv"}
magnet:?xt=urn:btih:aaa
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(content)
        path = f.name
    try:
        result = _parse_sator_file(path)
        assert len(result) == 1
        assert result[0]['normalized'] == 'Rick and Morty - S09E04 [WEB-DL 1080p].mkv'
    finally:
        os.unlink(path)


def test_parse_sator_file_empty():
    """Empty file yields empty list."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write('')
        path = f.name
    try:
        result = _parse_sator_file(path)
        assert result == []
    finally:
        os.unlink(path)


def test_parse_sator_file_only_comments():
    """File with only comments yields empty list."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write('# just a comment\n# another\n')
        path = f.name
    try:
        result = _parse_sator_file(path)
        assert result == []
    finally:
        os.unlink(path)


def test_parse_sator_file_unexpected_line():
    """Non-comment, non-magnet line raises ValueError."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write('garbage line\n')
        path = f.name
    try:
        import pytest
        with pytest.raises(ValueError, match='garbage'):
            _parse_sator_file(path)
    finally:
        os.unlink(path)


def test_parse_sator_file_not_found():
    """Non-existent file exits with code 1."""
    import subprocess
    code = subprocess.call([sys.executable, '-c', '''
import sys
sys.path.insert(0, ".")
from sator.cli import _parse_sator_file
try:
    _parse_sator_file("/nonexistent/file.txt")
except SystemExit as e:
    sys.exit(e.code)
'''])
    assert code == 1, f"Expected exit 1, got {code}"


def test_parse_sator_file_meta_only_applies_to_next_magnet():
    """Meta line only applies to immediately following magnet."""
    content = """\
# Meta: {"show_name": "Show A", "season": 1, "episode": 2}
magnet:?xt=urn:btih:aaa
# Meta: {"show_name": "Show B", "season": 3, "episode": 4}
magnet:?xt=urn:btih:bbb
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(content)
        path = f.name
    try:
        result = _parse_sator_file(path)
        assert len(result) == 2
        assert result[0]['show_name'] == 'Show A'
        assert result[1]['show_name'] == 'Show B'
    finally:
        os.unlink(path)
