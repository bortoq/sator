# sator — Search And TORrent

Multi-tracker torrent search and filtering tool with qBittorrent integration.

```
sator -s "Rick and Morty S07" -o results.url
sator -s queries.txt -a                                          # search + auto-add
sator -s queries.txt -v                                          # show all results with details
sator -a downloads.txt                                           # add magnets from file
```

## Features

- **11 torrent trackers**: Nyaa, TPB, YTS, SolidTorrents, EZTV, TorrentGalaxy (TGx), LimeTorrents (blocked), YourBittorrent, TorrentFunk, Magnetz, GloTorrents
- **Filter pipeline**: resolution bounds, size bounds, language, subtitles, blacklist
- **Language detection**: title parsing + Wikidata auto-detect (original language)
- **Detail page enrichment**: scrapes metadata when title lacks language/subtitle info
- **Best-mode**: scores and selects best result per query (default). Use `-m` to show all results
- **Fallback**: when no results pass filters, returns best filtered-out item (in **paused** state when auto-adding)
- **Verbose output** (`-v`): shows all results including filtered-out (with reason)
- **qBittorrent integration** (`-a`): auto-add found torrents
- **Blacklist**: built-in exclusion of CAM/TS/scrubbed releases
- **Tracker selection** (`-T`): restrict which trackers to search
- **Output file** (`-o FILE`): write magnets/URLs (suppress screen spam)
- **Series expansion** (`-sn`): auto-expand season/episode ranges into individual queries
- **Sub-commands**: `run`, `help`

## Install

```bash
pip install git+https://github.com/bortoq/sator.git
```

Or set up for development:

```bash
git clone https://github.com/bortoq/sator.git ~/work/sator
export PYTHONPATH=~/work/sator:$PYTHONPATH
alias sator='python3 -m sator.cli'
```

## Usage

### Basic search

```bash
sator -s "Rick and Morty"
sator -s "Lost Complete Series" --verbose
```

### Search with filters

```bash
# Size and resolution bounds
sator -s "Interstellar" -rl 1080 -rb 720 -zl 8g -zb 200m

# Language filters
sator -s "Amélie" -l fr                     # French audio
sator -s "Parasite" -l                      # auto-detect original language via Wikidata

# Subtitle filters (opt-in with -t)
sator -s "Amélie" -t en                     # require English subtitles
sator -s "Amélie" -t                        # auto-detect original language subtitles
sator -s "Movie" -t en -t fr                # require both English AND French subs

# Choose trackers
sator -s "Lost" -T nyaa -T yts
```

### Search series (expand season/episode ranges)

`-sn` takes only season/episode **numbers** (the title goes in `-s`).
No value = all seasons. Repeat `-sn` for multiple independent blocks.

```bash
# All episodes of season 1
sator -s "Breaking Bad" -sn 1

# All seasons (no number given)
sator -s "Breaking Bad" -sn

# Specific episodes — just list them one by one
sator -s "Game of Thrones" -sn 1 1 2 3 4 5

# Shell brace expansion works great for ranges
sator -s "Game of Thrones" -sn 1 $(echo {1..5})

# Two separate seasons
sator -s "Better Call Saul" -sn 1 -sn 3
```

### Episode-level expansion (automatic)

When `-sn` specifies a season without individual episodes (e.g. `-sn 1`),
sator automatically looks up the episode count from Wikidata (Wikipedia, no API key)
and searches for **both** the season pack and individual episodes:

```bash
sator -s "Breaking Bad" -sn 1 -a
# Searches: "Breaking Bad S01" (season pack)
#           "Breaking Bad S01E01" ... "Breaking Bad S01E07" (7 episodes)
# Compares: pack seeders vs average episode seeders
# If episodes win: adds 7 torrents, each tagged "series:breaking-bad"
# If pack wins:   adds 1 torrent
```

| Scenario | Result |
|----------|--------|
| Pack OK, all episodes found, ep seeders > pack seeders | **Episodes win** (auto-tagged) |
| Pack OK, all episodes found, pack seeders >= ep seeders | **Pack wins** |
| Pack OK, some episodes missing | **Pack wins** |
| Pack empty, all episodes found | **Episodes win** |
| Wikidata has no data for this series | **Pack only** (fallback, no expansion) |

Disable with `--no-episode-expansion`.

### Best-mode

Best-mode scores results and picks the best match per query:

```bash
sator -s "Lost" -m                          # show all filtered results, sorted
```

Scoring factors: seeders, resolution match, size range fit, trusted groups, source quality.

### File input

```bash
sator -s queries.txt                        # one query per line, output to stdout
sator -s queries.txt -o results.url         # write results to file
```

When the argument to `-s` is an existing file, it is read line-by-line.

### Auto-add to qBittorrent

```bash
sator -s "Rick and Morty S07" -a
```

qBittorrent must be running with WebUI enabled at `http://localhost:8090/`.

Fallback results (torrents that did not pass filters) are added in **paused** state — you can review and resume or delete them without wasting bandwidth.

### Sub-command: run

```bash
sator run -s "Lost" -o lost.url
```

The `run` sub-command is the default; all flags work identically.

### Real-world examples

```bash
# Batch process your watchlist: search for multiple movies, pick best per query,
# write magnets to file for later import
sator -s watchlist.txt -o favorites.url -rl 1080 -l __original__ -t en

# Find 4K HDR content with English audio and subtitles, auto-add to qBittorrent
sator -s "Dune 2021" -rl 2160 -rb 2160 -l en -t en -a --tags "4K movies"

# Search for a TV series season across all trackers, show all results sorted by score
sator -s "Severance" -sn 2 -m                                    # search one season

# Exclude dubbed/multi-audio releases and prefer BluRay source
sator -s "The Matrix" -e MULTi,DUAL -rl 1080

# Quick check: what's available for a query? Verbose mode shows filtered-out too
sator -s "Interstellar 4K" -v

# Nightly cron job: process a list of wanted movies, auto-add best matches,
# adding in paused state if fallback kicks in
sator -s /path/to/wanted.txt -a --tags "automated" -o /tmp/last_run.url

# Import existing magnet links from a file into qBittorrent
sator -a ~/Downloads/magnets.txt
```

## Options

### Resolution bounds (each at most once)

| Flag | Default | Description |
|------|---------|-------------|
| `-rl <res>` | 0 (disabled) | Upper bound, e.g. `2160`, `1080`, `720` |
| `-rb <res>` | 0 (disabled) | Lower bound, e.g. `1080`, `720`, `480` |

Default is `0` (disabled) — no resolution filtering unless explicitly set.

### Size bounds (each at most once)

| Flag | Default | Description |
|------|---------|-------------|
| `-zl <size>` | 0 (disabled) | Upper bound, suffixes `k`, `m`, `g`, `t` |
| `-zb <size>` | 0 (disabled) | Lower bound, suffixes `k`, `m`, `g`, `t` |

Default is `0` (disabled) — no size filtering unless explicitly set.

### Language and subtitle filters (repeatable)

| Flag | Default | Description |
|------|---------|-------------|
| `-l [lang]` | `__original__` | Audio language (ISO 639-1 or name). No arg = Wikidata auto-detect |
| `-t [lang]` | (none) | Subtitle language (ISO 639-1 or name). No arg = auto-detect original language subtitle |

Without `-t`, subtitle filtering is disabled — all releases pass regardless of subtitle markers.
Use `-t` without a value to require subtitles matching the original language.

### Other flags

| Flag | Description |
|------|-------------|
| `-v`, `--verbose` | Show all results including filtered-out (with `✗` prefix) |
| `-tt`, `--tracker-titles` | Show tracker source per result |
| `-m`, `--more` | Show **all** filtered results instead of best-only (disable best-mode) |
| `-o FILE` | Write output to file (suppresses magnet URIs on stderr) |
| `-T TRACKER` | Restrict search to specific tracker(s). Repeatable. |
| `-sn [S] [E] ...` | Series season/episode numbers. No value = all seasons. Needs `-s` for the title |
| `--enrich` | Enable TMDB enrichment (requires `--tmdb-key`) |
| `--no-enrich` | Disable detail-page enrichment (lazy scrape of tracker pages) |
| `--no-episode-expansion` | Disable automatic episode-level expansion (`-sn` searches pack only) |
| `--tmdb-key KEY` | TMDB API key |
| `-a` | Auto-add found torrents to qBittorrent |
| `--tags TAG [TAG ...]` | Tags to apply in qBittorrent (space-separated) |
| `-e PATTERN` | Extra exclude pattern(s), comma-separated (e.g. `-e MULTi,DUAL`) |
| `-h`, `--help` | Show help |

## Trackers

| Tracker | Status | Notes |
|---------|--------|-------|
| **Nyaa** | ✅ Working | HTML scrape, anime + general |
| **TPB** | ✅ Working | Multi-mirror fallback |
| **YTS** | ✅ Working | JSON API, movies only |
| **SolidTorrents** | ✅ Working | JSON API |
| **EZTV** | ✅ Working | HTML scrape, TV shows |
| **TorrentGalaxy (TGx)** | ✅ Working | HTML scrape |
| **LimeTorrents** | ⛔ Blocked | Cloudflare-protected, kept for future use |
| **YourBittorrent** | ✅ Working | JSON API |
| **TorrentFunk** | ✅ Working | JSON API |
| **Magnetz** | ✅ Working | JSON API |
| **GloTorrents** | ✅ Working | HTML scrape |

Default trackers (when `-T` not used): `nyaa`, `tpb`, `yourbittorrent`, `torrentfunk`, `magnetz`, `glotorrents`.

## Detail Page Enrichment

When a torrent title lacks language or subtitle metadata, sator can scrape the tracker's detail page:

- Extracts audio languages and subtitle info
- Applies extracted info to the filter pipeline
- Lazy: only fetched when the result would otherwise be filtered out
- Cached: duplicate URLs fetched once per search
- Controlled by `--enrich` (requires `--tmdb-key`) and `--no-enrich` (disable)

## Blacklist

Built-in blacklist excludes releases matching any of: `CAM`, `HDCAM`, `TELESYNC`, `TS`, `SCR`, `SCREENER`, `HC`, `SUBBED`, `DVDSCR`, `R5`.

Custom exclude patterns via `-e/--exclude` (comma-separated, e.g. `-e CAM,TS,SCR`).

## Fallback Mechanism

When no results pass the filter pipeline, sator falls back to returning the best-scored filtered-out candidates:

- Torrents that failed filters get `FALLBACK_PENALTY` (500 points) subtracted from their score
- Fallback results are marked with `⚠` in display output and `_fallback: True` in JSON
- A warning is printed to stderr: `⚠ No results passed filters — returning best fallback`
- When auto-adding (`-a`), fallback torrents are added in **paused** state — review before resuming

## Scoring (best-mode)

| Factor | Weight | Description |
|--------|--------|-------------|
| Seeders | High | More seeders = higher score |
| Resolution | High | Closer to target resolution = better |
| Size range | Medium | Within size bounds |
| Trusted groups | Bonus | FLUX, NTb, DON, CtrlHD, HONE, SPARKS |
| Source quality | Score | BluRay > WEB-DL > WEBRip > HDTV > … |

## Configuration

Built-in defaults are applied when flags are not explicitly provided:

- Resolution: no filter (set `-rl`/`-rb` to enable)
- Size: no filter (set `-zl`/`-zb` to enable)
- Language: original (Wikidata auto-detect)
- Subtitles: no filter (opt-in with `-t`)
- Trackers: `nyaa`, `tpb`, `yourbittorrent`, `torrentfunk`, `magnetz`, `glotorrents`

CLI flags always override defaults.

## Development

```bash
git clone https://github.com/bortoq/sator.git
cd sator
python3 -m pytest tests/
```

96 tests covering: CLI parsing, filter pipeline, blacklist, scoring, magnet parsing, tracker integration (mocked HTTP), detail page enrichment, Wikidata lookup, series expansion.

## License

MIT
