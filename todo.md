# v0.3 — ✅ Реализовано

## 1. `-m` / `--more` — показать все результаты (вместо лучшего) ✅

- **Default**: scoring + авто-выбор одного лучшего результата (`best_mode=True`)
- `-m` / `--more`: вернуть все отфильтрованные результаты
- Scoring-формула в `process.py:_score_result()`
- Сиды (cap 100) + source quality + разрешение + размер + trusted группы

## 2. Чёрный список — исключение мусора ✅

- `sator/exclude.py`: `is_excluded()`, `_DEFAULT_EXCLUDES`
- `filter.py`: интеграция в `filter_result_json`
- `-e`/`--exclude PATTERNS` — comma-separated

## 3. TMDB-обогащение запросов ✅

- `sator/tmdb.py`: `enrich_query()` с in-memory кэшем
- `--enrich` (default: on), `--no-enrich`, `--tmdb-key KEY`
- Graceful degradation без API-ключа

## Конфиг-файл

`~/.config/sator/config` — INI:
```ini
[sator]
rb = 480
rl = 1080
zb = 200m
zl = 8g
t = en
l = original
trackers = nyaa, tpb

[exclude]
patterns = CAM, HDCAM, TELESYNC, TS, SCR, SCREENER, HC, SUBBED, HDRip, DVDRip, R5

[tmdb]
api-key = 
enrich = false
```

**Приоритет**: CLI-аргументы > конфиг-файл > встроенные умолчания.
