# Changelog

## v0.4.0 (2026-07-27)

### Breaking Changes

- **`-f` / `--file` flag removed**. File input is now auto-detected: `sator -s queries.txt`
  checks if the argument is an existing file and reads it line-by-line.
- **Defaults changed to "disabled"**: `-rl`, `-rb`, `-zl`, `-zb` default to `0` (no filter).
  Previously they defaulted to 480p–1080p / 200 MiB–8 GiB.
- **`--tags` now uses `nargs='+'`** (space-separated) instead of a single comma-separated string.
  Usage: `--tag1 tag2` (was `--tags "tag1,tag2"`).
- **`-t` accepts optional argument**: `-t` without value auto-detects original-language subtitles
  (same behaviour as `-l`).
- **`-s`/`--string` renamed to `-s`/`--search`** (old `--string` still accepted for compat).
- **`DEFAULT_TRACKERS` expanded** from `['nyaa', 'tpb']` to include 4 new working indexers.

### Features

- **Centralised settings module** (`sator/settings.py`): all defaults, scoring constants,
  timeouts, URLs, and paths in one place.
- **4 new tracker indexers**:
  - YourBittorrent (JSON API)
  - TorrentFunk (JSON API)
  - Magnetz (JSON API)
  - GloTorrents (HTML scrape)
- **SolidTorrents indexer fixed**: API domain `.net` → `.to`, field names `name`/`magnet`
  → `title`/`infohash`.
- **Fallback mechanism**: if no results pass filters, the best filtered-out candidate(s)
  are returned with a `FALLBACK_PENALTY` subtracted from score.
- **Fallback + `-a`**: fallback torrents auto-added in **paused** state (`paused=true`
  in qBittorrent API). User can review and resume or delete without wasting bandwidth.
- **Series expansion** (`-sn`): auto-expand season/episode ranges into individual queries.
- **Wikidata search improved**: tries plain → film → TV series query order; relevance filter
  skips unrelated Wikipedia pages. Baskin (2015) now correctly resolves to Turkish.
- **Scoring fix**: `_quality` dict now correctly injected into torrent results, source/resolution
  scoring actually works.

### Bug Fixes

- **BUG-9**: NyaaIndexer and TGxIndexer used `TIMEOUT_EZTV` instead of their own timeout constants.
- **BUG-10**: Fallback torrents auto-added with `-a` are now added in **paused** state.
- **MINOR-1**: Magnetz/GloTorrents/YB/TF now use dedicated timeout constants.
- **Output file** (`-o`) is always truncated on open, preventing stale data.
- **KeyboardInterrupt** handled gracefully (exit code 130) instead of raw traceback.
- **`-m` sort order**: 0-seeder results always sorted to bottom regardless of score.
- **LimeTorrents, KickAssTorrents, 1337x, Bitsearch removed** (blocked/broken).

### Documentation

- **README fully rewritten**: all 12 errors from v0.3 audit fixed.
  - `-f` → `-s` in all examples.
  - Defaults documented as `0 (disabled)`.
  - Default trackers: all 6 listed.
  - Test count: 96.
  - New flags: `-sn`, `--no-enrich`, fallback, `-t` without arg.
- **`__version__` bumped to `0.4.0`** (semver-compliant).
- **`__init__.py` exports**: all indexer classes + `expand_series_queries`.
- **`indexer.py` docstring** lists all 11 indexers.

### Removed

- Bitsearch (JS-rendered, no results from HTML).
- KickAssTorrents (Cloudflare 403).
- 1337x (Cloudflare 403).
- `DEFAULTS` dict from `cli.py` (replaced by `settings.py`).


## Unreleased

### Features
- **Episode-level expansion**: When `-sn` specifies a season (e.g. `-sn 1`), sator now:
  - Looks up episode count from Wikidata (Wikipedia, no API key required)
  - Generates per-episode queries: `S01E01` .. `S01E{N}`
  - Searches both pack and individual episodes across all trackers
  - Compares pack vs episodes: chooses the option with better seeders
  - Auto-tags episodes with `series:{show-name}` when using `-a`
  - Caches episode counts in `~/.cache/sator/seriess.json`

### CLI
- **`--no-episode-expansion`**: Disable automatic episode-level expansion, search pack only.
- **`-n` / `--normalize`**: Opt-in file name normalisation for torrents added to qBittorrent.
  Renames files according to configurable templates (separate for movies and series) and
  writes a sidecar `{torrent}.orig.json` mapping original → new names.

### Quality Parser
- **Modifier detection**: Extended, Director's Cut, Unrated, Remastered, IMAX, Proper, Internal,
  and 20+ other edition/cut indicators are now parsed from release titles and exposed in
  `QualityInfo.modifiers`.

### Settings
- **`TEMPLATE_MOVIE`**: Default `'{title} ({year}) [{quality}] [{group}].{ext}'`
- **`TEMPLATE_SERIES`**: Default `'{show} - S{season:02d}E{episode:02d} [{quality}].{ext}'`
- Available placeholders: `{title}`, `{show}`, `{year}`, `{season}`, `{episode}`,
  `{quality}`, `{resolution}`, `{source}`, `{codec}`, `{audio}`, `{hdr}`,
  `{group}`, `{mod}`, `{ext}`.

### TMDB
- **`get_season_episode_titles()`**: Fetch episode names from TMDB for a given
  show + season. Used when ``-n`` normalizes series files — ``{ep_title}``
  placeholder is populated with the real episode name.
- **`get_tv_show_id()`**: Search TMDB for a TV show, return its TMDB ID.
- **Disk cache**: Episode titles cached in ``~/.cache/sator/episodes.json``
  to avoid redundant API calls.
- **Key sources** (in order): ``--tmdb-key KEY`` > ``tmdb_key`` in config file
  (``~/.config/sator/config``). Register at https://www.themoviedb.org/settings/api.

### Normalize + TMDB integration
- When ``-n`` + ``-sn``, sator pre-fetches episode titles from TMDB and passes
  ``{ep_title}`` into the series template. Titles are matched by episode number
  extracted from each file name (or from the ``-sn`` context).

### Internal
- **`sator/normalizer.py`**: New module with `compute_new_name()`, `write_sidecar()`,
  `build_sidecar()`, `_clean_show_name()`, `_parse_season_episode()`.
- **QBClient.rename_file()**: Rename a single file in an existing torrent.
- **QBClient.get_torrent_files()**: List files for a given torrent hash.
- **QBClient.rename_folder()**: Rename a folder inside a torrent.


### Fixed

- **`_qb_add_simple` no longer swallows errors**: returns `bool`, logs exception to stderr.
- **process.py counters now accurate**: `added` is only incremented when `_qb_add_simple` returns `True`.
- **cli.py episode-expansion no longer adds to qB prematurely**: pack and episode queries skip qB-add
  during the search loop; addition happens only after `pick_series_best()` decides the winner.
- **cli.py pack-win branch now adds to qB**: previously the pack was only counted, never sent to qB
  (it was added prematurely inside `_process_query_internal` before the fix).
- **cli.py episode-win branch no longer double-adds**: each episode magnet is sent to qB exactly once,
  with return-value check.
- **cli.py direct-download mode** (`-a file`): checks `_qb_add_simple` return before incrementing counter.
- **Normalization tracking** now conditional on successful qB add.

### Tests
- **14 new tests** for modifier parsing (`test_quality_modifiers.py`).
- **18 new tests** for normalizer (`test_normalizer.py`).
- **7 new tests** for TMDB episode titles (`test_tmdb_episodes.py`).
- Total: 147 tests (all passing).
