# TMDb-Only Candidate Flow

## Цель

Сделать public candidate pool независимым от KP API и локального IMDb dataset.

Публичный продукт кандидатов использует только:

- `TMDB_TOKEN`;
- TMDb Discover;
- TMDb TV Details;
- локальную нормализацию, scoring и import.

KP/IMDb rating enrichment не входит в public candidate flow. `imdb_id` может сохраняться только как external id из TMDb `external_ids`. Movie runtime uses `runtime_minutes`; legacy `imdb_runtime_minutes` is stripped.

## Новый Flow

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

## Candidate Object Contract

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

## Removed Fields

Candidate pool write-path strips old external rating fields:

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

Not removed:

- `imdb_id`;
- `tmdb_id`;
- `tmdb_score`;
- `tmdb_votes`;
- `tmdb_popularity`;
- `runtime_minutes`.

## Migration Scripts

One-time migration for existing `data/candidates/pool.json`:

```powershell
py scripts/migrations/migrate_candidate_pool_tmdb_only.py --dry-run
py scripts/migrations/migrate_candidate_pool_tmdb_only.py --apply
```

Behavior:

- finds the current candidate pool via repository/config helpers;
- writes a backup before `--apply`;
- strips removed fields;
- sets `source`, `source_provider`, `source_version`;
- recomputes `year`, completeness and missing fields;
- keeps incomplete candidates instead of deleting them;
- marks candidates without `tmdb_id` with `needs_tmdb_match=true`;
- writes `data/diagnostics/candidate_pool_tmdb_only_migration_report.json`.

## Refresh Scripts

Refresh current pool from TMDb Details:

```powershell
py scripts/tmdb/refresh_candidate_pool_from_tmdb.py --dry-run
py scripts/tmdb/refresh_candidate_pool_from_tmdb.py --apply
py scripts/tmdb/refresh_candidate_pool_from_tmdb.py --dry-run --limit 50
py scripts/tmdb/refresh_candidate_pool_from_tmdb.py --apply --only-missing
py scripts/tmdb/refresh_candidate_pool_from_tmdb.py --apply --force-refresh
```

Behavior:

- candidates with `tmdb_id` are refreshed via TMDb TV Details;
- candidates without `tmdb_id` are searched by title/year;
- uncertain matches are reported as `needs_manual_match`;
- local/user fields like `hidden`, `notes`, `criteria_name`, `added_at`, `source_trace` are preserved;
- removed KP/IMDb rating fields are stripped;
- scoring and completeness are recomputed;
- `--apply` creates a backup before writing;
- report path: `data/diagnostics/candidate_pool_tmdb_refresh_report.json`.

Migrate watched raw scores to the TMDb-only schema:

```powershell
py scripts/migrations/migrate_watched_raw_scores_tmdb_only.py --dry-run
py scripts/migrations/migrate_watched_raw_scores_tmdb_only.py --apply
```

Behavior:

- strips watched/meta `kp_score`, `kp_votes`, `imdb_score`, `imdb_votes`;
- keeps existing `tmdb_score`, `tmdb_votes`, `tmdb_popularity`;
- recomputes watched `computed_scores`;
- writes `data/diagnostics/watched_raw_scores_tmdb_only_migration_report.json`.

Refresh watched metadata and TMDb raw scores:

```powershell
py scripts/tmdb/refresh_watched_from_tmdb.py --dry-run
py scripts/tmdb/refresh_watched_from_tmdb.py --apply
py scripts/tmdb/refresh_watched_from_tmdb.py --dry-run --limit 50
py scripts/tmdb/refresh_watched_from_tmdb.py --apply --only-missing
py scripts/tmdb/refresh_watched_from_tmdb.py --apply --force-refresh
```

Behavior:

- records with `meta.tmdb_id` are refreshed via TMDb TV Details;
- records without `tmdb_id` are searched by title/year;
- uncertain matches are reported as `needs_manual_match`;
- updates meta `tmdb_id`, `imdb_id`, description and poster fields;
- updates watched `raw_scores.tmdb_score`, `tmdb_votes`, `tmdb_popularity`;
- does not touch `user_score`, vibe tags, manual genre markup or personal notes;
- does not save KP/IMDb rating fields;
- report path: `data/diagnostics/watched_tmdb_refresh_report.json`.

## Scoring

TMDb-only scoring uses:

- Bayesian TMDb rating;
- vote reliability;
- country score;
- popularity component;
- metadata completeness.

Main scores:

- `quality_score` - stable ranking for normal recommendations;
- `hidden_gem_score` - boosts strong but less obvious titles;
- `final_score` - default search/ranking score.

Known limitation: RU series often have low TMDb vote counts. Watchbane does not use a hard high minimum-votes gate for them. It uses softer Bayesian/reliability scoring so a good RU title with 20-50 votes can remain visible, while a title with 2 votes and a very high rating does not become the absolute top.

## UI/Search Changes

Public candidate search sort modes:

- `final_score` - Итог;
- `quality_score` - Качество;
- `tmdb_score` - TMDb;
- `tmdb_votes` - Голоса TMDb;
- `tmdb_popularity` - Популярность TMDb;
- `year` - Год.

Incomplete view now means missing TMDb/core metadata. It does not mean missing KP/IMDb enrichment.

Candidate cards show TMDb rating/votes. KP/IMDb ratings are not part of the public candidate card.

Watched detail cards also use the TMDb-only public display contract:

- the score ring shows `tmdb_score` with a `TMDb` label;
- ring progress and color come from `final_score`;
- the main-info block shows `tmdb_votes` as `Голоса TMDb`;
- legacy `kp_score`, `kp_votes`, `imdb_score`, `imdb_votes` are not exposed in the card payload;
- if an old watched record has no TMDb scores, the read-only card may fill them from watched meta or the current candidate pool without migrating JSON files.

## Future

Planned directions:

- better local ranker over saved candidate history;
- optional LLM filters over local candidate metadata;
- manual match UI for candidates without confident `tmdb_id`;
- richer country/genre diagnostics;
- watched-pool feedback loop for ranking.
