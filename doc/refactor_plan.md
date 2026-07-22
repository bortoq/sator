# Refactoring Report: sator_core.py → atomic modules

## Status: ✅ COMPLETED

### What was done
Split the monolithic `sator_core.py` (1960 lines) into 11 single-responsibility Python modules under the `_sator/` package.

### Resulting structure

```
work/sator/
├── _sator/                          # Python package
│   ├── __init__.py                  # Re-exports public API
│   ├── __main__.py                  # Entry point for `python3 -m _sator`
│   ├── iso_langs.py                 # ISO 639 database, iso_lookup/name/code (251 lines)
│   ├── language.py                  # parse_languages, parse_subtitle_language (160 lines)
│   ├── quality.py                   # parse_quality, QualityInfo (155 lines)
│   ├── title.py                     # parse_title, ParsedTitle (176 lines)
│   ├── size.py                      # parse_size, bytes_to_human (41 lines)
│   ├── wikidata.py                  # get_wikidata_original_lang (118 lines)
│   ├── filter.py                    # filter_result_json, _parse_res_filter (81 lines)
│   ├── indexer.py                   # NyaaIndexer, TPBIndexer, LimeTorrentsIndexer, search_all (226 lines)
│   ├── qb_client.py                 # QBClient, _qb_add_simple (126 lines)
│   ├── process.py                   # _process_query_internal (70 lines)
│   └── cli.py                       # All cmd_*, main() (609 lines)
├── sator                            # Bash script: `exec python3 -m _sator run "$@"` (2 lines)
├── sator_core.py                    # Thin wrapper (4 lines, backward compat)
└── doc/
    └── refactor_plan.md             # This file
```

### Changes from the plan
| Original plan | Actual |
|---|---|
| Package name `sator/` | `_sator/` (to avoid conflict with `sator` bash script) |
| `sator_core.py` deleted | Kept as 4-line thin wrapper |
| Tests in `tests/` | Not yet created (postpone) |
| Each module ≤ 300 lines | All ≤ 251 except cli.py (609 lines — cmd_run is large) |

### Verification
- [x] `python3 -m _sator run -s "test"` works
- [x] `./sator -s "test"` works
- [x] `python3 sator_core.py run -s "test"` works (backward compat)
- [x] All CLI flags work identically
- [x] No circular imports
- [x] All functions from original file present

### Future improvements
1. Split `cli.py` cmd_run (400+ lines) into separate file
2. Add `tests/` directory with `pytest` test suite
3. Consider removing `sator_core.py` thin wrapper
