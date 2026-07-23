# cursor-work.md — отчёт по работе Cursor / агентов

**Назначение:** живой журнал изменений в репозитории Watchbane, который ведёт агент после каждой осмысленной сессии или закрытого roadmap ID.

**Канон продукта:** [`docs/contracts/PRODUCT_ROADMAP_CONTRACT.md`](docs/contracts/PRODUCT_ROADMAP_CONTRACT.md)  
**Правила агента:** [`AGENTS.md`](AGENTS.md)

---

## Как вести этот файл

После задачи агент **дописывает** запись сверху журнала (новые сверху):

```markdown
### YYYY-MM-DD — <ID или тема>
- **Запрос:** …
- **Сделано:** …
- **Файлы / коммит:** …
- **Проверка:** …
- **Не сделано / next:** …
```

Не дублировать весь PRODUCT — сюда краткий отчёт «что реально сделали в git/чате».

---

## Сейчас (снимок)

| Поле | Значение |
| --- | --- |
| Продуктовый контур | **X — inbox-колода** (смотрел / сохранить / скрыть) |
| Не делаем | V0 «Сегодня», A/B (parking), web, LLM |
| Активный фокус | `C3-04` [!] закрыта без acceptance; C4 [x]; весь блок C ещё не закрыт |
| TMDb | **1.5–1.7 closed**; канон [`docs/research/tmdb_data_contract.md`](docs/research/tmdb_data_contract.md); next **TMDB-1.8** (условный) |
| UI QA scales | `1.0` и `1.25` |
| Последний docs commit | `89d0e6a` (C3-07/C3-08) |

**Цель простыми словами:** разобрать порцию рекомендаций в списки, а не «выбрать кино на вечер».

**Дальше по плану:** TMDB-1.8 только если `episode_run_time` системно теряется; иначе C3 acceptance.

---

## Журнал

### 2026-07-23 — TMDB-1.7 (Onboarding Details field parity)
- **Запрос:** onboarding Details merge на уровне deck/watched: runtime/rating/keywords + TV shape + adult.
- **Сделано:** `_merge_details_into_discover_result` копирует TV `number_of_seasons`/`number_of_episodes` и tri-state `adult`; `build_candidate_record_from_result` персистит их. Runtime/content_rating/keywords уже были с cc96ff8. Ranking/quotas/historical backfill не трогались.
- **Файлы / commit:** `candidates/onboarding/autofill.py`, `tests/test_onboarding_autofill.py`, `tmdb_data_contract.md`, cursor-work, PRODUCT; `d674e2f`.
- **Проверка:** `py -m pytest tests/test_onboarding_autofill.py -q -k "details_merge_persists or keeps_adult_and_tv_shape or details_enrichment_dedupes_before"` — 6 passed.
- **Не сделано / next:** TMDB-1.8 условный; historical backfill не планируется.

### 2026-07-23 — HOUSEKEEP-TMDB-QA
- **Запрос:** убрать synthetic taste profiles P1–P3 и одноразовые TMDb-отчёты; оставить isolation.
- **Сделано:** один контракт `docs/research/tmdb_data_contract.md`; удалены baseline/partial/inventory/snapshot md; удалены P1–P3 harness + runners + `screens/tmp_ui/C3-10|11|12`; slim `tools/qa/README`; `tests/helpers/candidate_factory.py`; isolation launcher сохранён.
- **Файлы / commit:** docs/research, tools/qa, tests/helpers, PRODUCT journal, cursor-work; в `4d396c1`.
- **Проверка:** `py -m pytest tests/test_qa_isolated_launcher.py tests/test_output_defect_audit.py tests/test_refresh_watched_from_tmdb.py tests/test_recommendation_deck_service.py -q` — 63 passed; `compileall tools/qa tests/helpers`.
- **Не сделано / next:** TMDB-1.7 (сделан следом); не reopen 1.5/1.6.

### 2026-07-23 — TMDB-1.6 (Watched Details parity)
- **Запрос:** одинаково корректные TMDb-данные в Recommendations и Collection после watched refresh.
- **Сделано:** `_meta_fields_from_details` media-aware: tri-state `adult`; movie `get_movie_content_rating` / `release_dates`; movie `credits` + `normalize_people`; TV без регрессии на `content_ratings` / `aggregate_credits`. Ranking/deck/UI/schema не менялись.
- **Файлы / commit:** `tools/tmdb/refresh_watched_from_tmdb.py`, `tests/test_refresh_watched_from_tmdb.py`, research docs, PRODUCT journal, `cursor-work.md`; в `4d396c1`.
- **Проверка:** `py -m pytest tests/test_refresh_watched_from_tmdb.py -q` — 13 passed.
- **Не сделано / next:** historical watched backfill; TMDB-1.7 (сделан следом).

### 2026-07-23 — TMDB-1.5F (docs freeze)
- **Запрос:** дальнейший план TMDb после 1.5 — freeze + backlog.
- **Сделано:** 1.5 помечен closed в research docs; backlog 1.6→1.7→1.8 зафиксирован; research tooling оставлен как audit harness (не product dependency). Product deck/onboarding/watched не менялись.
- **Файлы / commit:** `docs/research/tmdb_snapshot_contract.md`, `tmdb_partial_enrichment_audit.md`, `tmdb_field_inventory.md`, `PRODUCT_ROADMAP_CONTRACT.md` journal, `cursor-work.md`; commit не создан.
- **Проверка:** docs-only; без product diff.
- **Не сделано / next:** следующий product ID — **TMDB-1.6** Watched Details parity (`adult`, movie certification, movie credits). Не reopen 1.5; не backfill pool.

### 2026-07-20 — C4-03
- **Запрос:** «ок, C4-03».
- **Сделано:** reserve ring уменьшен с 48/40 до 40/32 scaled px — это спокойный вторичный status рядом с «Для вас». Presentation, tooltip, accessibility и refill/new-deck actions не менялись.
- **Файлы / commit:** `desktop/candidates/deck_reserve_indicator.py`, PRODUCT, `cursor-work.md`; commit не создан.
- **Проверка:** `py -m compileall desktop tests scripts tools`; deck presentation/snapshot — 12 passed. Native Windows PNG открыты: `screens/tmp_ui/C4-03/{after_100,after_125}.png`; platform `windows`, Segoe UI available; ring читаем, но не конкурирует с title. Widget tests не стартуют из-за Qt binding mismatch в `pytest-qt`.
- **Не сделано / next:** C4 пройдена. Весь блок C не закрывается автоматически: C3 acceptance остаётся неподтверждённым.

### 2026-07-20 — C4-02
- **Запрос:** «ок, C4-02».
- **Сделано:** `RecommendationEmptyState` больше не получает scaled fixed minimum width. В узкой detail panel его title/subtitle переносятся внутри собственных границ; `--empty-state` в isolated `capture_recommendation_after_action.py` покрывает pool-empty/no-results и печатает geometry/platform/font evidence.
- **Файлы / commit:** `desktop/candidates/empty_state.py`, `tools/screenshots/capture_recommendation_after_action.py`, `tests/test_desktop.py`, PRODUCT, `cursor-work.md`; commit не создан.
- **Проверка:** `py -m compileall desktop tests scripts tools`; 3 targeted direct layout tests — passed. Qtbot Candidates tests не дошли до assertions: `pytest-qt` не распознаёт PyQt6 QWidget. Native Windows screenshots открыты: `screens/tmp_ui/C4-02/{after_empty_100,after_empty_125,after_no_results_125}.png`; platform `windows`, Segoe UI available. Нет clipping/overlap/mojibake; long no-results copy wraps.
- **Happy path:** A да (Recommendations активна через capture); B да (одно ясное empty state); C n/a (колода сознательно пуста); D да (нет technical tab text или top clipping); E да (1.0/1.25 без overlap).
- **Не сделано / next:** не менялись deck/ranking/safety/filters; C4-03 отдельно.

### 2026-07-20 — C4-01
- **Запрос:** «ок, C4-01» после отдельного решения открыть C4.
- **Сделано:** на UI scale 1.25 detail card остаётся compact two-column; poster в compact profile уменьшен. Overview больше не находится внутри poster-column: он всегда расположен после полного hero-row на ширину detail section, поэтому не конкурирует с main info.
- **Файлы / commit:** `desktop/shared/detail/{profiles,card_layout}.py`, `tests/{test_desktop,test_ui_scale_settings}.py`, PRODUCT, `cursor-work.md`; commit не создан.
- **Проверка:** `py -m compileall desktop tests scripts`; 5 targeted detail/scale tests — passed. Native Windows `capture_film_card.py` 1.0/1.25, PNG открыты: `screens/tmp_ui/C4-01/{after_100,after_125}.png`; Segoe UI available, нет clipping title/chips/main-info header, overview не overlap main info. Full pytest: 1569 passed, 117 failed из-за массового Qt binding mismatch в pytest-qt; три старых overview expectations затем исправлены targeted-тестами.
- **Не сделано / next:** не менялись ranking, safety, filters, data; C4-02 отдельно.

### 2026-07-20 — C3-04 (закрыта без acceptance)
- **Решение автора:** не продолжать C3-04 по критерию «мог бы посмотреть». Одна сессия дала 1/10; методика не признана воспроизводимой оценкой качества.
- **Сделано:** в PRODUCT задача получила статус `[!]` — закрыта без прохождения acceptance; C3 acceptance явно оставлен неподтверждённым, автоматический переход к C4 запрещён.
- **Файлы / commit:** PRODUCT, `cursor-work.md`; commit не создан.
- **Проверка:** `screens/tmp_ui/C3-04/session1_*.json`; код не менялся.
- **Не сделано / next:** новая методика качества или отдельное продуктовое решение о допуске к C4.

### 2026-07-20 — C3-12
- **Запрос:** провести output QA всех пресетов: странные названия, пустые metadata и возможные porn/hentai-сигналы в title/overview/keywords.
- **Сделано:** `output_defect_audit.py` проверяет все 8 current onboarding `PRESETS` через существующие `TastePreset → OnboardingTasteProfile → fetch buckets → discover request`: plans непустые, страны/media согласованы, `include_adult=False`. Synthetic top-10 отдельно проверяются на placeholders, mojibake, пустые visible fields и explicit/hentai/porn; используется текущий explicit safety gate. Новый runner сохраняет единый JSON-отчёт в isolated runtime.
- **Результат:** 8/8 preset contracts PASS; P1/P2/P3 top-10 — 0 defects, 0 suspicious sexual markers. Negative fixture `Hentai Academy` / `pornographic anime` доказательно отмечается как explicit + marker.
- **Файлы / commit:** `tools/qa/{output_defect_audit.py,run_output_defect_audit.py,README.md}`, `tools/qa/synthetic_taste_profiles.py`, `tests/test_output_defect_audit.py`, PRODUCT; commit не создан.
- **Проверка:** `py -m tools.qa.run_output_defect_audit --runtime-root screens/tmp_ui/C3-12/runtime --output-dir screens/tmp_ui/C3-12`; targeted pytest — 20 passed. Evidence: `screens/tmp_ui/C3-12/output_defect_audit.json`.
- **Не сделано / next:** offline fixture audit не доказывает live TMDb availability/metadata и не заменяет методику качества; нет ranking/UI/safety fixes.

### 2026-07-20 — C3-11
- **Запрос:** оценивать не только «понравилось», но и соответствие карточек заданному вайбу; mismatch вроде school drama для heavy Russian drama должен быть виден отдельно.
- **Сделано:** в synthetic taste profile schema добавлен strict `vibe_alignment`: required/forbidden genres, countries, keywords и пороги matching cards / distinct countries / distinct genres. Runner сохраняет per-card reasons (`wrong_country`, `missing_required_all_genres`, `forbidden_keyword` и т.д.) + deck summary; это audit-only после существующего RecommendationDeckService, без нового filter algebra, ranker, safety или UI.
- **Файлы / commit:** `tools/qa/synthetic_taste_profiles.py`, три fixtures, `tests/test_synthetic_taste_profiles.py`, `tools/qa/README.md`, PRODUCT; commit не создан.
- **Проверка:** `py -m tools.qa.run_synthetic_taste_profile_evaluation --runtime-root screens/tmp_ui/C3-11/runtime --output-dir screens/tmp_ui/C3-11` → P1/P2/P3 PASS; `py -m pytest tests/test_synthetic_taste_profiles.py tests/test_qa_isolated_launcher.py -q` — 17 passed. Evidence: `screens/tmp_ui/C3-11/`.
- **Не сделано / next:** это не доказательство полезности и не замена авторской C3-04; на момент этой записи C3-04 оставалась [~].

### 2026-07-20 — D2-01
- **Запрос:** Factory Reset в Settings должен действительно очищать текущий пользовательский runtime; не удалять QA-sandbox из-за путаницы путей.
- **Причина:** стандартный runtime `C:\Users\super\AppData\Local\Watchbane\data` очищался, но legacy-артефакты в `C:\Users\super\AppData\Local\Watchbane\` (`watchbane.sqlite3`, `watched/`, `candidates/`) оставались и выглядели как несброшенный профиль.
- **Сделано:** Factory Reset удаляет эти legacy-файлы и credential-файлы app root вместе с текущими managed paths; TMDb credential переносится в новый main runtime. Панель показывает active profile + exact runtime path до destructive confirmation; QA launcher и `WATCHBANE_DATA_DIR` не менялись.
- **Файлы / commit:** `storage/profile_reset.py`, `app/use_cases/profile_management.py`, `desktop/settings/{factory_reset_panel,tab_view}.py`, `desktop/i18n/catalog.py`, tests, `tools/screenshots/capture_factory_reset_panel.py`, PRODUCT; commit не создан.
- **Проверка:** `py -m pytest tests/test_data_profiles.py tests/desktop/test_profile_reset_flow.py -q` — 19 passed; native Windows captures `screens/tmp_ui/D2-01/after_{100,125}.png` открыты: нет clipping/overlap/mojibake, путь и кнопка видимы; platform `windows`, Segoe UI available. Пользователь разрешил live destructive check: Qt-диалог подтвердил `DELETE ALL`, startup reset применён к `main`; после `ensure_runtime_data_layout()` watched=0, candidates=0, onboarding required.
- **Не сделано / next:** не удалены/не переработаны profiles или QA-sandbox; это отдельное архитектурное решение. На момент этой записи C3-04 оставалась [~].

### 2026-07-20 — D2-02
- **Запрос:** `DELETE ALL` визуально подтверждается, но после повторного открытия профиль остаётся заполненным.
- **Причина:** bootstrap создаёт `watchbane.instance.lock` в runtime до обработки отложенного Factory Reset. На Windows попытка удалить всю `data` завершалась `WinError 32` на занятом lock-файле, поэтому SQLite и пользовательские данные оставались на месте.
- **Сделано:** Factory Reset сохраняет только технический lock текущего процесса, удаляет всё остальное содержимое runtime и затем возвращает main profile; при обычном завершении `SingleInstanceGuard` удаляет сохранённый lock. UI, ranking и `WATCHBANE_DATA_DIR` не менялись.
- **Файлы / commit:** `storage/profile_reset.py`, `tests/test_data_profiles.py`, PRODUCT; commit не создан.
- **Проверка:** `py -m compileall storage tests`; `py -m pytest tests/test_data_profiles.py tests/desktop/test_profile_reset_flow.py -q` — 19 passed. Изолированный Windows `QLockFile` harness воспроизвёл старый `WinError 32`, после исправления: SQLite, watched и reset request удалены; lock исчез после `release()`.
- **Не сделано / next:** основной пользовательский runtime намеренно не очищался агентом; повторите `DELETE ALL` в уже запущенном приложении и откройте его снова.

### 2026-07-20 — C4-04
- **Статус:** отменено по решению автора 2026-07-21: оформление возвращено к C4-01…C4-03.
- **Откат:** удалено размещение overview в recommendation info-column; description снова следует за полной hero-row. Порядок metadata возвращён: страна → где смотреть → голоса TMDb. C4-01…C4-03, ranking, filters и safety не менялись.
- **Файлы / commit:** `desktop/shared/detail/{profiles,card_layout,main_info}.py`, `tests/test_desktop.py`, `tools/screenshots/capture_recommendation_after_action.py`, PRODUCT; commit не создан.
- **Проверка:** `py -m compileall desktop tests scripts`; main-info/overview subset — 29 passed, movie detail — 4 passed. Native Windows captures `screens/tmp_ui/C4-04/reverted_{100,125}.png` открыты: исходная композиция восстановлена, нет clipping/overlap; platform `windows`, Segoe UI available.

### 2026-07-21 — C4-05
- **Запрос:** description в Recommendations должен быть в левой колонке карточки, сразу под постером и не заходить в правую metadata-column.
- **Сделано:** один candidate-only layout flag перенёс `detailOverviewSection` и `detailOverviewTopGap` в `detailPosterColumn`. Overview шириной ровно с постер; присоединён сразу после poster primary без вертикального gap. Watched detail сохранил общую overview-section после full hero row.
- **Файлы / commit:** `desktop/shared/detail/{profiles,card_layout}.py`, `tests/test_desktop.py`, PRODUCT; commit не создан.
- **Проверка:** `py -m compileall desktop tests scripts`; targeted detail overview tests — 5 passed. Native Windows captures `screens/tmp_ui/C4-05/{after_100,after_125}.png` открыты: description находится под постером, не пересекается с правой колонкой; clipping/overlap/mojibake не увидены. Platform `windows`, Segoe UI available.

### 2026-07-19 — C3-10
- **Запрос:** Synthetic taste profile evaluation harness: воспроизводимый QA-only контур для трёх JSON-профилей.
- **Сделано:** строгая валидация (unknown fields → ошибка), адаптер в существующие candidate filters/vector, fixture pool и synthetic watched/saved/hidden через storage API, isolated launcher до import, единый RecommendationDeckService, сохранение actual top-10 и hard checks. Keywords/franchise, для которых нет current filter contract, помечены audit-only; parallel filtering не добавлен.
- **Файлы / commit:** `tools/qa/{synthetic_taste_profiles.py,synthetic_taste_profiles_child.py,run_synthetic_taste_profile_evaluation.py,fixtures/synthetic_taste_profiles/*,README.md}`, `tests/test_synthetic_taste_profiles.py`, PRODUCT; commit не создан.
- **Проверка:** `py -m tools.qa.run_synthetic_taste_profile_evaluation --runtime-root screens/tmp_ui/C3-10/runtime --output-dir screens/tmp_ui/C3-10` → 3 reports + `child_isolation_proof.json`; `py -m compileall desktop tests scripts tools`; targeted pytest (16 passed). Evidence: `screens/tmp_ui/C3-10/`.
- **Не сделано / next:** не менялись ranking/UI/safety, не добавлены LLM/embeddings/внешний evaluator; на момент этой записи `C3-04` оставалась [~].

### 2026-07-19 — C3-09
- **Запрос:** ок, C3-09 — promote из reserve после recommendation action.
- **Сделано:** `list_view` → `refill_active=True`; HAPPY_PATH §4; тесты promote + UI передаёт True; capture script `capture_recommendation_after_action.py`.
- **Проверка:** pytest deck/desktop; captures `screens/tmp_ui/C3-09/after_{100,125}.png` + Read.
- **Не сделано / next:** не TMDb auto-replenish; не C3-04.

### 2026-07-19 — Диагностика: колода не обновляется после действия
- **Запрос:** запас есть; после убирания карточки колода не обновляется («пул не пополняется»).
- **Симптом:** reserve/запас есть; после смотрел/сохранить/скрыть active не добирается.
- **Root cause:** UI вызывает `RecommendationDeckService.apply_action_and_refill(..., refill_active=False)` в `desktop/candidates/list_view.py` (~1227). Сервис умеет promote из reserve при `True`; Recommendations отключают это намеренно.
- **Контракт:** HAPPY_PATH / C1-05 — конечная колода **уменьшается** после действия; тест `test_finite_active_deck_does_not_promote_reserve_after_action`.
- **Не релевантно:** TMDb replenish / Apply / `auto_pool_refill` / C3-07 safety — другой контур.
- **Код:** не менялся (диагностика only).
- **Next:** если нужен UX «убрал → подтянул из запаса до 10» — Scope Gate + новый roadmap ID + правка HAPPY_PATH/теста; без явного `ок, <ID>` не делать.

### 2026-07-19 — C3-08
- **Запрос:** ок/делай C3-08 — Consistent RU metadata selection and fallback (QA-DEFECT-02).
- **Сделано:** enrichment мержит `localized` title/overview без требования poster; `tmdb_localized_checked_at`; `choose_display_*` / legacy builder: selected → primary → en → original; пустые строки skip; `--data-language` в `capture_readme.py`.
- **Проверка:** 16 targeted pytest; captures `after_100.png` / `after_125.png` Read — Breaking Bad как «Во все тяжкие» + RU overview; chrome RU; без mass migration.
- **Не сделано / next:** не C3-04; не ranking/safety; screens не коммитить.

### 2026-07-19 — C3-07
- **Запрос:** ок, C3-07 — Block explicit sexual content from safe recommendation eligibility (QA-DEFECT-01).
- **Сделано:** `candidates/safety/explicit_content.py` (strong structural + cautious text); hard-drop в `_eligible_candidates`; soft reject в filter replenish; reason codes; fixtures для 95897 / romance / same-sex / ambiguous words; deck size + watched/hidden; локальный 2/2 PASS.
- **Файлы:** `candidates/safety/*`, `recommendation_deck_service.py`, `filter_replenisher.py`, `result.py`, `tests/test_explicit_content_safety.py`, PRODUCT + cursor-work.
- **Проверка:** 44 pytest (safety + deck) green.
- **Не сделано / next:** не DEFECT-02; не C3-04; не wipe pool; не adult UI.

### 2026-07-19 — C3-06
- **Запрос:** ок, C3-06 — Safe isolated launcher for recommendation QA audits.
- **Сделано:** `tools/qa/run_recommendation_audit.py` + `isolation.py` + `verify_isolation_child.py` + README; parent не импортирует `config.constant`; child доказывает `APP_DATA_DIR` внутри runtime; отказ на real APPDATA / пустой root.
- **Проверка:** 7 pytest `tests/test_qa_isolated_launcher.py`; CLI smoke ok/fail. Journal: предотвращает повтор QA-DEFECT-03; **не** чистит возможное загрязнение реального профиля.
- **Не сделано / next:** не DEFECT-01/02; не полный re-run C3-05.

### 2026-07-19 — C3-05
- **Запрос:** ок, C3-05 — полный QA audit без фиксов.
- **Сделано:** изолированный runtime; сценарии S1–S10 + N/A; safety repro Overflow 95897 2×; UI capture 1.0/1.25 + Read; отчёт `screens/tmp_ui/C3-05/AUDIT_REPORT.md`.
- **Дефекты:** QA-DEFECT-01 high (erotic in pool/DEFAULT eligibility); QA-DEFECT-02 medium (EN metadata on RU UI); QA-DEFECT-03 process isolation miss на первых runners.
- **Проверка:** product `.py` / UI / tests не менялись ради фиксов.
- **Не сделано / next:** не чинить; C3-04 сессии автора; новые ID на фиксы.

### 2026-07-19 — C3-04 (авторская сессия 1/3)
- **Запрос:** ок, делай C3-04.
- **Сделано:** собрана live-колода DEFAULT-режима из локального пула (184; watched=0, actioned=17, recently_seen=157 → 10 eligible, reserve пуст). Автор отметил интерес только к «В поисках Персефоны»: **1/10** при пороге ≥5. Агентская proxy-оценка 6/10 сохранена отдельно и не считается авторским результатом.
- **Артефакты:** `screens/tmp_ui/C3-04/session1_deck.json`, `session1_eval.json`, `session1_author_eval.json`.
- **Проверка:** код не менялся; ответ автора записан без подмены оценкой агента.
- **Не сделано / next:** ещё 2 авторские сессии; при повторном провале не закрывать C3-04 и разбирать причины отдельным roadmap ID.

### 2026-07-19 — C3-03
- **Запрос:** начинай (после gate на C3-03).
- **Сделано:** Recommendations не берёт saved discovery presets/vector через `startup_filters` при старте FiltersView; до Apply — только `DEFAULT_BROWSE_FILTERS` + `DEFAULT_RECOMMENDATION_VECTOR`. Пресеты остаются в форме «Настройки поиска».
- **Файлы / commit:** `desktop/candidates/{session,filters_view,list_view}.py`, tests, PRODUCT, `cursor-work.md`.
- **Проверка:** compileall; targeted pytest. UI не менялся (layout/copy).
- **Не сделано / next:** C3-04 — субъективная проверка автора ≥5/10.

### 2026-07-19 — C3-02
- **Запрос:** коммит и следующий шаг после C3-01.
- **Сделано:** genre affinity из watched ratings (TOP/OK/NOT_FOR_ME/unscored) + saved (+) / hidden (−); влияет на `_personal_fit_score` / rank в build/top-up/promote; сами title по-прежнему hard-exclude.
- **Файлы / commit:** `candidates/recommendation_deck_service.py`, deck tests, PRODUCT, `cursor-work.md`.
- **Проверка:** compileall; 31 pytest deck service. UI не менялся.
- **Не сделано / next:** C3-03 — один режим по умолчанию вместо пресетов.

### 2026-07-19 — C3-01
- **Запрос:** коммит/пуш D1-03 и следующий шаг по плану.
- **Сделано:** в `_eligible_candidates` hard-drop junk genres (`reality`, `talk_show`, `news`, `game_show`, `soap`) даже при `mood=any`; soap в `genre_schema` (TMDb 10766).
- **Файлы / commit:** `candidates/recommendation_deck_service.py`, `candidates/models/genre_schema.py`, deck tests, PRODUCT, `cursor-work.md`.
- **Проверка:** compileall; 53 pytest passed (deck/intent/schema). UI не менялся.
- **Не сделано / next:** C3-02 — сильнее опираться на watched/saved/hidden.

### 2026-07-19 — D1-03
- **Запрос:** выровнять `main_agents.md`, `docs/README.md`, корневой `README.md` с PRODUCT Phase C; без кода.
- **Сделано:** `main_agents` → короткий pointer; `docs/README` — индекс без битых ops и без «пул» как продукта; корневой README — inbox ≤10, три действия, без pool/reserve/фильтров как user features; A/B/V0 явно parking.
- **Файлы / commit:** `main_agents.md`, `docs/README.md`, `README.md`, PRODUCT, `cursor-work.md`.
- **Проверка:** ручная проверка ссылок на существующие пути; diff без `.py`.
- **Не сделано / next:** C3-01 после «ок»; авторские 5 сессий для §3.

### 2026-07-19 — C2-07
- **Запрос:** сразу C2-06 + C2-07, коммит между ними.
- **Сделано:** smoke S1–S6 на Recommendations; зафиксирован **N≈0.6 с** (warm, gate skipped → preparing/list); фаза C2 отмечена пройденной. §3 S1–S6 не отмечались — нужны 5 авторских сессий в разные дни.
- **Файлы / commit:** PRODUCT, `cursor-work.md`; скрины `screens/tmp_ui/C2-07/` (не в commit).
- **Проверка:** timing smoke + capture preparing/ready 1.0/1.25 + Read PNG. A–E: да по smoke/prior C1–C2.
- **Не сделано / next:** C3-01; авторские 5 сессий для §3.

### 2026-07-19 — C2-06
- **Запрос:** сразу C2-06 и C2-07, между ними коммит.
- **Сделано:** UI copy без «пул»/pool (Filters + Settings + counters); checkbox пополнения сеется из `auto_pool_refill` (default on) — одно действие «Обновить колоду» / «Ещё варианты».
- **Файлы / commit:** `desktop/i18n/catalog.py`, `desktop/candidates/filters_form.py`, targeted tests, PRODUCT, `cursor-work.md`; commit `f825ce0`.
- **Проверка:** 17 pytest passed; capture `screens/tmp_ui/C2-06/` + Read PNG.
- **Не сделано / next:** C2-07.

### 2026-07-19 — C2-05
- **Запрос:** коммит C2-04 и следующий шаг — повторный запуск без напоминаний про токен/фильтры.
- **Сделано:** при сохранённом TMDb-токене и сбое сети gate больше не открывает форму токена, а уходит в local continue; completed onboarding по-прежнему не открывается после pass. Добавлены regression-тесты warm/missing token и skip wizard.
- **Файлы / commit:** `desktop/startup/tmdb_gate.py`, `tests/test_tmdb_startup_gate.py`, PRODUCT, `cursor-work.md`; commit C2-04 уже `c4cbc27`, C2-05 — отдельным commit.
- **Проверка:** compileall; `tests/test_tmdb_startup_gate.py` 20 passed; capture `screens/tmp_ui/C2-05/` + Read PNG 1.0 / 1.25.
- **Не сделано / next:** C2-06 — пополнение без термина «локальный пул» в UI.

### 2026-07-19 — C2-04
- **Запрос:** заменить технические status-сообщения на человеческие RU.
- **Сделано:** в `desktop/i18n/catalog.py` убраны «пул» / «локальн*» / CDN / «источник кандидатов» из status, empty, deck_reserve, discovery status и replenish progress copy (RU+EN); regression test на жаргон.
- **Файлы / commit:** `desktop/i18n/catalog.py`, `tests/desktop/test_candidate_search_behavior.py`, PRODUCT, `cursor-work.md`; commit `c4cbc27`.
- **Проверка:** compileall; 6 pytest passed; capture `screens/tmp_ui/C2-04/` (preparing/error/after × 1.0/1.25) + Read PNG.
- **Не сделано / next:** C2-05 — повторный запуск не напоминает про токен и фильтры.

### 2026-07-19 — C2-02
- **Запрос:** оставить два основных состояния колоды и отдельное error-состояние.
- **Сделано:** `recommendationsDeckStack.workflowState` явно фиксирует `preparing` до reveal и `ready` после него; `error` выделен отдельно. Для пустой Recommendations replenishment теперь использует общий preparing-screen и не создаёт третью основную поверхность.
- **Файлы / commit:** `desktop/candidates/list_view.py`, targeted Qt tests, `tools/screenshots/capture_readme.py`, PRODUCT, happy path, `cursor-work.md`; commit будет создан отдельным шагом.
- **Проверка:** compileall; targeted Qt pytest с `PYTEST_QT_API=pyqt6`; native capture + Read PNG 1.0 / 1.25.
- **Не сделано / next:** C2-04 — заменить технические status-сообщения на человеческие RU-формулировки.

### 2026-07-19 — C2-01
- **Запрос:** сделать единый empty/loading overlay в правой области Recommendations.
- **Сделано:** loading-экран использует один явно именованный overlay с copy «Подготавливаем рекомендации» и прогрессом постеров; capture умеет снять именно это состояние без подмены runtime-данных.
- **Файлы / commit:** `desktop/candidates/list_view.py`, `tests/desktop/test_candidate_deck_reveal.py`, `tools/screenshots/capture_readme.py`, PRODUCT, happy path, `cursor-work.md`; commit будет создан отдельным шагом.
- **Проверка:** compileall; targeted Qt pytest с `PYTEST_QT_API=pyqt6`; native capture + Read PNG 1.0 / 1.25.
- **Не сделано / next:** C2-02 — закрепить только preparing / ready как основные состояния и отдельный error.

### 2026-07-19 — C2-03
- **Запрос:** показывать колоду с постерами через один экран ожидания.
- **Сделано:** готовая колода больше не открывается до первой poster batch; `recommendationsDeckLoadingPage` остаётся единственным экраном ожидания и закрывается после готовности партии или fallback.
- **Файлы / commit:** `desktop/candidates/list_view.py`, `tests/desktop/test_candidate_deck_reveal.py`, PRODUCT, `cursor-work.md`; commit будет создан отдельным шагом по запросу.
- **Проверка:** compileall; targeted Qt pytest 7 passed с `PYTEST_QT_API=pyqt6`; capture + Read PNG 1.0 / 1.25.
- **Не сделано / next:** C2-01 / C2-02 — привести loading/empty/error к единому контракту состояний.

### 2026-07-19 — C1-06
- **Запрос:** сделать три действия на карточке рекомендаций одновременно доступными и понятными.
- **Сделано:** оценка для действия «смотрел» получила явную подпись «Смотрел — оцените»; «+ Запомнить» и «× Не показывать» сохранены отдельными видимыми кнопками.
- **Файлы / commit:** i18n, UI-regression test, PRODUCT, `HAPPY_PATH_INBOX.md`, `cursor-work.md`; commit будет создан отдельным шагом по запросу.
- **Проверка:** compileall; targeted Qt pytest 4 passed с `PYTEST_QT_API=pyqt6`; capture + Read 1.0 / 1.25.
- **Не сделано / next:** C2-03 — показывать колоду с постерами через один экран ожидания.

### 2026-07-19 — C1-05
- **Запрос:** сделать конечную пользовательскую колоду до 10 карточек и одну CTA после её окончания.
- **Сделано:** `ACTIVE_DECK_SIZE` = 10; действия не подставляют резервные карточки в активную колоду; «Ещё варианты» появляется только после последней карточки; сохранённые колоды старого размера инвалидируются версией схемы.
- **Файлы / commit:** `candidates/recommendation_deck_service.py`, `desktop/candidates/list_view.py`, i18n, тесты, PRODUCT, `HAPPY_PATH_INBOX.md`, `cursor-work.md`; commit будет создан отдельным шагом по запросу.
- **Проверка:** compileall; service 29 passed; reserve 12 passed; Qt targeted 3 passed и orchestration 2 passed с `PYTEST_QT_API=pyqt6`; capture + Read PNG 1.0 / 1.25.
- **Не сделано / next:** C1-06 — три действия на карточке сделать однозначными с первого взгляда.

### 2026-07-19 — C1-04
- **Запрос:** скрыть с главного экрана Recommendations вайб-контролы и лишние пресеты.
- **Сделано:** подтверждён и закреплён regression-тестом контракт: пресеты и вайб-контролы находятся только в отдельной вкладке «Настройки поиска», а не в `CandidateListView`.
- **Файлы / commit:** `tests/test_desktop.py`, PRODUCT, `HAPPY_PATH_INBOX.md`, `cursor-work.md`; commit будет создан отдельным шагом по запросу.
- **Проверка:** targeted pytest; capture Recommendations и Read PNG на 1.0 / 1.25.
- **Не сделано / next:** C1-05 — ограничить пользовательскую колоду десятью карточками и показать единственную CTA после её окончания.

### 2026-07-19 — C1-03
- **Запрос:** выполнить daily path без обязательного перехода в «Настройки поиска».
- **Сделано:** закреплено, что Recommendations строит колоду на `DEFAULT_BROWSE_FILTERS`, когда пользователь не открывал форму поиска; добавлен регрессионный тест этого инварианта.
- **Файлы / commit:** `desktop/candidates/list_view.py`, `tests/test_desktop.py`, PRODUCT, `cursor-work.md`; commit не создан — не запрашивался.
- **Проверка:** targeted pytest; capture Recommendations и Read PNG на 1.0 / 1.25.
- **Не сделано / next:** `C2-01` остаётся активным ID.

### 2026-07-19 — C0-03
- **Запрос:** синхронизировать строгий план и текущий рабочий ID.
- **Сделано:** PRODUCT назначен единственным источником текущего ID; активный ID приведён к `C2-01` по PRODUCT §10; «вечерний путь» заменён на путь разбора рекомендаций; C2-02 описывает два основных и отдельное error-состояние; дублирующий backlog удалён из этого журнала.
- **Файлы / commit:** `docs/contracts/PRODUCT_ROADMAP_CONTRACT.md`, `cursor-work.md`; commit создан в этой сессии.
- **Проверка:** docs-only review: активный ID, следующий ID и порядок PRODUCT §10 согласованы.
- **Не сделано / next:** `C2-01` — только после нового Scope Gate и явного «ок».

### 2026-07-19 — C0-02
- **Запрос:** задать строгий критерий проверки продуктовой гипотезы.
- **Сделано:** добавлены условия подтверждения после C3 и правило опровержения: при провале не открывать A/B/V0 и C4 автоматически.
- **Файлы / commit:** `docs/contracts/PRODUCT_ROADMAP_CONTRACT.md`, `cursor-work.md`; commit создан в этой сессии.
- **Проверка:** docs-only review: S1–S6 отделены от проверки реальной полезности inbox.
- **Не сделано / next:** провести проверку только после рабочего C1–C3.

### 2026-07-19 — C0-01
- **Запрос:** зафиксировать конкретную продуктовую постановку задачи.
- **Сделано:** в PRODUCT добавлена гипотеза: автор разбирает небольшую колоду неизвестных кандидатов, чтобы поддерживать актуальные watched / saved / hidden без бесконечного каталога; обозначены проблема, альтернатива и ожидаемый результат сессии.
- **Файлы / коммит:** `docs/contracts/PRODUCT_ROADMAP_CONTRACT.md`; включён в общий docs commit C0-01…C0-03.
- **Проверка:** docs-only review: формулировка не добавляет V0, A/B, web или новую продуктовую функцию.
- **Не сделано / next:** C0-02 и C0-03 выполнены в следующих записях; следующий рабочий ID — `C2-01`.

### 2026-07-19 — C1-02
- **Запрос:** сделать C1-02, коммит, отдельный блок UX
- **Сделано:** `docs/contracts/HAPPY_PATH_INBOX.md` — 6 шагов, маппинг смотрел→оценка / сохранить / скрыть, чеклист, разрывы → C1-03…C1-06; ссылки в PRODUCT §6 и AGENTS; C1-02 `[x]`; фокус → C1-03
- **Файлы / коммит:** `5a42533` (`HAPPY_PATH_INBOX.md`, PRODUCT, AGENTS, cursor-work)
- **Проверка:** capture → `screens/tmp_ui/C1-02/` + Read (deck_list, deck_ready, rating); A–E: да/частично по таблице в HAPPY_PATH; код UI не меняли
- **Не сделано / next:** C1-03; размер колоды 10 и одна CTA (C1-05); явные 3 кнопки (C1-06)

### 2026-07-19 — C1-01
- **Запрос:** коммит docs (`cursor-work`) + первый шаг C1-01
- **Сделано:** Recommendations = default shell tab; `DEFAULT_SHELL_TAB_ID`; focus после build и после TMDb gate без onboarding; PRODUCT + тесты
- **Файлы / коммит:** `25179cc` → `origin/main` (`tabs.py`, `main_window.py`, tests, PRODUCT, cursor-work)
- **Проверка:** 6 pytest зелёные; скрин `screens/tmp_ui/C1-01/after_100.png` (Read): вкладка «Рекомендации» первая и активная; A да, B да (список), C н/д (не цель), D да, E 1.0 only (layout не трогали)
- **Не сделано / next:** C1-02; колода 25→10; empty overlay

### 2026-07-19 — создать `cursor-work.md`
- **Запрос:** вести md-отчёт по изменениям `cursor-work.md`
- **Сделано:** файл создан; зафиксирован снимок состояния и бэклог сессий D0–X
- **Файлы / коммит:** `d91eef2` → `origin/main`
- **Проверка:** docs only
- **Не сделано / next:** код C1-01 (сделан в записи выше)

### 2026-07-19 — канон вариант X
- **Запрос:** зафиксировать X (inbox), обновить docs, commit + push
- **Сделано:** PRODUCT v1.4 — inbox vs «вечер»; A/B/V0 = parking; обновлены README, AGENTS, rules
- **Файлы / коммит:** `a80b7ea` → `origin/main`
- **Проверка:** docs only
- **Не сделано / next:** C1-01

### 2026-07-18 — Scope Gate (S0)
- **Запрос:** строгий STOP перед out-of-scope кодом
- **Сделано:** секция Scope Gate в AGENTS; `.cursor/rules/scope-gate.mdc`; PRODUCT v1.3
- **Файлы / коммит:** `fa9e003`
- **Проверка:** docs only
- **Не сделано / next:** —

### 2026-07-18 — AGENTS UI DoD (D1-D)
- **Запрос:** дописать визуал, скрины, capture-скрипты, happy path
- **Сделано:** полный AGENTS DoD + `product-phase-c.mdc`
- **Файлы / коммит:** вошло в `2a78df0` / уточнения рядом с S0
- **Проверка:** docs only

### 2026-07-18 — D1 docs cleanup + RU
- **Запрос:** архив отчётов/планов, русская документация, хаб
- **Сделано:** reports/plans → `internal/archive/docs/`; активные contracts/arch/ops на RU; корневой AGENTS
- **Файлы / коммит:** `2a78df0`
- **Проверка:** `tests/test_runtime_reports.py` — 12 passed (путь template → archive)
- **Не сделано / next:** не коммитили `screens/`, `desktop/images/ui_9*`, шум `start_app.py`

### 2026-07-17 — D0 PRODUCT_ROADMAP
- **Запрос:** контракт продукта и roadmap с чекбоксами
- **Сделано:** создан `PRODUCT_ROADMAP_CONTRACT.md`; колода 10; scales 1.0/1.25
- **Файлы / коммит:** позже вошло в docs-коммиты
- **Проверка:** docs only

---

Текущий рабочий ID и порядок задач берутся только из PRODUCT §7 и §10; этот файл — журнал, не второй roadmap.
