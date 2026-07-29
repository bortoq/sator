"""Centralised default settings and magic numbers for sator.

All tunable constants live here so changing defaults never requires touching
business-logic code.  Import individual names or the module as a whole.
"""

# ── Package ────────────────────────────────────────────────────────────────
__version__ = '0.4.0'

# ── CLI defaults (filter bounds etc.) ──────────────────────────────────────
DEFAULT_RB = '0'          # resolution lower bound  (0 = disabled)
DEFAULT_RL = '0'          # resolution upper bound  (0 = disabled)
DEFAULT_ZB = '0'          # size lower bound        (0 = disabled)
DEFAULT_ZL = '0'          # size upper bound        (0 = disabled)
DEFAULT_LANG = ['__original__']   # auto-detect original language via Wikidata
DEFAULT_SUBS = []                 # no subtitle filter by default
DEFAULT_TRACKERS = ['nyaa', 'tpb', 'yourbittorrent', 'torrentfunk', 'magnetz', 'glotorrents', 'anilibria', 'rutor']

# ── Scoring heuristics (process.py) ───────────────────────────────────────
PREFERRED_RES = 1080
SEEDER_CAP = 100  # max seeders for scoring; beyond this gives no advantage
SIZE_FLOOR_GB = 0.1  # minimum file size for scoring; avoids division by zero
EFFICIENCY_WEIGHT = 0.1
EXACT_RES_BONUS = 30
CLOSE_RES_BONUS = 15
CLOSE_RES_THRESHOLD = 360        # e.g. 720 is "close" to 1080
REASONABLE_SIZE_MIN_GB = 1.0
REASONABLE_SIZE_MAX_GB = 15.0
REASONABLE_SIZE_BONUS = 10
TRUSTED_GROUP_BONUS = 20

TRUSTED_GROUPS = [
    'FLUX', 'NTb', 'DON', 'CtrlHD', 'HONE', 'SPARKS',
]

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

# ── Indexer timeouts (seconds) ────────────────────────────────────────────
TIMEOUT_NYAA = 15
TIMEOUT_TPB = 20
TIMEOUT_LIMETORRENTS = 15
TIMEOUT_YTS = 15
TIMEOUT_SOLIDTORRENTS = 15
TIMEOUT_EZTV = 15
TIMEOUT_TGX = 15
TIMEOUT_MAGNETZ = 15
TIMEOUT_GLOTORRENTS = 15
TIMEOUT_YB_LIKE = 15               # YourBittorrent / TorrentFunk (same JSON API)
TIMEOUT_DETAIL = 10               # detail-page enrichment

# ── API timeouts (seconds) ────────────────────────────────────────────────
TIMEOUT_TMDB = 10
TIMEOUT_WIKIDATA = 10
TIMEOUT_QB = 15
TIMEOUT_QB_SIMPLE = 10

# ── Default URLs and mirrors ──────────────────────────────────────────────
DEFAULT_QB_URL = 'http://localhost:8090'
TPB_MIRRORS = ['https://tpb.party', 'https://piratebay.party']
TPB_FALLBACK_URL = 'https://tpb.party'
LIMETORRENTS_BASE_URL = 'https://www.limetorrents.fun'
GLOTORRENTS_BASE_URL = 'https://glodls.to'
SOLIDTORRENTS_API_URL = 'https://solidtorrents.to/api/v1/search?q='
EZTV_BASE_URL = 'https://eztvx.to'

# ── User-Agent strings ────────────────────────────────────────────────────
UA_INDEXER = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
UA_SATOR = 'sator/0.1'
UA_TMDB = 'sator/0.3'

# ── Filesystem paths ──────────────────────────────────────────────────────
CACHE_DIR = '~/.cache/sator'
CONFIG_PATH = '~/.config/sator/config'

# ── Exclude defaults (exclude.py) ────────────────────────────────────────
DEFAULT_EXCLUDES = [
    'CAM', 'HDCAM', 'TELESYNC', 'TS', 'SCR', 'SCREENER',
    'HC', 'SUBBED', 'DVDSCR', 'R5',
]
SHORT_PATTERN_THRESHOLD = 5       # ≤ this length → token-match only

# ── Result / display limits ───────────────────────────────────────────────
MAX_LIMETORRENTS_RESULTS = 30
MAX_SOLIDTORRENTS_RESULTS = 50
YTS_API_LIMIT = 50
WIKIPEDIA_SRLIMIT = 3
MAGNET_TRUNC = 80
QUERY_TRUNC = 50
RELEASE_GROUP_MIN_LEN = 2

# ── Size-display thresholds (bytes) ───────────────────────────────────────
TIB = 1024 ** 4
GIB = 1024 ** 3
MIB = 1024 ** 2
KIB = 1024

# ── Series numbering padding ──────────────────────────────────────────────
SERIES_SEASON_PAD = 2
SERIES_EPISODE_PAD = 2

# ── TMDB ──────────────────────────────────────────────────────────────────
TMDB_YEAR_PATTERN = r'\b(19|20)\d{2}\b'

# ── Resolution constants ────────────────────────────────────────────────
RES_4K = 2160
RES_FHD = 1080
RES_HD = 720
RES_SD = 480

# ── Fallback (best-mode) ─────────────────────────────────────────────────
FALLBACK_PENALTY = 500       # subtracted from score of filtered-out items so any
                             # so any passing item beats any fallback

# ── Series / episode expansion ──────────────────────────────────────────────
SERIES_TAG_PREFIX = 'series:'   # tag prefix for episode-level auto-add results

# ── Normalize / rename templates ─────────────────────────────────────────────
# These are Python format-strings. Available placeholders:
#   Movie : {title} {year} {quality} {resolution} {source} {codec} {audio} {hdr}
#   Series: {show} {season:02d} {episode:02d} {title} (episode name) {quality}
#           {resolution} {source} {codec} {audio} {hdr} {group} {mod} {ext}
#   Note: {title} is the episode title for series, movie name for movies.
TEMPLATE_MOVIE = '{title} ({year}) {mod}.{ext}'
TEMPLATE_SERIES = '{season:02d}.{episode:02d}. {title}.{ext}'

# Normalize is opt-in (use -n flag) — this default is unused, kept for config
NORMALIZE_ENABLED = False

# Sidecar file: when normalizing, write original names to a .orig.json file
SIDECAR_ENABLED = True

# ── AniLibria (anilibria.top) ─────────────────────────────────────────────
TIMEOUT_ANILIBRIA = 15
ANILIBRIA_API_URL = 'https://anilibria.top/api/v1'
ANILIBRIA_SEARCH_LIMIT = 5         # max releases to fetch per query

# ── RuTor (rutor.info / rutor.is) ─────────────────────────────────────────
TIMEOUT_RUTOR = 15
RUTOR_BASE_URL = 'https://rutor.info'
RUTOR_MIRRORS = ['https://rutor.info', 'https://rutor.is']
RUTOR_ANIME_CATEGORY = 10          # category id for anime on rutor

# ── Adaptive series search ───────────────────────────────────────────────
# If a season pack has at least this many seeders, skip searching for
# individual episodes — the pack is good enough and saves significant time.
PACK_SKIP_EPISODES_SEED_THRESHOLD = 10

# ── Search cache (indexer.py) ─────────────────────────────────────────────
SEARCH_CACHE_TTL = 300           # seconds; cached search results expire after this
SEARCH_CACHE_DIR_NAME = 'search_cache'  # subdirectory under CACHE_DIR
SEARCH_CACHE_FILE = 'cache.json'        # filename for search cache

# ── YB-Like (YourBittorrent / TorrentFunk) search limit ───────────────────
YB_LIKE_SEARCH_LIMIT = 100

# ── TMDB episode cache ────────────────────────────────────────────────────
TMDB_CACHE_TTL = 604800           # 7 * 24 * 3600 seconds (7 days)
TMDB_EPISODE_CACHE_FILE = 'episodes.json'

# ── Wikidata cache filenames ──────────────────────────────────────────────
WIKIDATA_SERIES_CACHE_FILE = 'seriess.json'
WIKIDATA_LANG_CACHE_FILE = 'wikilang.json'

