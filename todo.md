# TODO — v0.3: умный поиск

## 1. `-m` / `--more` — показать все результаты (вместо лучшего)

**Изменение поведения**:
- По умолчанию: scoring + авто-выбор одного лучшего результата
- `-m` / `--more`: вернуть все отфильтрованные результаты (как работало раньше)

**Scoring-формула**:
```python
def _score_result(t: dict, preferred_res: int = 1080) -> float:
    score = min(t.get('seeders', 0), 100) * 1.0
    src = t.get('_quality', {}).get('source', '')
    source_score = {'BluRay': 40, 'WEB-DL': 25, 'WEBRip': 15, 'HDTV': 5, 'BDRip': 30, 'DVDRip': 10}
    score += source_score.get(src, 0)
    res = t.get('_quality', {}).get('resolution', 0)
    if res == preferred_res: score += 30
    elif res > 0 and abs(res - preferred_res) <= 360: score += 15
    size_gb = t.get('size_bytes', 0) / (1024**3)
    if 1.0 <= size_gb <= 15.0: score += 10
    title = t.get('title', '')
    trusted = ['FLUX', 'NTb', 'DON', 'CtrlHD', 'HONE', 'SPARKS']
    if any(g in title for g in trusted): score += 20
    return score
```

**Логика**:
- `best_mode = not parsed.more` (по умолчанию True)
- Если `best_mode` → `out['torrents'] = [best]`, добавляется один лучший
- Если `-m` → `out['torrents'] = all_filtered` (как сейчас)

**Файлы**: `cli.py` (аргумент `-m`/`--more`), `process.py` (scoring + выбор)

**Трудоёмкость**: ~60 строк

---

## 2. Чёрный список — исключение мусора

**Решение**: `exclude.py` + `--exclude` + конфиг. Только паттерны в названии (без групп).

**_DEFAULT_EXCLUDES**: `['CAM','HDCAM','TELESYNC','TS','SCR','SCREENER','HC','SUBBED','DVDSCR','R5']`

**Файлы**: новый `sator/exclude.py`, `filter.py` (интеграция), `cli.py` (аргумент `--exclude`)

**Трудоёмкость**: ~80 строк

---

## 3. TMDB-обогащение запросов

**Решение**: `tmdb.py` + `--enrich` + TMDB API-ключ.

**Файлы**: новый `sator/tmdb.py`, `cli.py` (аргументы `--enrich`, `--tmdb-key`)

**Трудоёмкость**: ~100 строк

---

## Порядок реализации

1. **Чёрный список** (независим, простой)
2. **`-m` + best по умолчанию** (меняет поведение вывода)
3. **TMDB-обогащение** (средне, нужен API-ключ)

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
