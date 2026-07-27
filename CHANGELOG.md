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

