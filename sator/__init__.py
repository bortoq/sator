"""sator — Search And TORrent: multi-tracker search, filtering, qBittorrent integration."""

__version__ = "0.3"

from sator.iso_langs import iso_lookup, iso_name, iso_code, ISO_LANGUAGES
from sator.language import parse_languages, parse_subtitle_language
from sator.quality import parse_quality, QualityInfo
from sator.title import parse_title, ParsedTitle
from sator.size import parse_size, bytes_to_human
from sator.wikidata import get_wikidata_original_lang
from sator.filter import filter_result_json
from sator.indexer import search_all, TorrentResult, NyaaIndexer, TPBIndexer, LimeTorrentsIndexer, YTSIndexer, SolidTorrentsIndexer, EZTVIndexer, TGxIndexer
from sator.qb_client import QBClient, QBConfig, _qb_add_simple
from sator.exclude import is_excluded, _DEFAULT_EXCLUDES
from sator.tmdb import enrich_query
from sator.process import _process_query_internal
from sator.cli import cmd_run, cmd_process_query, main
