# TMDb-only migration audit

Дата аудита: 2026-07-02.

Цель: подготовить безопасную миграцию candidate pool на TMDb-only flow без изменения runtime behavior и без удаления данных.

## Runtime paths

Текущий общий candidate pool:

```text
data/candidates/pool.json
```

Связанные runtime JSON:

```text
data/candidates/criteria.json
data/candidates/hidden.json
data/candidates/watchlist.json
```

Пути задаются в:

- `config/constant.py`
  - `CANDIDATES_DIR = "data/candidates"`
  - `CRITERIA_POOL_JSON = "data/candidates/criteria.json"`
  - `CANDIDATE_POOL_JSON = "data/candidates/pool.json"`
- `storage/runtime.py`
  - создаёт runtime directories;
  - вызывает `init_candidate_criteria()`;
  - вызывает `init_candidate_pool()`.
- `candidates/repositories/pool_repository.py`
  - `init_candidate_pool()`
  - `load_candidate_pool()`
  - `save_candidate_pool()`
- `candidates/repositories/criteria_repository.py`
  - `init_candidate_criteria()`
  - `load_candidate_criteria()`
  - `save_candidate_criteria()`
  - `ensure_common_pool_criteria()`

## Current pool shape

Файл `data/candidates/pool.json` существует локально.

На момент аудита:

```text
entries: 593
```

Все 593 записи содержат широкий TMDb + IMDb + KP compatibility schema.

Поля, найденные в текущем pool:

```text
tmdb_id
imdb_id
tvdb_id
kp_id
title
original_title
year
first_air_date
last_air_date
status
type
in_production
original_language
tmdb_origin_countries
tmdb_production_countries
tmdb_country_codes
genres_tmdb
networks
production_companies
number_of_seasons
number_of_episodes
tmdb_rating
tmdb_votes
tmdb_popularity
overview
poster_path
poster_url
backdrop_path
backdrop_url
content_rating
watch_providers_ru
actors_top
crew_top
imdb_rating
imdb_votes
imdb_title_type
imdb_is_adult
imdb_start_year
imdb_end_year
imdb_runtime_minutes
imdb_genres
country_score
country_signals
quality_score
hidden_gem_score
final_score
signals
source
source_query
kp_rating
kp_votes
kp_status
is_complete
criteria_name
genres
countries
country_codes
country_display
genre_keys
genres_display
kp_score
imdb_score
tmdb_score
description
id
alternative_title
saved_at
imdb_found_in_sql
kp_title
kp_attempts
last_kp_attempt_at
last_kp_error
```

Важное наблюдение:

- TMDb-only данные уже есть: `tmdb_id`, `tmdb_rating`, `tmdb_votes`, `tmdb_popularity`, `genres_tmdb`, `tmdb_country_codes`, `poster_url`, `overview`, `quality_score`, `final_score`.
- Но общий pool всё ещё имеет обязательность `kp_score`, `kp_votes`, `imdb_score`, `imdb_votes` через schema/completeness.
- Для совместимости TMDb build нормализует `imdb_rating -> imdb_score`, `kp_rating -> kp_score`, `tmdb_rating -> tmdb_score`.

## KP/IMDb dependency map

### TMDb build pipeline

Основные файлы:

- `candidates/sources/tmdb/builder.py`
- `candidates/sources/tmdb/transformer.py`
- `candidates/sources/tmdb/importer.py`
- `candidates/sources/tmdb/output.py`
- `candidates/sources/tmdb/debug.py`
- `ui/console/tmdb_pool_tools.py`

Ключевые зависимости:

- `builder.build_candidate_pool(...)`
  - default `enrichment_mode="full"`;
  - `full` открывает IMDb SQL и использует KP cache/API;
  - `fast` уже делает TMDb Discover + Details без IMDb SQL и KP API;
  - `kp_cache` использует только локальный KP cache;
  - `kp_top` вызывает KP API только для top N.
- `transformer.connect_imdb(...)`
- `transformer.enrich_from_imdb_sql(...)`
- `transformer.passes_imdb_filters(...)`
- `transformer.compute_quality_score(...)`
- `transformer.compute_hidden_gem_score(...)`
- `transformer.enrich_from_kp_cache_only(...)`
- `transformer.enrich_from_kp_api_if_needed(...)`
- `transformer.normalize_tmdb_candidate_for_common_pool(...)`
- `importer.normalize_tmdb_candidate_for_common_import(...)`
- `output.CSV_FIELDS`
- `tmdb_pool_tools._input_enrichment_mode(...)`
- `tmdb_pool_tools._print_tmdb_candidate_top(...)`
- `tmdb_pool_tools._print_tmdb_candidate_test_details(...)`
- `tmdb_pool_tools._print_tmdb_candidate_stats(...)`

Что надо менять для TMDb-only:

- сделать TMDb-only отдельным explicit mode или новым default только после миграции UI/tests;
- убрать обязательное использование IMDb SQL из default build path;
- заменить `passes_imdb_filters` на TMDb-safe фильтры;
- пересчитать `quality_score`/`hidden_gem_score` без IMDb/KP;
- решить, сохранять ли compatibility-поля `kp_score`, `imdb_score` как `None`, или удалить их из pool schema позже отдельной миграцией.

### Candidate schema/completeness

Основные файлы:

- `candidates/models/schema.py`
- `candidates/pool/queries.py`
- `candidates/pool/search_helpers.py`
- `app/core/filters.py`
- `app/core/ranking.py`
- `candidates/scoring/sort_keys.py`

Ключевые зависимости:

- `COMPLETENESS_REQUIRED_FIELDS = ("kp_score", "kp_votes", "imdb_score", "imdb_votes")`
- `compute_completeness(...)`
- `ensure_candidate_defaults(...)`
- `is_candidate_complete(...)`
- `resolve_canonical_year(...)` использует `imdb_start_year > year > kp_year`
- search filters:
  - `min_kp_score`
  - `min_kp_votes`
  - `min_imdb_score`
  - `min_imdb_votes`
- ranking:
  - `calculate_quality_score(...)` использует `kp_score`, `imdb_score`, `imdb_votes`, `kp_votes`
  - `rank_candidates(...)` сортирует по KP/IMDb signals

Что надо менять для TMDb-only:

- ввести TMDb-only completeness contract, например `tmdb_score/tmdb_votes/poster_url/title/year`;
- изменить `is_complete` так, чтобы отсутствие KP/IMDb не делало кандидата incomplete;
- заменить default sort/ranking с `kp_score` на `final_score`, `quality_score`, `tmdb_score`, `tmdb_votes`;
- оставить старую completeness только для legacy/KP flow, если он сохраняется.

### Candidate service and UI

Основные файлы:

- `candidates/service.py`
- `desktop/candidates/session.py`
- `desktop/candidates/presenters.py`
- `desktop/shared/detail/presenters.py`
- `desktop/shared/detail/main_info.py`
- `ui/console/candidate_pool_tools.py`
- `ui/console/search_menu.py`
- `ui/console/request.py`
- `ui/console/title_presenters.py`

Ключевые зависимости:

- `candidates.service.get_retry_kp_view(...)`
- `candidates.service.retry_kp_enrichment_in_pool(...)`
- `SEARCH_SORT_MODES = ("kp_score", "imdb_score", "kp_votes", "imdb_votes")`
- `SEARCH_SORT_MODE_LABELS`
- `desktop.candidates.session.DEFAULT_SORT_MODE = "kp_score"`
- `desktop.candidates.presenters.SORT_MODE_METRIC_PREFIX`
- `desktop.candidates.presenters.build_candidate_readonly_card(...)`
- `desktop.shared.detail.presenters.build_meta_pill_items(...)`
- `desktop.shared.detail.main_info.build_main_info_items(...)`
- `candidate_pool_tools.retry_kp_for_incomplete_candidates(...)`
- console output печатает KP status, KP score, IMDb score/votes.

Что надо менять для TMDb-only:

- добавить sort modes по TMDb/final score;
- сделать default sort не KP;
- UI должен показывать TMDb score/votes как primary signal;
- KP retry menu либо скрыть, либо перевести в legacy/optional maintenance;
- main-info/card должны не считать пустые KP/IMDb проблемой.

### Dataset transfer/add-title flow

Основные файлы:

- `dataset/transfer/candidate.py`
- `dataset/resolve/defaults.py`
- `dataset/resolve/priority.py`
- `dataset/resolve/service.py`
- `dataset/resolve/identity.py`
- `dataset/resolve/countries.py`
- `dataset/resolve/genres.py`
- `dataset/title_resolve.py`
- `dataset/genres/extract.py`
- `common/cards.py`
- `common/valid.py`

Ключевые зависимости:

- перенос candidate -> watched берёт `kp_score`, `kp_votes`, `imdb_score`, `imdb_votes`;
- genre fallback использует `imdb_genres`, `genres_tmdb`, `genres`;
- resolve flow использует `apis.imdb_sql`;
- country mapping местами импортирует `candidates.sources.kp.enrichment`.

Что надо менять для TMDb-only:

- candidate transfer должен уметь заполнять watched defaults из TMDb-only полей;
- решить, куда в watched raw_scores класть TMDb rating/votes, если KP/IMDb отсутствуют;
- не ломать watched schema, где KP/IMDb остаются историческими raw score fields.

### Direct KP modules and retry

Основные файлы:

- `candidates/sources/kp/enrichment.py`
- `candidates/sources/kp/retry.py`
- `candidates/service.py`
- `ui/console/candidate_pool_tools.py`
- `apis/kp_api.py`

Ключевые функции:

- `retry_kp_enrichment_for_pool(...)`
- `retry_kp_enrichment_in_pool(...)`
- `retry_kp_for_incomplete_candidates(...)`
- `enrich_from_kp_api_if_needed(...)`
- `enrich_from_kp_cache_only(...)`

Что надо менять для TMDb-only:

- не удалять сразу;
- пометить как optional/legacy;
- перестать считать KP retry обязательным шагом для ready pool;
- сохранить для watched/add-title flow, если KP ещё нужен вне candidate pool.

### Direct IMDb SQL modules

Основные файлы:

- `apis/imdb_sql.py`
- `candidates/sources/tmdb/builder.py`
- `candidates/sources/tmdb/transformer.py`
- `dataset/title_resolve.py`
- `dataset/resolve/service.py`
- `dataset/resolve/identity.py`
- `ui/console/sql_tools.py`
- `ui/console/tmdb_pool_tools.py`
- `scripts/build_candidate_pool.py`

Ключевые функции:

- `connect_imdb(...)`
- `enrich_from_imdb_sql(...)`
- `passes_imdb_filters(...)`
- `build_candidate_pool(..., db_path=sql_search.DEFAULT_DB_PATH)`

Что надо менять для TMDb-only:

- не открывать SQLite в TMDb-only build path;
- перенести IMDb SQL в optional enrichment mode;
- убрать `imdb_start_year` из canonical year priority для TMDb-only records или сделать optional fallback.

### Diagnostics/scripts

Основные файлы:

- `scripts/evaluate_candidate_pool.py`
- `scripts/build_candidate_pool.py`
- `scripts/dublecate/instrumenty_povtorov.py`
- `candidates/sources/tmdb/output.py`

Зависимости:

- отчёты считают `imdb_rating`, `imdb_votes`, `imdb_genres`, `kp_id`;
- CSV export содержит `imdb_rating`, `imdb_score`, `imdb_votes`, `kp_score`, `kp_status`, `imdb_genres`;
- duplicate tools используют `kp_score` в выводе.

Что надо менять для TMDb-only:

- добавить TMDb-only report columns;
- не считать отсутствие IMDb/KP ошибкой в diagnostics;
- переименовать/почистить старые `dublecate` scripts позже отдельной задачей.

## Tests that may break

Наиболее вероятные зоны поломки при реальной миграции:

- `tests/test_tmdb_novelty_builder.py`
  - проверяет enrichment modes;
  - проверяет отсутствие KP/IMDb вызовов в `fast`;
  - проверяет stats `found_in_imdb_sql`, `kp_status`.
- `tests/test_search_core.py`
  - фильтры по `kp_score`, `kp_votes`, `imdb_score`, `imdb_votes`;
  - dedupe выбирает лучший `kp_score`;
  - canonical year через `imdb_start_year`.
- `tests/candidate_modules/test_schema.py`
  - completeness зависит от KP/IMDb fields.
- `tests/candidate_modules/test_pool_repository.py`
  - normalization/storage может менять `kp_score` и completeness.
- `tests/candidate_modules/test_pool_dedupe.py`
  - best record выбирается по KP score.
- `tests/desktop/test_candidate_search_behavior.py`
  - default sort/list behavior по KP/IMDb.
- `tests/test_desktop.py`
  - candidate card, main-info, votes, sort labels.
- `tests/test_score_analytics.py`
  - watched analytics использует IMDb/KP scores.
- `tests/dataset/test_resolve_identity.py`
- `tests/dataset/test_resolve_priority.py`
- `tests/dataset/test_records_add.py`
- `tests/dataset/test_records_update.py`
- `tests/dataset/test_records_validation.py`
  - watched raw_scores всё ещё KP/IMDb oriented.
- poster tests могут косвенно использовать fixture cards с KP/IMDb fields:
  - `tests/test_poster_download.py`
  - `tests/test_poster_cache.py`
  - `tests/test_metadata_gui.py`

## Migration risks

- `is_complete` сейчас означает “есть KP+IMDb score/votes”; в TMDb-only это станет ложным почти для всех новых кандидатов, если не поменять контракт.
- Default sorting сейчас KP-first. После TMDb-only кандидаты с `kp_score=None` уйдут вниз или будут выглядеть пустыми.
- `rank_candidates` и dedupe quality используют KP/IMDb; возможно изменится порядок кандидатов и выбор записи при дублях.
- UI/console вывод может выглядеть как “данных нет”, хотя TMDb data есть.
- Candidate transfer в watched может потерять raw_scores, если не определить TMDb fallback.
- IMDb SQL сейчас влияет на genres и canonical year; при отключении надо полагаться на TMDb genres/year.
- KP retry currently doubles as “complete candidates” repair; после миграции это должно стать optional enrichment, иначе UI будет тянуть пользователя обратно к KP.
- Текущий `pool.json` содержит legacy/compat fields; удалять их нельзя без отдельной миграции и backup.

## Recommended safe migration steps

1. Ввести новый schema mode/contract для pool records:
   - `tmdb_only`;
   - `legacy_kp_imdb`;
   - или `enrichment_profile`.
2. Сначала поменять completeness:
   - TMDb-only candidate ready when title/year/tmdb_score/tmdb_votes/poster/genres are enough;
   - KP/IMDb missing fields не считать incomplete.
3. Добавить sort modes:
   - `final_score`;
   - `quality_score`;
   - `tmdb_score`;
   - `tmdb_votes`.
4. Сменить desktop default sort с `kp_score` на `final_score` или `tmdb_score`.
5. Оставить `kp_score/imdb_score` read-compatible fields на время миграции.
6. Спрятать KP retry из основного flow, оставить в optional maintenance.
7. Обновить TMDb import/output diagnostics под TMDb-first columns.
8. Только после зелёных тестов и backup делать data migration.

## Audit commands

Использовались только read-only команды:

```powershell
rg -n "candidate_pool|pool\\.json|CANDIDATE|criteria|data/candidates|HIDDEN_JSON|WATCHLIST" config storage candidates dataset desktop ui tests docs
rg -n "\\b(kp_score|kp_votes|kp_rating|kp_id|kp_status|imdb_score|imdb_rating|imdb_votes|imdb_start_year|imdb_genres)\\b|candidates\\.sources\\.kp|apis\\.imdb_sql|retry_kp_enrichment" app apis candidates common config dataset desktop posters scripts storage tests ui web docs
```

Также read-only Python-команда прочитала `data/candidates/pool.json` и посчитала поля/типы.

Runtime behavior не менялся.
Данные не удалялись.
