# Filter Replenish Preflight Audit

Date: 2026-07-10

## Scope

This audit maps the existing Candidates filter UI, local search flow, onboarding replenish flow, and SQLite save path before adding filter-driven candidate replenish. No product behavior changes are included in this step.

## Current Candidates Filter Controls

`desktop/candidates/filters_view.py` owns the Filters tab orchestration. `CandidateFiltersView._collect_filters()` currently returns the runtime local-search filter dict:

- `criteria_name`
- `source`
- `country`
- `media_type`
- `year_min`
- `year_max`
- `include_genres`
- `exclude_genres`
- `min_tmdb_score`
- `min_tmdb_votes`
- `only_complete`
- `only_unwatched`
- `hide_hidden`

The widgets are built in `desktop/candidates/filters_form.py` by `build_filters_form()`. Current sections are basic filters, genres, TMDb thresholds, and visibility. Country and genre controls are chip selectors; media type is a combo; years and TMDb thresholds use range sliders; visibility uses checkboxes.

`CandidateFiltersView._apply_filter_defaults()` loads defaults and chip options through `candidates.service`:

- `get_search_filter_defaults_view()`
- `get_search_filter_chip_options_view()`

There is no replenish-specific control yet, and Apply currently has no network or storage side effect.

## Current Apply Flow

The Apply button calls `CandidateFiltersView._apply_filters()`.

Flow:

1. collect widget values through `_collect_filters()`;
2. pass them through `on_before_apply()` extension hook;
3. call `CandidateSearchSession.apply_filters_async(filters, parent=...)`;
4. `CandidateSearchWorker` loads/searches/sorts using the injected service facade;
5. `CandidateSearchSession._apply_search_result()` updates in-memory filtered candidates and notifies listeners.

`CandidateSearchSession.reload_from_pool(force=True)` already exists for post-mutation refresh. It invalidates cached overview and reapplies the last filters synchronously.

## Existing Onboarding Replenish Path

`desktop/onboarding/worker.py` contains `PoolReplenishWorker`, which calls `candidate_service.replenish_candidate_pool(cancel_checker=...)`.

`candidates.service.replenish_candidate_pool()`:

- checks `get_pool_replenish_view()`;
- loads the last onboarding profile from SQLite settings;
- calls `run_onboarding_autofill(..., target=missing)`;
- returns a dict payload from `_autofill_result_to_dict()`.

This path is saved-profile based. It does not use the current Candidates filter UI intent.

## Taste Preset And Compatibility Modules

`candidates/onboarding/taste_presets.py` defines the preset contract and normalization:

- preset ids such as `anime`, `k_drama`, `family_animation`, `russian_mainstream`, `manual`;
- `media_type`: `movie`, `tv`, `both`;
- `animation_mode`: `any`, `animation_only`, `live_action_only`;
- selected origin countries with a max of five manual countries;
- genre groups, vibe, and release preference.

`candidates/onboarding/compatibility.py` already checks preset/country/animation conflicts for onboarding, including anime and family animation requirements. It auto-fixes onboarding profiles by default. Filter replenish needs a separate plain-domain compatibility result because GUI filter runs should report warnings/blocking states without silently rewriting an already visible manual filter selection.

## Candidate Save, Merge, And FTS Path

The current TMDb import write path is:

1. `candidates.sources.tmdb.importer.import_tmdb_candidates_to_common_pool()`;
2. load existing pool through `candidates.repositories.pool_repository.load_candidate_pool()`;
3. normalize and dedupe incoming candidates against watched titles, TMDb identity, and storage keys;
4. update only when the incoming candidate has a better sort score;
5. save shared pool through `candidates.repositories.pool_repository.save_candidate_pool()`;
6. repository delegates to `storage.sqlite.candidate_pool_repository.save_candidate_pool_dict()`;
7. SQLite records are rewritten and `candidates.search.fts_index.rebuild_fts_index()` is called inside the same transaction.

This is the preferred merge/save/FTS path for filter replenish. GUI code should call a service facade and must not write SQLite directly.

## Existing Tests

Relevant current coverage:

- `tests/desktop/test_candidate_search_behavior.py`: filter UI, session cache reload, async stale result handling, FTS search path.
- `tests/candidate_modules/test_onboarding_taste_presets.py`: preset axes, anime compatibility, manual country caps, onboarding plan view.
- `tests/candidate_modules/test_pool_dedupe.py`: pool dedupe and merge behavior.
- `tests/test_search_fts_integration.py`, `tests/test_search_core.py`, and search-related tests: FTS/index/search behavior.
- `tests/test_sqlite_candidate_*`, `tests/test_sqlite_indexed_queries.py`, `tests/test_sqlite_records.py`: SQLite candidate storage behavior.
- `tests/test_runtime_reports.py`: report output hygiene and onboarding report schema.
- TMDb-related tests mock network behavior through local harnesses; new filter replenish tests must not require live TMDb.

## Proposed Module Boundary

Add a plain Python package under `candidates/replenish/`:

- `filter_intent.py`: normalized GUI replenish intent contract;
- `compatibility.py`: warning/blocking compatibility result;
- `filter_plan.py`: bounded country/media/genre buckets;
- `discover_requests.py`: safe TMDb Discover request kwargs with guardrail tests;
- `mock_tmdb.py` or test fixtures: offline TMDb harness;
- `pipeline.py`: fetch, details, normalize, dedupe, merge via existing import/save path;
- `reports.py`: JSONL/markdown summary writer under `reports/candidates/replenish/`.

Add a desktop worker under `desktop/candidates/workers/` and expose it through `CandidateFiltersView` only via `candidates.service`.

## Expected Later Changed Files

Likely domain and service files:

- `candidates/replenish/__init__.py`
- `candidates/replenish/filter_intent.py`
- `candidates/replenish/compatibility.py`
- `candidates/replenish/filter_plan.py`
- `candidates/replenish/discover_requests.py`
- `candidates/replenish/pipeline.py`
- `candidates/replenish/reports.py`
- `candidates/service.py`

Likely desktop files:

- `desktop/candidates/filters_form.py`
- `desktop/candidates/filters_view.py`
- `desktop/candidates/session.py`
- `desktop/candidates/workers/replenish_worker.py`
- `desktop/i18n/catalog.py`
- theme/QSS files if the new control needs polish

Likely tests:

- `tests/test_filter_replenish_intent.py`
- `tests/test_filter_replenish_compatibility.py`
- `tests/test_filter_replenish_plan.py`
- `tests/test_filter_replenish_discover_requests.py`
- `tests/test_filter_replenish_pipeline.py`
- `tests/desktop/test_candidate_search_behavior.py`
- SQLite/FTS regression tests if the merge path gets a new public facade

## Stale Assumptions To Avoid

STALE ASSUMPTION: filter thresholds such as `min_tmdb_score` and `min_tmdb_votes` can be copied to initial TMDb Discover as `vote_average.gte` or `vote_count.gte`. This queue forbids those initial Discover parameters.

STALE ASSUMPTION: low-yield filters should fall back to a broad origin search. This queue forbids broad-origin fallback; underfill must be reported.

STALE ASSUMPTION: onboarding auto-fix behavior can be reused directly for Candidates GUI filters. GUI replenish needs explicit blocking/warning reporting because the user is applying visible filters.

STALE ASSUMPTION: saved pool import is JSON-first. Runtime storage is SQLite, and the existing repository save path rebuilds FTS.
