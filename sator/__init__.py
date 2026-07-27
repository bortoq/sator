"""sator — Search And TORrent: multi-tracker search, filtering, qBittorrent integration."""

from sator import settings
__version__ = settings.__version__

from sator.iso_langs import iso_lookup, iso_name, iso_code, ISO_LANGUAGES
from sator.language import parse_languages, parse_subtitle_language
from sator.quality import parse_quality, QualityInfo, strip_modifiers
from sator.title import parse_title, ParsedTitle
from sator.size import parse_size, bytes_to_human
from sator.wikidata import get_wikidata_original_lang
from sator.filter import filter_result_json
from sator.indexer import search_all, TorrentResult, NyaaIndexer, TPBIndexer, LimeTorrentsIndexer, YTSIndexer, SolidTorrentsIndexer, EZTVIndexer, TGxIndexer, YourBittorrentIndexer, TorrentFunkIndexer, MagnetzIndexer, GloTorrentsIndexer
from sator.qb_client import QBClient, QBConfig, _qb_add_simple
from sator.exclude import is_excluded
from sator.tmdb import enrich_query
from sator.process import _process_query_internal
from sator.series import expand_series_queries, pick_series_best, make_series_tag
from sator.normalizer import compute_new_name, write_sidecar, build_sidecar, _clean_show_name, _parse_season_episode
from sator.cli import cmd_run, cmd_process_query, main
