# TODO — формат `-o` / `-a file`

## Формат строки (3 строки на торрент)

```
# [<source>] <title>
# Size: <size_h> | <quality_label> | seeders: <seeders>
magnet:?xt=urn:btih:...
```

Разделитель между торрентами — опциональная пустая строка.

## Пример

```
# [tpb] Seven.Samurai.1954.CRITERION.1080p.BluRay.x264.anoXmous
# Size: 0 B | BluRay 1080p x264 | seeders: 108
magnet:?xt=urn:btih:F7F2B473B8B16DDD5004CC9BF78249E252CEBBD1&...

# [nyaa] [reddeimon] Seven Samurai 1954 [1080p Bluray Remux x264 PCM].mkv
# Size: 40.8 GiB | BluRay Remux 1080p x264 PCM | seeders: 0
magnet:?xt=urn:btih:455df592722424400aaca8b5cc7cf57976844603&...
```

## Парсинг `-a file`

```python
def _parse_magnet_file(path: str) -> List[str]:
    magnets = []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            if s.startswith('magnet:'):
                magnets.append(s)
            else:
                raise ValueError(f"Unexpected: {s[:80]!r}")
    return magnets
```

## Изменения в данных

`_process_query_internal()` добавляет `out['torrents']`:

```python
{
    'title': str,          # название
    'size_h': str,         # человекочитаемый размер
    'source': str,         # трекер (nyaa/tpb/...)
    'seeders': int,        # сиды
    'quality_label': str,  # качество
    'magnet': str,         # magnet-ссылка
}
```

## Изменения в `cmd_run`

1. `all_magnets` → `all_torrents: List[dict]` (из `out['torrents']`)
2. stdout — только magnet URI (без изменений)
3. `-o FILE` — форматированный вывод по спецификации выше
4. `-a file` — использует `_parse_magnet_file()`
