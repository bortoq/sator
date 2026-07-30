"""Centralised default settings and magic numbers for sator.

All tunable constants live here so changing defaults never requires touching
business-logic code.  Import individual names or the module as a whole.

Quick reference
===============
- Scoring:       PREFERRED_RES, SEEDER_CAP, SIZE_FLOOR_GB, EFFICIENCY_WEIGHT …
- Timeouts:      TIMEOUT_*  (seconds per tracker / API)
- Indexers:      DEFAULT_TRACKERS, *BASE_URL, *MIRRORS
- Cache:         SEARCH_CACHE_TTL, TMDB_CACHE_TTL, CACHE_DIR
- Series search: PACK_SKIP_EPISODES_SEED_THRESHOLD, SERIES_TAG_PREFIX
- Resolutions:   RES_4K, RES_FHD, RES_HD, RES_SD
"""


# ──── Package ─────────────────────────────────────────────────────────────────────
# Semver version of the application.
__version__ = '0.4.0'


# ──── CLI defaults (filter bounds etc.) ───────────────────────────────────────────
# Default resolution lower bound when --rb is not specified.
# Set to '0' to disable filtering by minimum resolution.
# Accepts: resolutions like '720', '1080', '2160' or names like 'hd', 'fhd', '4k'.
DEFAULT_RB = '0'

# Default resolution upper bound when --rl is not specified.
# Set to '0' to disable filtering by maximum resolution.
# Accepts same formats as DEFAULT_RB.
DEFAULT_RL = '0'

# Default size lower bound (bytes or human-readable like '500MB', '2GB').
# Set to '0' to disable minimum-size filtering.
DEFAULT_ZB = '0'

# Default size upper bound (bytes or human-readable).
# Set to '0' to disable maximum-size filtering.
DEFAULT_ZL = '0'

# Language filter used when --lang is omitted.
# '__original__' auto-detects the show/movie original language via Wikidata.
# Other values: ISO 639-1 codes ('en', 'ru', 'ja'...) or full names ('English', 'Russian'...).
DEFAULT_LANG = ['__original__']

# Subtitle-language filter when --subs is omitted.
# '__original__' auto-detects original language subtitles.
# Format: ISO 639-1 codes or full language names.
DEFAULT_SUBS = []

# Trackers used for every search, in priority order.
# All 13 built-in indexers are always enabled (the -T flag was removed).
# Order affects search speed -- faster trackers first reduces total wall-clock time.
# All 13 built-in indexers:
DEFAULT_TRACKERS = [
    'nyaa',           # Nyaa.si -- anime, Asian media
    'tpb',            # The Pirate Bay -- general
    'limetorrents',   # LimeTorrents -- general (cached torrents)
    'yts',            # YTS.mx -- movies (small encodes)
    'solidtorrents',  # SolidTorrents -- general, multi-source
    'eztv',           # EZTV -- TV shows / series
    'tgx',            # TorrentGalaxy -- general, large catalogue
    'yourbittorrent', # YourBittorrent.com -- general
    'torrentfunk',    # TorrentFunk.com -- general
    'magnetz',        # MagnetZ -- general (cached)
    'glotorrents',    # GloDLS.to -- general
    'anilibria',      # AniLibria.top -- Russian anime
    'rutor',          # RuTor.info / rutor.is -- Russian general
]


# ──── Scoring heuristics (process.py) ─────────────────────────────────────────────
# Preferred resolution for scoring. Torrents with this exact resolution get EXACT_RES_BONUS.
PREFERRED_RES = 1080

# Seeders above this value give no additional score benefit.
# Prevents a single ultra-popular torrent from drowning out all other quality signals.
SEEDER_CAP = 100

# Minimum file size (GiB) used as a floor when computing size/seeds efficiency.
# Avoids division-by-zero and prevents tiny files (nfo, subtitles-only) from scoring high.
SIZE_FLOOR_GB = 0.1

# Weight applied to the seeders-to-size efficiency score (0.0-1.0 range).
# Higher = efficiency matters more vs resolution / source bonuses.
EFFICIENCY_WEIGHT = 0.1

# Bonus points added when torrent resolution exactly matches PREFERRED_RES.
EXACT_RES_BONUS = 30

# Bonus points added when resolution is within CLOSE_RES_THRESHOLD of PREFERRED_RES.
# e.g. 720p is 'close to' 1080p, so it gets CLOSE_RES_BONUS instead of EXACT_RES_BONUS.
CLOSE_RES_BONUS = 15

# Resolution difference threshold (pixels) that still counts as 'close enough'.
# Example: with PREFERRED_RES=1080 and CLOSE_RES_THRESHOLD=360, 720p qualifies as close.
CLOSE_RES_THRESHOLD = 360

# Lower bound of 'reasonable' file size range (GiB).
# Torrents larger than this (and under REASONABLE_SIZE_MAX_GB) get REASONABLE_SIZE_BONUS.
REASONABLE_SIZE_MIN_GB = 1.0

# Upper bound of 'reasonable' file size range (GiB).
REASONABLE_SIZE_MAX_GB = 15.0

# Bonus points for torrents whose size falls within [MIN, MAX] range.
REASONABLE_SIZE_BONUS = 10

# Bonus points for torrents released by trusted groups (see TRUSTED_GROUPS).
TRUSTED_GROUP_BONUS = 20

# Release groups whose torrents receive TRUSTED_GROUP_BONUS.
# Names are matched case-insensitively against the release group tag in the torrent title.
TRUSTED_GROUPS = [
    'FLUX', 'NTb', 'DON', 'CtrlHD', 'HONE', 'SPARKS',
]

# Per-source quality scores used when computing the total score.
# Higher = better source (BluRay > WEB-DL > HDTV > CAM).
# Negative values actively penalise low-quality sources.
SOURCE_SCORES = {
    'BluRay':   40,
    'WEB-DL':   25,
    'WEBRip':   15,
    'HDTV':      5,
    'BDRip':    30,
    'DVDRip':   10,
    'CAM':     -50,
    'TELESYNC':-40,
    'SCREENER':-30,
    'TELECINE':-20,
    'WORKPRINT':-10,
}


# ──── Indexer HTTP timeouts (seconds) ─────────────────────────────────────────────
# Maximum seconds to wait for each tracker HTTP response.
# Increase if you have a slow connection and trackers time out frequently.
# Decrease to fail faster on unresponsive trackers.
TIMEOUT_NYAA = 15
TIMEOUT_TPB = 20
TIMEOUT_LIMETORRENTS = 15
TIMEOUT_YTS = 15
TIMEOUT_SOLIDTORRENTS = 15
TIMEOUT_EZTV = 15
TIMEOUT_TGX = 15
TIMEOUT_MAGNETZ = 15
TIMEOUT_GLOTORRENTS = 15
TIMEOUT_YB_LIKE = 15           # YourBittorrent / TorrentFunk (same JSON API)
TIMEOUT_DETAIL = 10           # Detail-page enrichment (per-torrent metadata)
TIMEOUT_ANILIBRIA = 15
TIMEOUT_RUTOR = 15


# ──── API HTTP timeouts (seconds) ─────────────────────────────────────────────────
# Maximum seconds to wait for third-party API responses.
# These affect startup time (Wikidata/TMDB) and enrichment (TMDB).
TIMEOUT_TMDB = 10
TIMEOUT_WIKIDATA = 10
TIMEOUT_QB = 15               # qBittorrent Web UI (add magnet, get status)
TIMEOUT_QB_SIMPLE = 10        # qBittorrent simple health-check call


# ──── Tracker URLs and mirrors ────────────────────────────────────────────────────
# Default qBittorrent Web UI endpoint.
# Change if qBittorrent runs on a different host/port or uses HTTPS.
DEFAULT_QB_URL = 'http://localhost:8090'

# The Pirate Bay mirror list -- tried in order until one responds.
# Used by TPBIndexer to bypass regional blocks.
TPB_MIRRORS = ['https://tpb.party', 'https://piratebay.party']
TPB_FALLBACK_URL = 'https://tpb.party'

# LimeTorrents base URL -- may change as the site moves domains.
LIMETORRENTS_BASE_URL = 'https://www.limetorrents.fun'

# GloDLS base URL.
GLOTORRENTS_BASE_URL = 'https://glodls.to'

# SolidTorrents API endpoint. The query term is appended to this URL.
SOLIDTORRENTS_API_URL = 'https://solidtorrents.to/api/v1/search?q='

# EZTV base URL -- used for TV show episode search.
EZTV_BASE_URL = 'https://eztvx.to'

# AniLibria API v1 endpoint.
ANILIBRIA_API_URL = 'https://anilibria.top/api/v1'
ANILIBRIA_SEARCH_LIMIT = 5   # Max anime releases to fetch per query

# RuTor base URL and mirrors (rutor.info, rutor.is).
RUTOR_BASE_URL = 'https://rutor.info'
RUTOR_MIRRORS = ['https://rutor.info', 'https://rutor.is']
RUTOR_ANIME_CATEGORY = 10    # Category id used for anime search on rutor


# ──── User-Agent strings ──────────────────────────────────────────────────────────
# User-Agent sent to tracker/indexer websites.
# Some trackers block known bot UAs -- change if you get 403/429 errors.
UA_INDEXER = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'

# User-Agent sent when making general HTTP requests from sator.
UA_SATOR = 'sator/0.1'

# User-Agent sent to TMDB API.
UA_TMDB = 'sator/0.3'


# ──── Filesystem paths ────────────────────────────────────────────────────────────
# Directory for all disk caches (search results, TMDB episodes, Wikidata).
# Created automatically if it does not exist. Supports ~ expansion.
CACHE_DIR = '~/.cache/sator'

# Path to the user configuration file.
# Supports ~ expansion. Contents are shell-format KEY=VALUE lines.
CONFIG_PATH = '~/.config/sator/config'


# ──── Exclude defaults (exclude.py) ───────────────────────────────────────────────
# Torrents whose title contains any of these substrings are excluded by default.
# Applied when --exclude is not passed; overridable via --exclude on the CLI.
DEFAULT_EXCLUDES = [
    'CAM', 'HDCAM', 'TELESYNC', 'TS', 'SCR', 'SCREENER',
    'HC', 'SUBBED', 'DVDSCR', 'R5',
]

# Pattern length threshold for exclude matching (characters).
# Patterns shorter than this are matched by individual tokens (not substring).
# Prevents very short patterns like 'TS' from matching unrelated text.
SHORT_PATTERN_THRESHOLD = 5


# ──── Result/display limits ───────────────────────────────────────────────────────
# Maximum number of search results to fetch from each tracker.
# Higher values find more obscure content but slow down the search.
MAX_LIMETORRENTS_RESULTS = 30
MAX_SOLIDTORRENTS_RESULTS = 50
YTS_API_LIMIT = 50
WIKIPEDIA_SRLIMIT = 3      # Max Wikipedia search results for Wikidata fallback
MAGNET_TRUNC = 80          # Max characters displayed for magnet URIs in output
QUERY_TRUNC = 50           # Max characters displayed for search queries in progress
RELEASE_GROUP_MIN_LEN = 2  # Minimum length for release group name extraction


# ──── Size-display thresholds (bytes) ─────────────────────────────────────────────
# Conversion constants for human-readable file-size formatting.
# TIB = tebibyte, GIB = gibibyte, MIB = mebibyte, KIB = kibibyte.
TIB = 1024 ** 4
GIB = 1024 ** 3
MIB = 1024 ** 2
KIB = 1024


# ──── Series numbering padding ────────────────────────────────────────────────────
# Number of zero-padded digits for season number in query strings.
# S02  -> season=2, pads to 2 digits. Change to 1 for 'S2' format.
SERIES_SEASON_PAD = 2

# Number of zero-padded digits for episode number in query strings.
# E01  -> episode=1, pads to 2 digits. Change to 1 for 'E1' format.
SERIES_EPISODE_PAD = 2


# ──── TMDB ────────────────────────────────────────────────────────────────────────
# Regex pattern to extract a 4-digit year (1900-2099) from a show/movie name.
# Used when calling TMDB to disambiguate between same-name titles.
TMDB_YEAR_PATTERN = r'\b(19|20)\d{2}\b'


# ──── Resolution constants ────────────────────────────────────────────────────────
# Named resolution values (vertical pixels) used throughout scoring/filtering.
# RES_4K  = 2160p (Ultra HD)
# RES_FHD = 1080p (Full HD)
# RES_HD  =  720p (HD Ready)
# RES_SD  =  480p (Standard Definition)
RES_4K = 2160
RES_FHD = 1080
RES_HD = 720
RES_SD = 480


# ──── Fallback (best-mode) ────────────────────────────────────────────────────────
# Penalty applied to torrents that fail ALL active filters when best-mode is on.
# Such fallback items get FALLBACK_PENALTY subtracted from their score, ensuring
# that any passing item is preferred over any fallback item.
# Set to 0 to disable fallback entirely (no torrents returned if none pass filters).
FALLBACK_PENALTY = 500


# ──── Series/episode expansion ────────────────────────────────────────────────────
# Tag prefix added when auto-adding episode-level torrents to qBittorrent.
# Full tag is '{PREFIX}{series-slug}' e.g. 'series:breaking-bad'.
SERIES_TAG_PREFIX = 'series:'




# ──── Adaptive series search ──────────────────────────────────────────────────────
# If a season pack has at least this many seeders, skip searching for
# individual episodes -- the pack is good enough and saves significant time.
# Set to 0 to always search for both packs and episodes.
# Set to a very high value (e.g. 99999) to always search episodes.
PACK_SKIP_EPISODES_SEED_THRESHOLD = 10


# ──── Search cache (indexer.py) ───────────────────────────────────────────────────
# Time-to-live for cached search results (seconds).
# Cached results are reused within this window to avoid redundant HTTP requests.
# Set to 0 to disable caching entirely (not recommended).
SEARCH_CACHE_TTL = 300           # 5 minutes

# Subdirectory name under CACHE_DIR for the search result cache.
SEARCH_CACHE_DIR_NAME = 'search_cache'

# Filename for the search result cache JSON file.
SEARCH_CACHE_FILE = 'cache.json'


# ──── YB-Like (YourBittorrent / TorrentFunk) search limit ─────────────────────────
# Maximum number of search results to fetch from YourBittorrent / TorrentFunk.
# Both share the same JSON API, so the same limit applies.
YB_LIKE_SEARCH_LIMIT = 100


# ──── TMDB episode cache ──────────────────────────────────────────────────────────
# Time-to-live for cached TMDB episode data (seconds).
# Episode structs (season/episode count, episode titles) are cached to reduce API calls.
# Default: 7 days.
TMDB_CACHE_TTL = 604800           # 7 * 24 * 3600

# Filename for the TMDB episode cache JSON file.
TMDB_EPISODE_CACHE_FILE = 'episodes.json'


# ──── Wikidata cache filenames ────────────────────────────────────────────────────
# Filename for the Wikidata series metadata cache (season counts, etc.).
WIKIDATA_SERIES_CACHE_FILE = 'seriess.json'

# Filename for the Wikidata language cache (original-language lookups).
WIKIDATA_LANG_CACHE_FILE = 'wikilang.json'
