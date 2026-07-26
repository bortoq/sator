"""Centralised default settings and magic numbers for sator.

All tunable constants live here so changing defaults never requires touching
business-logic code.  Import individual names or the module as a whole.
"""

# ── Package ────────────────────────────────────────────────────────────────
__version__ = '0.3'

# ── CLI defaults (filter bounds etc.) ──────────────────────────────────────
DEFAULT_RB = '0'          # resolution lower bound  (0 = disabled)
DEFAULT_RL = '0'          # resolution upper bound  (0 = disabled)
DEFAULT_ZB = '0'          # size lower bound        (0 = disabled)
DEFAULT_ZL = '0'          # size upper bound        (0 = disabled)
DEFAULT_LANG = ['__original__']   # auto-detect original via Wikidata
DEFAULT_SUBS = []                 # no subtitle filter by default
DEFAULT_TRACKERS = ['nyaa', 'tpb', 'yourbittorrent', 'torrentfunk', 'magnetz', 'glotorrents']

# ── Scoring heuristics (process.py) ───────────────────────────────────────
PREFERRED_RES = 1080
SEEDER_CAP = 100
SIZE_FLOOR_GB = 0.1
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
FALLBACK_PENALTY = 500       # subtracted from score of filtered-out items
                             # so any passing item beats any fallback
