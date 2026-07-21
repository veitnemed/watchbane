# Матрица полей TMDb — Watchbane

**Статус:** исследование текущего кода, без изменения продукта.
**Ветка:** `polya-tmdb`. **Дата:** 2026-07-21.
**Метод:** статическая трассировка исходного кода и тестовых fixtures; сетевые запросы и TMDb token не использовались.

## Границы исследования

Проверены два фактических контура.

1. **Recommendations:** `Discover /movie|tv` → `get_*_details()` → candidate normalizer → `candidate_records` → `RecommendationDeckService` → `desktop.candidates` / detail card.
2. **Collection:** TMDb Search → `get_*_details()` → add defaults либо `refresh_watched_from_tmdb` → `watched_records` → watched/detail UI.

`candidate_records` хранит identity, год, TMDb metrics и scoring отдельными колонками; полный нормализованный candidate дополнительно лежит в `payload_json`. `watched_records` индексирует только identity/main fields, а доменные метаданные лежат в `payload_json` и `meta_json`.

## Endpoint и append contract

| Media type | Details endpoint | Обязательные `append_to_response` текущего клиента |
| --- | --- | --- |
| TV | `/tv/{id}` | `external_ids`, `content_ratings`, `watch/providers`, `aggregate_credits`, `keywords`, `images`, `translations` |
| Movie | `/movie/{id}` | `external_ids`, `release_dates`, `watch/providers`, `credits`, `keywords`, `images`, `translations` |

Discover получает shortlist через `/discover/tv` или `/discover/movie`; поля, требующие полной метаинформации, фиксируются только после Details. Search/Add использует `/search/tv` или `/search/movie`, затем тот же Details contract.

## Матрица

Обозначения storage: **C** — candidate pool, **W** — watched/Collection; `SQL` — отдельная индексируемая колонка, `JSON` — поле внутри payload/meta JSON. «UI» описывает фактический desktop consumer, а не потенциально доступное поле.

| Поле TMDb | Endpoint / append | Тип | API client / нормализация | Storage | Фильтрация | Ranking / deck | UI | Null | Fallback | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | Discover + Details | оба | `get_tv_details` / `get_movie_details` → `tmdb_id` | C: `tmdb_id` SQL + JSON; W: `tmdb_id` SQL + meta JSON | watched/hidden/dedupe identity | исключение watched/hidden и duplicate; не score | candidate identity; Add search показывает ID | да для legacy/import | fallback title/year identity; одинаковый ID разделён по `media_type` | `apis/tmdb/client.py#get_*_details`; `candidates/sources/tmdb/normalizer.py#prepare_*`; `storage/sqlite/*_mapper.py` |
| `media_type` (route `movie`/`tv`) | Discover route + caller | оба | builder задаёт `movie` или `tv`; не читается как raw TMDb field | C/W: `media_type` SQL + JSON | прямой filter | identity, dedupe, route выбора ranker | badge/detail shape | нет для normalizer, да для legacy | `number_of_seasons`/`episodes` позволяет UI распознать TV | `candidates/sources/tmdb/builder.py#_prepare_candidate_for_media_type`; `desktop/candidates/presenters.py#build_candidate_readonly_card` |
| `title` / `name` | Discover + Details | movie / TV | movie `title`; TV `name` → `title` | C: `title` SQL + JSON; W: `title` SQL + payload | text search / identity | final tie-breaker; explanation text | list title, detail title | да в TMDb ответе | original title → localized/primary → `common.untitled` UI | `normalizer.py#prepare_tmdb_*`; `dataset/language.py#choose_display_title` |
| `original_title` / `original_name` | Discover + Details | movie / TV | → `original_title` | C: JSON; W: не гарантирован refresh/add contract | text search, existing-index aliases | не score | Add search suffix; display-title fallback | да | original title после selected/primary/en localized title | `normalizer.py`; `candidates/search/document.py`; `desktop/watched/add_title/search_dialog.py` |
| `overview` | Details + `translations` | оба | `extract_best_overview` → `overview`, `description`, `localized.*.overview` | C: JSON; W: meta JSON/payload по refresh | text search; explicit safety corpus | metadata completeness | description detail card | да | raw overview → translations `ru-RU`, `ru`, `en-US`, `en` → hidden section | `client.py#extract_best_overview`; `normalizer.py`; `explicit_content.py#_text_corpus` |
| `release_date` | Movie Details | movie | → `release_date`, `year` | C: year SQL + JSON date; W: meta/payload | year range, future-release gate | quality freshness when rating unknown | title meta | да | `year` first 4 chars; canonical year checks date if `year` absent | `normalizer.py#prepare_tmdb_movie_candidate`; `models/schema.py#resolve_canonical_year` |
| `first_air_date` | TV Details | TV | → `first_air_date`, `year` | C: year SQL + JSON date; W: meta/payload | year range, future-release gate | quality freshness when rating unknown | title meta, TV information | да | same canonical-year rule | `normalizer.py#prepare_tmdb_candidate`; `recommendation_deck_service.py#_eligible_candidates` |
| `genres[].name` | Details (`genre_ids` only in Discover) | оба | names → `genres`; canonical `genre_keys` | C: JSON; W: meta/payload | include/exclude genres; always-irrelevant gate | affinity, reasons, metadata completeness | chips/detail reasons | да | Discover numeric IDs are not display labels; no genre means incomplete | `normalizer.py#_genre_keys`; `pool/search_helpers.py#_matches_optional_genres` |
| `original_language` | Discover + Details | оба | → `original_language` | C: JSON; W: meta/payload on refresh | only TMDb Discover planning (`with_original_language`), not saved-pool runtime filter | RU signals / onboarding quotas; not direct final score | not shown in candidate detail | да | overview localization may query original-language locale | `builder.py#_russian_signals`; `onboarding/autofill.py`; `dataset/language.py` |
| `origin_country[]` | TV Details; may be absent for movie | оба | merged with production countries into `countries` / `country_codes`; W also keeps `origin_country` | C: JSON only; W: meta/payload | country selector matches `country_codes` | country score / recommendation reasons | country label | да | country codes → names; missing codes fail an active country filter | `normalizer.py#_country_codes`; `pool/search_helpers.py#_matches_optional_country` |
| `production_countries[]` | Details | оба | names/codes merged into same `countries` / `country_codes`; raw separation lost in C | C: JSON only; W: meta/payload | country selector | country score / metadata completeness | country label | да | appended after origin countries, deduplicated | `normalizer.py#_movie_country_*`; `refresh_watched_from_tmdb.py#_meta_fields_from_details` |
| `runtime` | Movie Details | movie | → `runtime`, `runtime_minutes` | C: JSON; W: meta/payload | нет | нет | movie detail runtime | да | `runtime` then `runtime_minutes`; absent value hides row | `normalizer.py#prepare_tmdb_movie_candidate`; `detail/main_info.py#_movie_runtime_value` |
| `episode_run_time[]` | TV Details | TV | → `episode_run_time` | C: JSON; W: meta/payload | нет | нет | TV runtime item | да | `episode_run_time` then legacy `runtime_minutes`; absent hides row | `normalizer.py#prepare_tmdb_candidate`; `detail/additional_info.py#build_additional_info_items` |
| `number_of_seasons` | TV Details | TV | direct field | C: JSON; W: meta/payload | нет | нет | seasons/episodes and TV-shape UI | да | `0`/empty means not TV shape for UI | `normalizer.py`; `detail/main_info.py#_has_tv_shape` |
| `number_of_episodes` | TV Details | TV | direct field | C: JSON; W: meta/payload | нет | нет | seasons/episodes UI | да | paired with seasons; partial display allowed | `normalizer.py`; `detail/main_info.py#build_title_meta_text` |
| `vote_average` | Discover + Details | оба | → `tmdb_score` | C: `tmdb_score` SQL + JSON; W: `raw_scores.tmdb_score` / meta | minimum TMDb score | Bayesian quality/final score; rank tie-breaker | score ring, sorting, reasons | да | unknown rating suppresses score/votes UI and uses metadata/popularity/freshness path | `normalizer.py`; `sources/tmdb/scoring.py#compute_tmdb_quality_score`; `detail/presenters.py` |
| `vote_count` | Discover + Details | оба | → `tmdb_votes` | C: `tmdb_votes` SQL + JSON; W: `raw_scores.tmdb_votes` / meta | minimum votes | vote reliability, low-vote cap, rank tie-breaker | votes row, sorting, reasons | да | zero/absent is `rating_confidence=unknown` | `normalizer.py`; `scoring/rating_confidence.py`; `detail/main_info.py#build_main_info_items` |
| `popularity` | Discover + Details | оба | → `tmdb_popularity` | C: `tmdb_popularity` SQL + JSON; W: `raw_scores.tmdb_popularity` / meta | нет current browse filter | quality/final score and rank tie-breaker | candidate/watched sort; not detail main-info row | да | missing treated as 0 in rank; score path is bounded | `normalizer.py`; `scoring/ranking.py#rank_candidates` |
| `adult` | Details base response, no append | оба | `prepare_tmdb_candidate` / `prepare_tmdb_movie_candidate` → raw `adult` | C: candidate JSON payload; W: not guaranteed by watched refresh | no normal saved-pool filter | candidate deck safety reads `adult`; watched path does not currently copy it | not displayed | да | `null` remains `null`; hard signal is retained when TMDb sends `true` | `normalizer.py#prepare_tmdb_*`; `explicit_content.py#evaluate_explicit_sexual_content`; TMDB-1.1a regression tests |
| TV `content_ratings` / Movie `release_dates` certification | Details append | TV / movie | C: TV `get_content_rating`; movie `get_movie_content_rating` → `content_rating`. W refresh currently always calls TV extractor. | C: JSON; W: meta/payload, but movie certification is not guaranteed | no user-facing filter | explicit-content hard gate; metadata completeness | not displayed | C TV: RU then first country; C movie: RU certification then first country. W movie falls to `None` because it does not read `release_dates`. | `client.py#get_*_content_rating`; `refresh_watched_from_tmdb.py#_meta_fields_from_details`; `explicit_content.py#_content_rating_token` |
| `keywords.results` / `keywords.keywords` | Details `keywords` append | оба | `extract_keywords` → `keywords: list[str]` | C: JSON; W: meta/payload | no current browse filter | explicit-content hard gate; metadata completeness | not displayed; QA/audit evidence | да | empty list, then no keyword safety signal | `client.py#extract_keywords`; `explicit_content.py#_keyword_names` |
| `poster_path`; `images.posters[]` | Details base + `images` append | оба | `extract_best_poster_path` → `poster_path`, `poster_url` | C: JSON; W: meta/payload; downloaded file separately in poster cache | no | metadata completeness only | list/detail poster | да | base poster → preferred language (`ru`, `en`, neutral) images ranking → placeholder | `client.py#extract_best_poster_path`; `detail/card.py#_set_poster_image` |
| `watch/providers` | Details append | оба | RU provider names → `watch_providers` | C: JSON; W: meta/payload | no | no | «Где смотреть» main-info row | да | RU only; empty result → UI `Неизвестно` | `client.py#get_watch_providers`; `detail/main_info.py#_build_watch_provider_item` |
| `credits` / `aggregate_credits` | Movie `credits`; TV `aggregate_credits` append | movie / TV | C: TV aggregate credits, movie direct `credits` → `actors_top`, `crew_top`. W refresh always uses aggregate helper. | C: JSON; W: meta/payload, but movie people lists are not guaranteed | full-text search includes actors | metadata completeness | не передаётся в readonly Recommendations detail | да | C: TV aggregate / movie regular credits. W movie passes `credits` through aggregate helper and may store empty lists. | `client.py#extract_aggregate_credits_top`; `normalizer.py#prepare_tmdb_*`; `refresh_watched_from_tmdb.py#_meta_fields_from_details` |

## Поля, которые загружаются, но не доходят до продукта

| Поле | Что происходит | Вывод |
| --- | --- | --- |
| Watched `adult` | Candidate normalizer после TMDB-1.1a сохраняет raw `adult` в payload, но watched refresh по-прежнему не копирует flag из Details. | Candidate safety signal восстановлен без миграции; watched storage остаётся отдельным известным разрывом. |
| `backdrop_path` / `backdrop_url` | Normalizer сохраняет в candidate JSON; readonly Recommendations card не копирует его, ranking/filter не читает. | Загружается и хранится, но в проверенном desktop recommendation/detail path не используется. |
| `translations` как raw append | Используется только извлекателями localized title/overview; raw append block отдельно не сохраняется. | Это транспортный источник, не самостоятельное domain field; при отсутствии нужного перевода UI опирается на fallback title/overview. |
| Movie `release_dates` certification в watched refresh | Movie append загружается, но refresh вызывает `get_content_rating()` вместо `get_movie_content_rating()`. | Movie `content_rating` после refresh обычно не заполняется и не даёт safety signal. |
| Movie `credits` в watched refresh | Movie append загружается, но refresh подаёт его в `extract_aggregate_credits_top()`, который читает `aggregate_credits`. | `actors_top`/`crew_top` у обновлённых movie records могут быть пустыми. |

## UI ожидает, но storage не гарантирует

| UI contract | Почему не гарантирован storage | Текущее безопасное поведение |
| --- | --- | --- |
| Detail title / overview | Legacy/import records могут не иметь localized block, title или overview; эти поля не все имеют отдельную SQL-колонку. | title использует языковые fallback и `common.untitled`; overview section скрывается. |
| Poster | `poster_path` — optional field и хранится только в JSON/cache, не в `candidate_records` SQL. | Detail показывает placeholder; карточка остаётся доступной. |
| Country | `country_codes` находятся только в JSON и могут отсутствовать у legacy/import records. | country filter не матчится при активном ограничении; UI показывает fallback unknown. |
| TMDb votes / score ring | В JSON/import записи могут быть `null`; только candidate SQL-копии метрик не означают, что UI payload имеет корректную numeric value. | `rating_confidence=unknown` убирает TMDb score/votes и оставляет final score. |
| TV information / providers | seasons, runtime и providers optional и не имеют SQL-колонок. | Неполные строки detail просто не рендерятся; providers показывают `Неизвестно`. |

## Сводка storage

| Хранилище | Отдельные SQL-поля TMDb / identity | TMDb metadata только в JSON |
| --- | --- | --- |
| `candidate_records` | `media_type`, `year`, `tmdb_id`, `tmdb_score`, `tmdb_votes`, `tmdb_popularity`, scoring fields | titles/original title, overview/localized, dates, genres, countries, language, runtime, TV counts, content rating, keywords, poster/provider/credits и прочее |
| `watched_records` | `title`, `media_type`, `year`, `tmdb_id`, `imdb_id`; пользовательская реакция | raw TMDb metrics в `raw_scores`, detail metadata в `meta_json`/payload: overview, dates, genres/countries, runtime, safety/context fields, poster/provider/credits |

## Ограничения результата

- Матрица описывает фактический код на ветке `polya-tmdb`, а не полный API contract TMDb.
- «Нет» в UI означает отсутствие потребителя в проверенном desktop recommendation/detail flow; это не рекомендация удалить поле.
- Не предлагаются schema migrations, новые фильтры или изменения ranking/safety: выявленные разрывы предназначены для следующих отдельных задач.
