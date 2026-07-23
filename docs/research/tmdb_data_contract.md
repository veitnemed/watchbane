# TMDb data contract (Watchbane)

Актуальный канон TMDb-путей после TMDB-1.5 / TMDB-1.6. Это не журнал аудитов и не
полная матрица API: только то, что продукт делает сейчас и чего сознательно не делает.

**Ветка / контекст:** `polya-tmdb` и далее. Research tooling в `tools/research/` и
`tools/qa/isolation.py` — audit harness; не импортировать из desktop runtime.

## Пути данных

| Path | Entry | Details? | Persist |
| --- | --- | --- | --- |
| Onboarding autofill | Discover buckets → optional Details merge | частично; field parity backlog **TMDB-1.7** | candidate pool |
| Filter replenish | Discover → optional Details merge | да, через `_maybe_fetch_details` | candidate pool |
| Bounded deck enrichment (**TMDB-1.5**) | `build_deck_details_enricher` → `RecommendationDeckService` | только ranked-окно колоды | markers + Details fields via merge |
| Watched refresh (**TMDB-1.6**) | `tools/tmdb/refresh_watched_from_tmdb.py` | media-aware parse | watched meta |

Composition для колоды (сеть не в repository / ranking / presenter / paint):

`CandidateListView` → `build_deck_details_enricher` → `RecommendationDeckService._enrich_selected_candidates` → filter Details merge → `candidate_pool_repository` merge.

## Enrichment markers (candidates)

После успешного Details для колоды:

- `details_enrichment_contract_version = 1`
- `details_enrichment_status = "success"`
- `details_enriched_at` — ISO timestamp

Reuse: запись с version=1 и status=success не запрашивается повторно.
Partial Discover upsert не должен downgrade уже enriched payload (adult /
runtime / content_rating / keywords и родственные поля).

## Bounded Details rule

Request window ≈ `active_limit + reserve_size` плюс cap floor в сервисе.
Весь preliminary pool Details-ами **не** обогащается. Post-Details explicit
rejects — ожидаемый counter, не failed request.

## Watched refresh parity (TMDB-1.6)

`_meta_fields_from_details(..., media_type=)`:

| Media | Certification | People | `adult` |
| --- | --- | --- | --- |
| movie | `get_movie_content_rating` / `release_dates` | `credits` + `normalize_people` | tri-state if key present |
| tv | `get_content_rating` / `content_ratings` | `aggregate_credits` | tri-state if key present |

## Ключевые сохраняемые поля (кратко)

Candidates / watched meta (JSON): identity, scores, genres/countries, overview,
poster, providers, keywords, content_rating, runtime / TV shape, actors_top /
crew_top, adult (где path поддерживает). SQL индексирует только часть identity и
метрик; полный payload в JSON.

## Не делается

- full-pool Details backfill / Discover-only historical rewrite
- schema migration под TMDb fields
- per-request Details audit log в SQLite
- ranking / filter algebra / like-dislike / web / LLM
- reopen TMDB-1.5 или 1.6 из-за ожидаемых safety rejects

## Backlog

| ID | Status | Scope |
| --- | --- | --- |
| TMDB-1.5 | closed | bounded deck Details + live acceptance |
| TMDB-1.6 | closed | watched Details parity |
| **TMDB-1.7** | next | onboarding Details field parity (`runtime` / `content_rating` / `keywords` + TV shape); без historical backfill |
| TMDB-1.8 | conditional | TV `episode_run_time` только при системной потере nonempty |

## Runners и тесты

```powershell
# Isolated live acceptance for deck enrichment (ignored evidence/)
py tools/research/trace_tmdb_details_enrichment_1_5.py `
  --runtime-root "$env:TEMP\watchbane-tmdb-1-5-live" `
  --output "evidence/tmdb_matrix_1_5"

# Watched refresh (product/tool path)
py -m pytest tests/test_refresh_watched_from_tmdb.py -q

# Deck enrichment unit coverage
py -m pytest tests/test_recommendation_deck_service.py -q

# Isolation launcher (no synthetic taste profiles)
py -m tools.qa.run_recommendation_audit --runtime-root tmp/qa_runtime_iso
```

Isolation: [`tools/qa/isolation.py`](../../tools/qa/isolation.py) —
`assert_runtime_is_isolated`, `apply_isolated_data_dir`, `.watchbane_qa_isolated`.
Не путать с Cursor sandbox и не с удалёнными synthetic taste profiles P1–P3.
