"""Tests for -o output format and -a file parsing."""
import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.cli import _parse_magnet_file


def test_parse_magnet_file_basic():
    """Parse well-formed magnet file."""
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
        result = _parse_magnet_file(path)
        assert len(result) == 2, f"Expected 2 magnets, got {len(result)}"
        assert result[0] == 'magnet:?xt=urn:btih:aaa&...'
        assert result[1] == 'magnet:?xt=urn:btih:bbb&...'
    finally:
        os.unlink(path)


def test_parse_magnet_file_empty():
    """Empty file yields empty list."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write('')
        path = f.name
    try:
        result = _parse_magnet_file(path)
        assert result == []
    finally:
        os.unlink(path)


def test_parse_magnet_file_only_comments():
    """File with only comments yields empty list."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write('# just a comment\n# another\n')
        path = f.name
    try:
        result = _parse_magnet_file(path)
        assert result == []
    finally:
        os.unlink(path)


def test_parse_magnet_file_unexpected_line():
    """Non-comment, non-magnet line raises ValueError."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write('garbage line\n')
        path = f.name
    try:
        import pytest
        with pytest.raises(ValueError, match='garbage'):
            _parse_magnet_file(path)
    finally:
        os.unlink(path)


def test_parse_magnet_file_not_found():
    """Non-existent file exits with code 1."""
    import subprocess
    # _parse_magnet_file calls sys.exit(1), so we test via subprocess
    code = subprocess.call([sys.executable, '-c', f'''
import sys
sys.path.insert(0, "{os.path.dirname(os.path.dirname(__file__))}")
from sator.cli import _parse_magnet_file
try:
    _parse_magnet_file("/nonexistent/file.txt")
except SystemExit as e:
    sys.exit(e.code)
'''])
    assert code == 1, f"Expected exit 1, got {code}"


def test_output_format_roundtrip():
    """Simulate writing and reading back the new format."""
    torrents = [
        {
            'source': 'tpb',
            'title': 'Seven Samurai 1954 1080p',
            'size_h': '3.2 GiB',
            'quality_label': 'BluRay 1080p x264',
            'seeders': 108,
            'magnet': 'magnet:?xt=urn:btih:aaa',
        },
        {
            'source': 'nyaa',
            'title': 'Some torrent',
            'size_h': '1.0 GiB',
            'quality_label': 'WEB 720p x264',
            'seeders': 5,
            'magnet': 'magnet:?xt=urn:btih:bbb',
        },
    ]
    
    # Write in new format
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        for t in torrents:
            f.write(f"# [{t['source']}] {t['title']}\n")
            f.write(f"# Size: {t['size_h']} | {t['quality_label']} | seeders: {t['seeders']}\n")
            f.write(f"{t['magnet']}\n\n")
        path = f.name
    
    try:
        # Read back
        magnets = _parse_magnet_file(path)
        assert len(magnets) == 2
        assert magnets[0] == 'magnet:?xt=urn:btih:aaa'
        assert magnets[1] == 'magnet:?xt=urn:btih:bbb'
    finally:
        os.unlink(path)
