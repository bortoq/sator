# Audit Report — sator v0.2

**Date**: 2026-07-22  
**Auditor**: Senior Code Forensic & AppSec QA  
**Scope**: Full codebase audit (12 Python modules, 2 test files, 3 doc files)

---

## Executive Summary

| Category | Status | Findings |
|----------|--------|----------|
| Memory/Resources | ✅ PASS | No leaks, no double-free, no use-after-free |
| Security | ⚠️ 1 Warning | No auth on qBittorrent add in `_qb_add_simple` |
| Complexity | ⚠️ 1 Warning | `cmd_run` too large (350+ lines) |
| Readability | ⚠️ 2 Issues | Dead code in `cmd_search`/`cmd_search_all`; stale `parsed` refs |
| Tests | ❌ 2 CRIT | `cmd_search` and `cmd_search_all` **crash on execution** |
| Roadmap Compliance | ⚠️ Partial | README outdated; `todo.md` spec mostly implemented |
| **Overall** | **❌ REJECTED** | **2 critical bugs in shipping code** |

---

## 1. ПАМЯТЬ И РЕСУРСЫ — ✅ PASS

- Нет ручного управления памятью (Python)
- Нет утечек файловых дескрипторов: все `open()` в контекстных менеджерах или с `try/finally`
- Нет скрытых аллокаций в циклах

## 2. БЕЗОПАСНОСТЬ — ⚠️ 1 Warning

### [WARN-1] `_qb_add_simple()` — no authentication
**Файл**: `sator/qb_client.py:110-125`  
**Описание**: `_qb_add_simple()` отправляет magnet-ссылку в qBittorrent WebUI без аутентификации. Если qBittorrent защищён паролем, запрос упадёт с 403.  
**Риск**: Низкий — это intentional minimal helper. Полноценный `QBClient` с аутентификацией существует отдельно.  
**Рекомендация**: Добавить поддержку `username`/`password` в `_qb_add_simple()` или хотя бы логировать ошибку.

## 3. СЛОЖНОСТЬ — ⚠️ 1 Warning

### [WARN-2] `cmd_run()` — 350+ строк
**Файл**: `sator/cli.py:358-700`  
**Описание**: `cmd_run()` выполняет парсинг аргументов, загрузку файлов, Wikidata-запросы, основной цикл поиска, фильтрацию, вывод и отчёт. Слишком много ответственностей.  
**Рекомендация**: Разбить на `_load_queries()`, `_resolve_languages()`, `_search_loop()`.

## 4. ЧИТАЕМОСТЬ — ⚠️ 2 Issues

### [WARN-3] `cmd_search()` и `cmd_search_all()` — мёртвый/сломанный код
**Файл**: `sator/cli.py:88-120`, `sator/cli.py:219-243`  
**Описание**: Обе функции содержат блоки с `parsed.output` (undefined variable) и `out['magnets']` (list subscripted as dict). Эти блоки никогда не выполняются (упали бы раньше на NameError), но являются copy-paste мусором.  
**Рекомендация**: Удалить мёртвые блоки с `parsed.output` и `out['magnets']`.

### [WARN-4] `cmd_search()` — `INDEXERS` не импортирован
**Файл**: `sator/cli.py:98-100`  
**Описание**: `INDEXERS` не импортирован (в `from sator.indexer import ...` его нет). Функция упадёт с NameError при вызове с tracker != 'all'.  
**Рекомендация**: Добавить `INDEXERS` в импорт.

## 5. ТЕСТЫ — ❌ 2 CRITICAL

### [CRIT-1] `cmd_search` — не тестируется и сломана
**Файл**: `sator/cli.py:88-120`  
**Описание**: Функция содержит 3 ошибки времени выполнения:
1. `INDEXERS` не импортирован (NameError)
2. `parsed` не определён (NameError)
3. `out['magnets']` — list indices must be integers (TypeError)
**Тесты**: Нет тестов для `cmd_search`.  
**Рекомендация**: Исправить или удалить мёртвый код; добавить тесты.

### [CRIT-2] `cmd_search_all` — не тестируется и сломана
**Файл**: `sator/cli.py:219-243`  
**Описание**: Аналогичные ошибки:
1. `parsed` не определён (NameError)
2. `out['magnets']` — list indices must be integers (TypeError)
**Тесты**: Нет тестов для `cmd_search_all`.  
**Рекомендация**: Исправить или удалить мёртвый код; добавить тесты.

### [WARN-5] Недостаточное покрытие тестами
**Статистика**:
- Всего тестов: 10
- `test_cli.py`: 4 теста (только `-help`/`--help`)
- `test_format.py`: 6 тестов (только `_parse_magnet_file`)
- Не покрыты: `cmd_run`, `_process_query_internal`, `search_all`, `parse_size`, `bytes_to_human`, `filter_result_json`, `parse_languages`, `parse_quality`, `parse_title`, `QBClient`, Wikidata lookup

## 6. ROADMAP COMPLIANCE — ⚠️ Partial

### Что реализовано (согласно `todo.md` и `doc/refactor_plan.md`):
- ✅ Рефакторинг bash → Python-пакет (11 модулей)
- ✅ `-h`/`--help`/`-help` нормализация
- ✅ `-o FILE` и `-a file` с `_parse_magnet_file()`
- ✅ `out['torrents']` с метаданными
- ✅ Индикация прогресса (`-v`, `-tt`, компактный режим)
- ✅ `:` вместо `.` для «нет результатов»
- ✅ Умолчания (`DEFAULTS` + `apply_defaults()`)
- ✅ TPB size parser (`&nbsp;` фикс)

### Что НЕ реализовано:
- ❌ **Конфиг-файл** (`~/.config/sator/config`) — отложен на 2-ю итерацию
- ❌ **Тесты для defaults** — обещаны в todo.md («след. коммит»), не написаны

### Документация:
- ❌ **README.md** устарел: не упоминает `-o`, `-T`, `-v`, `-tt`, умолчания, TPB-трекер
- ❌ **doc/refactor_plan.md** устарел: ссылается на `_sator/` (пакет переименован в `sator/`)

---

## Полный список дефектов

| # | Блок кода | Тип | Описание | Как исправить |
|---|-----------|-----|----------|---------------|
| CRIT-1 | `cmd_search` | Крит | 3 runtime-ошибки: undefined INDEXERS, undefined parsed, list→dict | Удалить мёртвый блок `parsed.output`/`out['magnets']`, добавить `INDEXERS` в импорт |
| CRIT-2 | `cmd_search_all` | Крит | 2 runtime-ошибки: undefined parsed, list→dict | Удалить мёртвый блок `parsed.output`/`out['magnets']` |
| WARN-1 | `_qb_add_simple` | Warning | Нет аутентификации при добавлении в qBittorrent | Добавить поддержку `username`/`password` |
| WARN-2 | `cmd_run` (350+ строк) | Warning | Одна функция делает всё | Разбить на `_load_queries()`, `_resolve_languages()`, `_search_loop()` |
| WARN-3 | `cmd_search`/`cmd_search_all` | Warning | Мёртвый код (copy-paste) | Удалить блоки с `parsed.output` |
| WARN-4 | `cmd_search` | Warning | Пропущен импорт `INDEXERS` | Добавить `from sator.indexer import INDEXERS` |
| WARN-5 | Все модули | Warning | Покрытие тестами < 30% | Добавить тесты для критических путей (parse_size, filter, indexer) |
| WARN-6 | README.md | Warning | Устарел — нет -o, -T, -v, -tt, умолчаний | Обновить README |
| WARN-7 | doc/refactor_plan.md | Warning | Ссылается на `_sator/` вместо `sator/` | Обновить пути |

---

## Исправления, внесённые в ходе аудита

1. **`-o FILE` подавляет stdout** — магнеты больше не дублируются на экран (коммит `a07eb77`)

---

## Вердикт: ❌ REJECTED

Две критические ошибки в `cmd_search` и `cmd_search_all` делают эти функции неработоспособными. 
Требуется исправление перед следующим коммитом.
