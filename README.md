# sator — Search And TORrent

Multi-tracker torrent search and filtering tool with qBittorrent integration.

```
sator -s "Rick and Morty S07" -o results.url
sator -f queries.txt -a                                          # search + auto-add
sator -f queries.txt -m results.json                             # search + best-match JSON
sator -a downloads.txt                                           # add magnets from file
```

## Features

- **6 torrent trackers**: Nyaa, TPB, YTS, SolidTorrents, EZTV, TorrentGalaxy (TGx)
- **Filter pipeline**: resolution bounds, size bounds, language, subtitles, blacklist
- **Language detection**: title parsing + Wikidata auto-detect (original language)
- **Detail page enrichment**: scrapes metadata when title lacks language/subtitle info
- **Best-mode** (`-m`): scores and selects best result per query
- **Verbose output** (`-v`): shows all results including filtered-out (with reason)
- **qBittorrent integration** (`-a`): auto-add found torrents
- **Blacklist**: built-in exclusion of CAM/TS/scrubbed releases
- **Tracker selection** (`-T`): restrict which trackers to search
- **Output file** (`-o FILE`): write magnets/URLs (suppress screen spam)
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
sator -s "Parasite" -l __original__         # auto-detect original language via Wikidata

# Subtitle filters (opt-in with -t)
sator -s "Amélie" -t en                     # require English subtitles
sator -s "Movie" -t en -t fr                # require both English AND French subs

# Choose trackers
sator -s "Lost" -T nyaa -T yts
```

### Best-mode

Best-mode scores results and picks the best match per query:

```bash
sator -f my_queries.txt -m results.json
```

Scoring factors: seeders, resolution match, size range fit, trusted groups, source quality.

### File input

```bash
sator -f queries.txt        # one query per line, output to stdout
sator -f queries.txt -o results.url
```

### Auto-add to qBittorrent

```bash
sator -s "Rick and Morty S07" -a
```

qBittorrent must be running with WebUI enabled at `http://localhost:8080/`.

### Sub-command: run

```bash
sator run -s "Lost" -o lost.url
```

The `run` sub-command is the default; all flags work identically.

## Options

### Resolution bounds (each at most once)

| Flag | Default | Description |
|------|---------|-------------|
| `-rl <res>` | 1080 | Upper bound, e.g. `2160`, `1080`, `720` |
| `-rb <res>` | 480 | Lower bound, e.g. `1080`, `720`, `480` |

### Size bounds (each at most once)

| Flag | Default | Description |
|------|---------|-------------|
| `-zl <size>` | 8g | Upper bound, suffixes `k`, `m`, `g`, `t` |
| `-zb <size>` | 200m | Lower bound, suffixes `k`, `m`, `g`, `t` |

### Language and subtitle filters (repeatable)

| Flag | Default | Description |
|------|---------|-------------|
| `-l [lang]` | `__original__` | Audio language (ISO 639-1 or name). No arg = Wikidata auto-detect |
| `-t <lang>` | (none) | Subtitle language (ISO 639-1 or name). Opt-in, no filter by default |

Without `-t`, subtitle filtering is disabled — all releases pass regardless of subtitle markers.

### Other flags

| Flag | Description |
|------|-------------|
| `-v`, `--verbose` | Show all results including filtered-out (with `✗` prefix) |
| `-tt`, `--tracker-titles` | Show tracker source per result |
| `-m FILE`, `--more FILE` | Best-mode: score & select best result per query, write JSON |
| `-o FILE` | Write output to file (suppresses magnet URIs on stderr) |
| `-T TRACKER` | Restrict search to specific tracker(s). Repeatable. |
| `--enrich` | Enable TMDB enrichment (requires `--tmdb-key`) |
| `--tmdb-key KEY` | TMDB API key |
| `-a` | Auto-add found torrents to qBittorrent |
| `-z`, `--original-lang` | Resolve original language via Wikidata |
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

Default trackers (when `-T` not used): `nyaa`, `tpb`.

## Detail Page Enrichment

When a torrent title lacks language or subtitle metadata, sator can scrape the tracker's detail page:

- Extracts audio languages and subtitle info
- Applies extracted info to the filter pipeline
- Lazy: only fetched when the result would otherwise be filtered out
- Cached: duplicate URLs fetched once per search

## Blacklist

Built-in blacklist excludes releases matching any of: `CAM`, `TS`, `TELESYNC`, `HDTS`, `HD-CAM`, `SCR`, `SCREENER`, `DVD-SCREENER`, `R5`, `R5.LINE`, `HC`, `TRUEDVD`.

Custom exclude patterns via `-e/--exclude` (repeatable).

## Scoring (best-mode)

| Factor | Weight | Description |
|--------|--------|-------------|
| Seeders | High | More seeders = higher score |
| Resolution | High | Closer to target resolution = better |
| Size range | Medium | Within size bounds |
| Trusted groups | Bonus | FLUX, NTb, DON, CtrlHD, HONE, SPARKS |
| Source quality | Penalty | YTS/EZTV get slight penalty vs Nyaa/TPB |

## Configuration

Built-in defaults are applied when flags are not explicitly provided:

- Resolution: 480p–1080p
- Size: 200 MiB – 8 GiB
- Language: original (Wikidata auto-detect)
- Subtitles: no filter (opt-in with `-t`)
- Trackers: `nyaa`, `tpb`

CLI flags always override defaults.

## Development

```bash
git clone https://github.com/bortoq/sator.git
cd sator
python3 -m pytest tests/
```

67 tests covering: CLI parsing, filter pipeline, blacklist, scoring, magnet parsing, tracker integration (mocked HTTP), detail page enrichment, Wikidata lookup.

## License

MIT
