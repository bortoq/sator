"""Test CLI argument handling."""
import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.cli import _main, _parse_cmd_run_args, cmd_run


@pytest.mark.parametrize('args', [
    ['Slide 2023', '-m', '-o', 'o'],
    ['-m', '-o', 'o', 'Slide 2023'],
    ['-a', 'Slide 2023'],
    ['-sn', '1', 'Slide 2023', '-m'],
    ['-l', 'Slide 2023', '-m'],
])
def test_query_position_is_independent_of_options(args):
    parsed, _ = _parse_cmd_run_args(args)
    assert parsed.search_strings == ['Slide 2023']


def test_season_numbers_do_not_consume_query():
    parsed, _ = _parse_cmd_run_args(['-sn', '1', '2', 'Slide 2023'])
    assert parsed.season_number == [['1', '2']]
    assert parsed.search_strings == ['Slide 2023']


def test_removed_search_flag_is_rejected(capsys):
    with pytest.raises(SystemExit) as exc:
        _parse_cmd_run_args(['-s', 'Slide 2023'])
    assert exc.value.code == 2
    assert 'was removed' in capsys.readouterr().err


def test_legacy_add_file_still_works(tmp_path):
    magnets = tmp_path / 'magnets.txt'
    magnets.write_text('magnet:?xt=urn:btih:' + 'a' * 40)
    parsed, _ = _parse_cmd_run_args(['-a', str(magnets)])
    assert parsed.add_file == str(magnets)
    assert parsed.search_strings == []


def test_auto_add_before_query_file_keeps_search_mode(tmp_path):
    queries = tmp_path / 'queries.txt'
    queries.write_text('Slide 2023\n')
    parsed, _ = _parse_cmd_run_args(['-a', str(queries)])
    assert parsed.add_file == ''
    assert parsed.search_strings == [str(queries)]


def test_add_file_cannot_bypass_more_mode(monkeypatch, tmp_path):
    magnets = tmp_path / 'magnets.txt'
    magnets.write_text('magnet:?xt=urn:btih:' + 'a' * 40)
    monkeypatch.setattr('sator.cli._direct_download_mode',
                        lambda *args: pytest.fail('must not add torrents'))
    with pytest.raises(SystemExit) as exc:
        cmd_run(['--add-file', str(magnets), '-m'])
    assert exc.value.code == 2


def test_add_file_cannot_be_silently_ignored_for_search(tmp_path):
    magnets = tmp_path / 'magnets.txt'
    magnets.write_text('magnet:?xt=urn:btih:' + 'a' * 40)
    with pytest.raises(SystemExit) as exc:
        cmd_run(['--add-file', str(magnets), 'Slide 2023'])
    assert exc.value.code == 2


def test_main_treats_non_command_as_positional_query(monkeypatch):
    seen = {}

    monkeypatch.setattr('sator.cli.sys.argv', ['sator', 'Slide 2023', '-m', '-o', 'o'])
    monkeypatch.setattr('sator.cli.cmd_run', lambda args: seen.setdefault('args', args))

    _main()

    assert seen['args'] == ['Slide 2023', '-m', '-o', 'o']


def test_more_ignores_auto_add_and_cleans_quoted_query(monkeypatch, capsys):
    seen = {}

    def fake_build(parsed):
        seen['query'] = parsed.search_strings[0]
        return [seen['query']], {}, {}, '/tmp'

    def fake_run(parsed, queries, series_meta, series_plan, tags, auto_add,
                 lang_filters, subs_filters, orig_lang_map, has_original_subs):
        seen['auto_add'] = auto_add
        return {'found_count': 0, 'added_count': 0, 'total_size': 0,
                'all_torrents': [], 'not_found_items': [], 'start_time': 0}

    monkeypatch.setattr('sator.cli._build_queries', fake_build)
    monkeypatch.setattr('sator.cli.get_wikidata_original_lang', lambda *args, **kwargs: 'en')
    monkeypatch.setattr('sator.cli._run_search', fake_run)

    cmd_run([r'John\ wick\ \(2014\)', '-a', '-m'])

    assert seen == {'query': 'John wick (2014)', 'auto_add': False}
    assert '-a is ignored with -m' in capsys.readouterr().err


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
        cmd_run(['-help', 'test'])
    except SystemExit as e:
        assert e.code == 0, f'-help with args should exit 0, got {e.code}'
    except Exception as exc:
        raise AssertionError('-help must not mask a CLI error') from exc
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
