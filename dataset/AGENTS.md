# Инструкции для агента в `dataset`

Эта папка — доменный слой watched-базы: добавление, обновление, удаление, meta, Excel, статистика, жанры и теги.

## Рабочие правила

- UI/desktop/console должны ходить через `dataset.service` (цель) или существующие compatibility wrappers.
- Write-path watched-базы: `add_dataset_record` → `update_dataset_record` → `delete_watched_record`.
- `storage` отвечает за I/O через active backend: SQLite по умолчанию, legacy JSON только для import/export/rollback; валидация и нормализация — в `dataset/*`.
- Не меняй формат SQLite watched tables или legacy `data/watched/titles.json` / `data/watched/meta.json` без отдельной задачи, миграции и тестов.
- Не импортируй `ui`, `desktop`, `web` из `dataset`.
- Не импортируй `candidates` из `dataset` (Phase 2: candidate cleanup через side_effects/events, не прямой import).
- `load_*` read-path функции не должны писать JSON без явного write use-case.

## Быстрая карта

- `service.py` — целевой facade для UI (Phase 2+).
- `models/` — results, identity, schema.
- `records/` — add, update, delete, features, side_effects.
- `meta/` — lookup, sync, payload, merge.
- `resolve/` — SQL/KP/TMDb defaults orchestration.
- `add_flow/` — resolve bundle, preview, save.
- `transfer/` — candidate → watched payloads.
- `excel/` — export/import rows.
- `tags/` — vibe tag mutations на dataset.
- `genres/` — mapping, catalog, API import.
- `stats/` — summary, popularity.
- `analytics/` — score analytics (read-only).
- `views/` — formatters (dict → str).

## Compatibility wrappers (не удалять до миграции импортов)

- `dataset_records.py` → `records/*`, `models/results`
- `storage_movie.py` → `records/builder`, `records/recompute`, `excel/rows`
- `title_resolve.py` → `resolve/*`, `transfer/candidate`, `meta/payload`
- `add_title_service.py` → `add_flow/*`
- `delete_record.py` → `records/delete`, `views/delete_formatters`
- `excel_work.py` → `excel/*`
- `genre_import.py`, `genre_stats.py` → `genres/*`
- `tags_work.py` → `tags/*`
- `dataset_stats.py`, `filter_popularity.py` → `stats/*`
- `score_analytics.py` → `analytics/*`

## Данные

- `data/watchbane.sqlite3` — source of truth для watched records/meta.
- `data/watched/titles.json` и `data/watched/meta.json` — legacy import/export/rollback compatibility.

Watched-запись не должна зависеть от доступности API.

## Перед правкой

1. Найди существующий поток через `rg`.
2. Определи read-path или write-path.
3. Проверь, не относится ли задача к UI facade.
4. Проверь offline-тесты в `tests/dataset/` и `tests/test_*.py`.

## После правки

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
```

Если менялся только markdown, тесты можно не запускать, но финально явно скажи, что изменение документационное.
