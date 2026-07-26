# C3-13 — чистота candidate pool: контракт baseline

**Статус:** read-only измеритель и первый baseline реализованы; задача остаётся открытой до отдельного фикса одной подтверждённой причины.  
**Граница:** только read-only аудит сохранённого candidate pool и результата production eligibility. Он не меняет pool, SQLite, пользовательский профиль, порядок, score или состав колоды.

## Зачем это отдельно от C3-04

`C3-04` остаётся исторически закрытой `[!]`: субъективное «мог бы посмотреть» не стало воспроизводимым критерием. C3-13 измеряет не вкус и не качество ранжирования, а только техническую чистоту данных до персонализации. Первый запуск — baseline, без заранее установленного процента «качества».

## Термины

### Объективный мусор (hard garbage)

Запись считается hard garbage только при детерминированной причине, не зависящей от вкуса пользователя:

- `invalid_tmdb_id` — `tmdb_id` отсутствует, не приводится к положительному целому или не может образовать TMDb identity;
- `invalid_media_type` — исходное значение не принадлежит текущим movie/TV aliases; нельзя скрывать этот факт нормализацией legacy/unknown в `tv`;
- `unusable_title` — ни одно из текущих display-title полей после trim не даёт текста. Placeholder допускается только если он уже является техническим fallback текущего display contract; новый словарь «плохих названий» в C3-13 не создаётся;
- `duplicate_identity` — повтор валидной пары `(media_type, tmdb_id)` в сохранённом pool;
- `explicit_content` — блокируется существующим `candidates.safety.explicit_content`;
- `hard_drop_genre` — содержит жанр из существующего `_ALWAYS_IRRELEVANT_GENRES`;
- `production_hard_reject` — другая уже существующая безусловная причина production eligibility. Она должна быть названа тем же reason code, а не новым QA-правилом.

Одна запись может иметь несколько diagnostics, но в `reason_counts` каждая причина считается отдельно. `pool_hard_garbage_count` считает уникальные записи с хотя бы одной hard-garbage причиной.

### Не является мусором

Следующее не попадает в hard garbage и не используется как proxy для персонализации:

- «не нравится», слабое совпадение со вкусом и низкий personal score;
- непопулярный жанр или старый год;
- отсутствие отдельных дополнительных полей;
- watched, saved, hidden и recently seen без отдельной проверки их storage contract.

Последние четыре состояния учитываются только как `state_flags` и сводятся в `state_conflict_count`; они не делают запись мусором автоматически.

### Metadata incomplete

Отсутствующие `poster`, `overview`, `year`, `genres`, `countries`, `runtime`, `content_rating` и `keywords` считаются отдельно в `metadata_incomplete_count_by_field`. Даже несколько таких пропусков не превращают запись в hard garbage. Production `quality_gate` может отсеять часть sparse/unrated записей — это отдельная production причина, а не задним числом переопределённый metadata defect.

## Текущая цепочка данных и наблюдаемость

| Этап | Текущий код | Что уже отсекается или учитывается | Что теряется из отчёта / где может остаться мусор |
| --- | --- | --- | --- |
| TMDb Discover | `candidates/onboarding/autofill.py`, `candidates/replenish/filter_replenisher.py` | Discover buckets и optional Details; filter replenish может hard-drop explicit после Details | Нет единого read-only reason report для каждой Discover-записи; некорректная запись может дойти до нормализации |
| Нормализация | `build_candidate_record_from_result`, `candidates.models.schema.normalize_candidate_record`, `candidates.pool.storage` | Поля приводятся к candidate shape; identity строится из TMDb пары, иначе title/year fallback | `normalize_media_type` приводит unknown/legacy к `tv`; исходная invalid media причина теряется. Невалидная TMDb identity может остаться на title fallback |
| Сохранённый pool | `storage/sqlite/candidate_pool_repository.py` → `merge_candidate_pool_dict` / `load_candidate_pool_dict` | Upsert удаляет прежнюю совпадающую `(media_type, tmdb_id)` только при валидно переданном ID; protected records учитываются при eviction | Нет storage-level audit reason; invalid ID не попадает в TMDb dedupe, а historical записи не проходят универсальный hard-garbage gate |
| Eligibility | `RecommendationDeckService._eligible_candidates` | Считает `watched`, `actioned`, `recently_seen`, `future_release`, `duplicate`, `preferences`, `quality_gate`, `junk_genre`, `explicit_content` | Счётчики агрегированы на build; нет findings по сохранённому pool, нет raw invalid-ID/media/title reason. Watched/actions/recent — state, а не garbage |
| Ranking | `_rank_candidates`, `_automatic_ranked_candidates` в `recommendation_deck_service.py` | Сортировка, relevance/unknown quotas и personal affinity | Не классифицирует hard garbage; C3-13 не меняет этот этап |
| Active deck / reserve | `build_deck`, `_enrich_selected_candidates` | Берёт ranked candidates в active/reserve; после Details повторно исключает explicit content | Post-Details reject виден только как агрегат `rejected_after_details`; baseline должен отдельно показать, была ли hard-garbage утечка до этой защиты |

## Будущий JSON baseline

Отчёт C3-13 обязан содержать только объясняющие данные, без полного payload:

```text
summary
reason_counts
metadata_incomplete_counts
state_counts
candidate_findings
production_context
head_commit
```

Минимальные показатели:

- `pool_total`;
- `pool_hard_garbage_count`;
- `pool_hard_garbage_rate`;
- `eligible_total`;
- `eligible_hard_garbage_leak_count`;
- `duplicate_identity_count`;
- `state_conflict_count`;
- `metadata_incomplete_count_by_field`;
- `reason_counts`.

Для проблемной записи допустимы только `tmdb_id`, `media_type`, `title`, `hard_garbage_reasons`, `state_flags`, `missing_fields`, `production_eligibility` и `production_reject_reason`.

## Правило после baseline

Цель — ноль объективного мусора в active deck. Каждый последующий фикс должен уменьшать конкретную измеренную причину и сохранять defense in depth на eligibility. Оценка персонализации начинается только после того, как baseline отделил техническую грязь от вкусовых решений. Если `eligible_hard_garbage_leak_count == 0`, C3-13 не придумывает дефект колоды: следующим кандидатом может быть только крупнейшая подтверждённая причина в сохранённом pool.

## Первый baseline — 2026-07-26

Изолированная копия current runtime, HEAD `20e0392`: `pool_total=119`, `pool_hard_garbage_count=35` (`29.4%`), `eligible_total=42`, `eligible_hard_garbage_leak_count=0`, `duplicate_identity_count=0`. Единственная hard-garbage причина — `explicit_content=35`; это крупнейший подтверждённый класс для отдельного следующего фикса. Evidence хранится в ignored `screens/tmp_ui/C3-13/`; audit не делал сетевых запросов и не менял source runtime.
