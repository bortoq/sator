# sator — Search And TORrent

Multi-tracker torrent search tool with filtering and qBittorrent integration.

## Usage

```
sator -f <file>              # Search queries from file
sator -s <string>            # Search by query string
sator -f <file> -a           # Search + auto-add to qBittorrent
sator -a <file>              # Direct download links from file (no search)
```

## Options (search mode only, each at most once)

| Flag | Description |
|------|-------------|
| `-rl <res>` | Resolution upper bound (not higher than), e.g. 1080p |
| `-rb <res>` | Resolution lower bound (not lower than), e.g. 720p |
| `-zl <size>` | Size upper bound (not larger than), suffixes k/m/g/t |
| `-zb <size>` | Size lower bound (not smaller than), suffixes k/m/g/t |

## Options (search mode only, repeatable)

| Flag | Description |
|------|-------------|
| `-l [lang]` | Audio language (ISO 639-1 or full name). No arg = original language (Wikidata auto-detect) |
| `-t <lang>` | Subtitle language (ISO 639-1 or full name) |

## Trackers

- **Nyaa.si** — works (HTML scraping)
- **LimeTorrents** — module present but currently blocked by Cloudflare
