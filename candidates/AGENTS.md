# Инструкции для агента в `candidates`

Эта папка отвечает за candidate pool. Работай осторожно: здесь легко случайно изменить формат JSON или смешать разные типы жанровых фильтров.

## Рабочие правила

- UI должен ходить через `candidates.service`, а не напрямую в `candidate_pool.py` или `tmdb_candidate_pool.py`.
- `load_candidate_pool()` и read-view функции не должны писать JSON.
- Любой write-path должен быть явным: import, save, delete, retry KP, mark watched.
- Не меняй формат `candidate_pool.json` и `candidate_criteria.json` без отдельной задачи, миграции и тестов.
- Не смешивай `tmdb_genre_options.py` и `genres.py`.
- Не меняй `keys.py` без понимания cross-criteria dedupe.

## Быстрая карта

- `service.py` — facade для UI.
- `candidate_pool.py` — общий saved pool, filters, stats, diagnostics, prediction helpers.
- `tmdb_candidate_pool.py` — новый TMDb build snapshot.
- `import_tmdb.py` — импорт TMDb snapshot в общий saved pool.
- `schema.py` — нормализация кандидата, `kp_status`, completeness.
- `keys.py` — identity/storage keys.
- `genres.py` — runtime жанры saved pool.
- `tmdb_genre_options.py` — TMDb TV genre IDs для Discover.
- `tmdb_country_options.py` — страны для TMDb Discover UI.
- `kp_enrichment.py` — KP lookup/match/fill helpers.
- `to_dataset.py` — mapper pool `genre_keys` / raw genres → dataset `has_*` (не смешивать с UI/runtime filters).

## Три слоя жанров

- `tmdb_genre_options.py` — TMDb Discover genre IDs.
- `genre_schema.py` / `genre_keys` — canonical keys в pool record.
- `to_dataset.py` + `config/genre_tags.json` — бинарные `has_*` для dataset/model.

При задачах на жанры переноса candidate → dataset сначала смотри `to_dataset.py` и [docs/ADD_RECORD_RULES.md](../docs/ADD_RECORD_RULES.md).

## Перед правкой

1. Найди существующий поток через `rg`.
2. Определи read-path или write-path.
3. Проверь, не относится ли задача к UI facade.
4. Проверь, нет ли уже offline-теста рядом в `tests/test.py`.

## После правки

Запусти:

```powershell
C:\Users\super\AppData\Local\Programs\Python\Python313\python.exe -m compileall main.py common config storage dataset candidates model apis ui scripts tests
C:\Users\super\AppData\Local\Programs\Python\Python313\python.exe tests\test.py
```

Если менялся только markdown, тесты можно не запускать, но финально явно скажи, что изменение документационное.

