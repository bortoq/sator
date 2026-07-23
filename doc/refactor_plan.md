# Refactoring Report: sator_core.py → atomic modules

## Status: ✅ COMPLETED (refactored, then renamed)

### What was done
1. Split the monolithic `sator_core.py` (1960 lines) into 13 single-responsibility Python modules.
2. Package renamed from `_sator/` to `sator/` for cleaner imports.

### Resulting structure

```
work/sator/
├── sator/                          # Python package
│   ├── __init__.py                 # Re-exports public API, __version__
│   ├── __main__.py                 # Entry point for `python3 -m sator`
│   ├── cli.py                      # All cmd_*, main(), cmd_run (710 lines)
│   ├── exclude.py                  # is_excluded, _DEFAULT_EXCLUDES
│   ├── filter.py                   # filter_result_json, _parse_res_filter
│   ├── indexer.py                  # NyaaIndexer, TPBIndexer, LimeTorrentsIndexer, search_all
│   ├── iso_langs.py                # ISO 639 database, iso_lookup/name/code
│   ├── language.py                 # parse_languages, parse_subtitle_language
│   ├── process.py                  # _process_query_internal, _score_result
│   ├── qb_client.py                # QBClient, _qb_add_simple
│   ├── quality.py                  # parse_quality, QualityInfo
│   ├── size.py                     # parse_size, bytes_to_human
│   ├── title.py                    # parse_title, ParsedTitle
│   ├── tmdb.py                     # enrich_query (TMDB enrichment)
│   └── wikidata.py                 # get_wikidata_original_lang
├── tests/                          # pytest test suite
│   ├── test_cli.py
│   ├── test_enrich.py
│   ├── test_exclude.py
│   ├── test_filter_blacklist.py
│   ├── test_format.py
│   ├── test_new_indexers.py
│   ├── test_scoring.py
│   └── test_wikidata.py
├── doc/
│   ├── refactor_plan.md            # This file
│   └── audit.md                    # v0.2 audit (superseded by v0.3)
├── todo.md
├── .gitignore
└── README.md
```

### Verification
- [x] `python3 -m sator run -s "test"` works
- [x] `python3 -m pytest tests/` — 67/67 pass
- [x] All CLI flags work (v0.2 + v0.3)
- [x] No circular imports
