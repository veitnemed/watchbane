# Кандидатный flow только на TMDb

## Цель

Сделать public candidate pool независимым от KP API и локального IMDb dataset.

Публичный продукт кандидатов использует только:

- `TMDB_TOKEN`;
- TMDb Discover;
- TMDb TV Details;
- локальную нормализацию, scoring и import.

KP/IMDb rating enrichment не входит в public candidate flow. `imdb_id` может сохраняться только как external id из TMDb `external_ids`. Movie runtime использует `runtime_minutes`; legacy `imdb_runtime_minutes` удаляется.

## Новый flow

1. UI/console запускает TMDb build.
2. `candidates.sources.tmdb.discovery_strategy` строит discovery slices.
3. TMDb Discover возвращает raw discover items.
4. `merge_discovery_results` объединяет slices и сохраняет `source_trace`.
5. Builder убирает watched и уже существующие candidates.
6. TMDb Details загружается с `DEFAULT_TV_DETAIL_APPENDS`.
7. `prepare_tmdb_candidate` нормализует raw details.
8. `candidates.sources.tmdb.scoring` считает quality/hidden/final scores.
9. Snapshot сохраняется в `data/exports/candidate_pool/`.
10. Importer мерджит snapshot в `data/candidates/pool.json`.

## Add-Title Flow

Watched add-title flow тоже public TMDb-only:

1. пользователь вводит title;
2. Watchbane делает TMDb TV Search;
3. для найденного match загружает TMDb TV Details;
4. показывает preview: title, year, TMDb score/votes/popularity, description, poster, genres;
5. пользователь вводит только `user_score`;
6. запись сохраняется в watched dataset и meta.

KP API не нужен. IMDb local dataset не нужен. IMDb rating/votes не используются. `imdb_id` может храниться только как external id из TMDb `external_ids`.

## Контракт объекта Candidate

Required/core поля:

- `source="tmdb"`;
- `source_provider="tmdb"`;
- `source_version=2`;
- `tmdb_id`;
- `title`;
- `year` или `first_air_date`;
- `tmdb_score`;
- `tmdb_votes`;
- `genres` или `genre_keys` или `genres_tmdb`;
- `countries` или `country_codes` или `origin_country`.

Scoring/diagnostic поля:

- `tmdb_popularity`;
- `country_score`;
- `metadata_completeness_score`;
- `quality_score`;
- `hidden_gem_score`;
- `final_score`;
- `is_complete`;
- `missing_fields`;
- `optional_missing_fields`.

Optional metadata:

- `description` / `overview`;
- `poster_path` / `poster_url`;
- `backdrop_path` / `backdrop_url`;
- `content_rating`;
- `actors_top`;
- `crew_top`;
- `keywords`;
- `watch_providers`;
- `networks`;
- `production_companies`;
- `runtime_minutes`;
- `imdb_id`.

## Удалённые поля

Write-path candidate pool удаляет старые external rating fields:

- `kp_score`;
- `kp_votes`;
- `kp_rating`;
- `kp_id`;
- `kp_status`;
- `kp_year`;
- `imdb_score`;
- `imdb_rating`;
- `imdb_votes`;
- `imdb_start_year`;
- `imdb_end_year`;
- `imdb_runtime_minutes`;
- `imdb_genres`;
- `imdb_title_type`;
- `imdb_is_adult`;
- `imdb_found_in_sql`.

Не удаляются:

- `imdb_id`;
- `tmdb_id`;
- `tmdb_score`;
- `tmdb_votes`;
- `tmdb_popularity`;
- `runtime_minutes`.

## Скрипты миграции

Одноразовая миграция для существующего `data/candidates/pool.json`:

```powershell
py scripts/migrations/migrate_candidate_pool_tmdb_only.py --dry-run
py scripts/migrations/migrate_candidate_pool_tmdb_only.py --apply
```

Поведение:

- находит текущий candidate pool через repository/config helpers;
- пишет backup перед `--apply`;
- удаляет removed fields;
- выставляет `source`, `source_provider`, `source_version`;
- пересчитывает `year`, completeness и missing fields;
- сохраняет incomplete candidates вместо удаления;
- помечает кандидатов без `tmdb_id` флагом `needs_tmdb_match=true`;
- пишет `data/diagnostics/candidate_pool_tmdb_only_migration_report.json`.

## Скрипты refresh

Обновить текущий pool из TMDb Details:

```powershell
py scripts/tmdb/refresh_candidate_pool_from_tmdb.py --dry-run
py scripts/tmdb/refresh_candidate_pool_from_tmdb.py --apply
py scripts/tmdb/refresh_candidate_pool_from_tmdb.py --dry-run --limit 50
py scripts/tmdb/refresh_candidate_pool_from_tmdb.py --apply --only-missing
py scripts/tmdb/refresh_candidate_pool_from_tmdb.py --apply --force-refresh
```

Поведение:

- кандидаты с `tmdb_id` обновляются через TMDb TV Details;
- кандидаты без `tmdb_id` ищутся по title/year;
- неоднозначные matches помечаются как `needs_manual_match`;
- локальные/пользовательские поля вроде `hidden`, `notes`, `criteria_name`, `added_at`, `source_trace` сохраняются;
- удалённые KP/IMDb rating fields снимаются;
- scoring и completeness пересчитываются;
- `--apply` создаёт backup перед записью;
- путь отчёта: `data/diagnostics/candidate_pool_tmdb_refresh_report.json`.

Мигрировать watched raw scores к схеме TMDb-only:

```powershell
py scripts/migrations/migrate_watched_raw_scores_tmdb_only.py --dry-run
py scripts/migrations/migrate_watched_raw_scores_tmdb_only.py --apply
```

Поведение:

- удаляет watched/meta `kp_score`, `kp_votes`, `imdb_score`, `imdb_votes`;
- сохраняет существующие `tmdb_score`, `tmdb_votes`, `tmdb_popularity`;
- пересчитывает watched `computed_scores`;
- пишет `data/diagnostics/watched_raw_scores_tmdb_only_migration_report.json`.

Обновить watched metadata и TMDb raw scores:

```powershell
py scripts/tmdb/refresh_watched_from_tmdb.py --dry-run
py scripts/tmdb/refresh_watched_from_tmdb.py --apply
py scripts/tmdb/refresh_watched_from_tmdb.py --dry-run --limit 50
py scripts/tmdb/refresh_watched_from_tmdb.py --apply --only-missing
py scripts/tmdb/refresh_watched_from_tmdb.py --apply --force-refresh
```

Поведение:

- записи с `meta.tmdb_id` обновляются через TMDb TV Details;
- записи без `tmdb_id` ищутся по title/year;
- неоднозначные matches помечаются как `needs_manual_match`;
- обновляет meta `tmdb_id`, `imdb_id`, description и poster fields;
- обновляет watched `raw_scores.tmdb_score`, `tmdb_votes`, `tmdb_popularity`;
- не трогает `user_score`, vibe tags, ручную genre markup или personal notes;
- не сохраняет KP/IMDb rating fields;
- путь отчёта: `data/diagnostics/watched_tmdb_refresh_report.json`.

## Scoring

TMDb-only scoring использует:

- Bayesian TMDb rating;
- vote reliability;
- country score;
- popularity component;
- metadata completeness.

Основные scores:

- `quality_score` — стабильный ranking для обычных рекомендаций;
- `hidden_gem_score` — поднимает сильные, но менее очевидные тайтлы;
- `final_score` — score поиска/ranking по умолчанию.

Известное ограничение: у RU-сериалов часто мало голосов TMDb. Watchbane не использует для них жёсткий высокий minimum-votes gate. Использует более мягкий Bayesian/reliability scoring, чтобы хороший RU-тайтл с 20–50 голосами оставался видимым, а тайтл с 2 голосами и очень высоким рейтингом не становился абсолютным топом.

## Изменения UI/Search

Режимы сортировки public candidate search:

- `final_score` — Итог;
- `quality_score` — Качество;
- `tmdb_score` — TMDb;
- `tmdb_votes` — Голоса TMDb;
- `tmdb_popularity` — Популярность TMDb;
- `year` — Год.

Incomplete view теперь означает отсутствие TMDb/core metadata. Это не означает отсутствие KP/IMDb enrichment.

Карточки кандидатов показывают TMDb rating/votes. KP/IMDb ratings не входят в public candidate card.

Watched detail cards также используют TMDb-only public display contract:

- score ring показывает `tmdb_score` с подписью `TMDb`;
- progress и цвет кольца берутся из `final_score`;
- блок main-info показывает `tmdb_votes` как `Голоса TMDb`;
- legacy `kp_score`, `kp_votes`, `imdb_score`, `imdb_votes` не попадают в payload карточки;
- если у старой watched-записи нет TMDb scores, read-only карточка может подставить их из watched meta или текущего candidate pool без миграции JSON-файлов.

## Будущее

Планируемые направления:

- лучший локальный ranker по сохранённой истории кандидатов;
- optional LLM filters поверх локальных candidate metadata;
- UI ручного match для кандидатов без уверенного `tmdb_id`;
- более богатая диагностика country/genre;
- feedback loop watched-pool для ranking.
