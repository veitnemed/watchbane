# TMDb-Only Migration Audit

Актуальное состояние после миграции candidate pool.

## Candidate Public Path

Публичный candidate flow теперь TMDb-only:

- TMDb Discover;
- TMDb TV Details;
- TMDb normalizer;
- TMDb scoring;
- import в общий `data/candidates/pool.json`.

В публичном candidate API и console UI не должно быть опций старого external rating flow, local SQL enrichment или retry-действий старого candidate flow.

Полное описание текущего public flow: [TMDB_ONLY_CANDIDATE_FLOW.md](TMDB_ONLY_CANDIDATE_FLOW.md).

## Active Candidate Contract

Core fields:

- `tmdb_id`;
- `title`;
- `year` или `first_air_date`;
- `tmdb_score`;
- `tmdb_votes`;
- `genres` / `genre_keys` / `genres_tmdb`;
- `countries` / `country_codes` / `origin_country`.

Optional fields:

- `description` / `overview`;
- `poster_path` / `poster_url`;
- `content_rating`;
- `actors_top` / `crew_top`;
- `imdb_id` как external id, без рейтингового контракта.

## Non-Candidate Internal Helpers

Некоторые external/local helpers могут оставаться вне candidate flow, если они используются add-title/defaults или diagnostics. Они не должны возвращаться в публичный candidate build/import/search путь.

## Current Risks

- В watched/add-title flow ещё могут быть свои источники defaults. Это отдельный продуктовый путь, не candidate pool.
- Старые runtime данные могли содержать external rating fields; write-path и migration scripts должны их вычищать при сохранении candidate pool.

## Проверки

При изменениях candidate flow запускать:

```powershell
py -m compileall candidates app dataset
py -m pytest tests/candidate_modules tests/test_search_core.py tests/dataset/test_candidate_transfer.py
```
