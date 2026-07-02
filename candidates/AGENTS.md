# Инструкции для агента в `candidates`

Эта папка отвечает за candidate pool. Работай осторожно: здесь легко случайно изменить формат JSON или смешать разные типы жанровых фильтров.

## Рабочие правила

- UI должен ходить через `candidates.service`, а не напрямую в `pool/`, `repositories/` или `sources/tmdb/builder.py`.
- `load_candidate_pool()` и read-view функции не должны писать JSON.
- Любой write-path должен быть явным: import, save, clear pool, dedupe, mark watched.
- Единый pool: `criteria_name = "pool"`, UI не создаёт named pools.
- Не меняй формат `candidate_pool.json` и `candidate_criteria.json` без отдельной задачи, миграции и тестов.
- Не смешивай `sources/tmdb/genre_options.py` и `genres.py`.
- Не меняй `models/keys.py` без понимания dedupe и merge legacy-ключей.
- Не трогай candidate pool ради desktop GUI-polish. Визуальный контракт PyQt GUI живёт в [../docs/DESKTOP_STYLE_CONTRACT.md](../docs/DESKTOP_STYLE_CONTRACT.md).

## Быстрая карта

- `service.py` — facade для UI.
- `models/` — schema, keys, country/genre schema.
- `repositories/` — load/save pool и criteria JSON.
- `pool/` — dedupe, queries, stats, diagnostics, search helpers, completeness.
- `scoring/` — sort keys для ranking/dedupe.
- `views/` — formatters (dict → str).
- `sources/tmdb/` — discovery, details normalization, scoring, builder, output, importer.
- `genres.py` — runtime жанры saved pool.
- `sources/tmdb/genre_options.py` — TMDb TV genre IDs.
- `sources/tmdb/country_options.py` — страны Discover UI.
- `to_dataset.py` — mapper pool `genre_keys` / raw genres → dataset `has_*` (не смешивать с UI/runtime filters).

## Три слоя жанров

- `sources/tmdb/genre_options.py` — TMDb Discover genre IDs.
- `models/genre_schema.py` — canonical keys в pool record.
- `to_dataset.py` + `config/genre_tags.json` — бинарные `has_*` для dataset.

При задачах на жанры переноса candidate → dataset сначала смотри `to_dataset.py` и [docs/ADD_RECORD_RULES.md](../docs/ADD_RECORD_RULES.md).

## Перед правкой

1. Найди существующий поток через `rg`.
2. Определи read-path или write-path.
3. Проверь, не относится ли задача к UI facade.
4. Проверь, нет ли уже offline-теста рядом в `tests/candidate_modules/`.

## После правки

Запусти:

```powershell
py -m compileall candidates
py -m pytest tests/candidate_modules tests/test_search_core.py tests/test_filter_popularity.py tests/test_tmdb_overrides.py -q
```

Если менялся только markdown, тесты можно не запускать, но финально явно скажи, что изменение документационное.
