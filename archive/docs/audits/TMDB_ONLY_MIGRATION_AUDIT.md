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

## Add-Title Public Path

Add-title flow теперь тоже TMDb-only:

- input title;
- TMDb TV Search;
- TMDb TV Details;
- preview;
- user_score;
- save watched.

KP API не нужен. IMDb local dataset не нужен. IMDb rating/votes не используются. `imdb_id` может храниться только как external id из TMDb.

## Non-Candidate Internal Helpers

Некоторые external/local helpers могут оставаться только для legacy/internal diagnostics. Они не должны возвращаться в public candidate или add-title flow.

## Current Risks

- Старые runtime данные могли содержать external rating fields; write-path и migration scripts должны их вычищать при сохранении candidate pool и watched raw scores.
- Для watched записей без `tmdb_id` refresh не должен угадывать при uncertain match; такие записи уходят в report `needs_manual_match`.

## Проверки

При изменениях candidate flow запускать:

```powershell
py -m compileall candidates app dataset
py -m pytest tests/candidate_modules tests/test_search_core.py tests/dataset/test_candidate_transfer.py
```
