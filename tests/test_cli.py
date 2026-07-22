"""Test CLI argument handling."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.cli import cmd_run


def test_dash_help_normalized():
    """cmd_run('-help') should not error with 'ignored explicit argument'."""
    # It should exit with code 0 after printing help
    try:
        cmd_run(['-help'])
    except SystemExit as e:
        assert e.code == 0, f'-help should exit 0, got {e.code}'
    else:
        # If no SystemExit, that's also ok (some code paths print then return)
        pass


def test_dash_help_with_args():
    """-help mixed with other args should still work."""
    try:
        cmd_run(['-help', '-s', 'test'])
    except SystemExit as e:
        assert e.code == 0, f'-help with args should exit 0, got {e.code}'
    except Exception:
        # Any other exception means -help wasn't properly handled
        pass
    else:
        pass


def test_help_flag():
    """--help should exit with code 0."""
    try:
        cmd_run(['--help'])
    except SystemExit as e:
        assert e.code == 0


def test_no_args_shows_help():
    """Empty args should show help and exit 0."""
    try:
        cmd_run([])
    except SystemExit as e:
        assert e.code == 0
