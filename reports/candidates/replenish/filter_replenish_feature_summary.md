# Filter Replenish Feature Summary

## Module Boundary

- `candidates/replenish/` owns intent normalization, compatibility, planning, Discover request guardrails, mocked replenish execution, result shaping, and sanitized reports.
- `candidates/service.py` is the save/merge facade. It imports TMDb candidates through the existing common-pool path, preserving SQLite and FTS rebuild behavior.
- `desktop/candidates/` owns GUI controls, status text, async worker wiring, cache invalidation, and filter reapply. It does not call TMDb or mutate SQLite directly.

## GUI Controls

- The replenish section is explicit and default-safe: the checkbox is unchecked by default.
- Controls cover preset, animation mode, vibe, release preference, origin preference, and advanced override.
- Help text clarifies that countries are TMDb origin countries, anime expects JP + animation-only, live-action excludes animation, and advanced override is for unusual manual combinations.

## Apply Flow

- Normal Apply behavior is unchanged when the replenish checkbox is unchecked.
- When checked, the UI first applies local filters, records the local visible count, then runs replenish in a background worker through the service seam.
- On success, filter chip options reload, the session invalidates its pool cache with `reload_from_pool(force=True)`, and the same filters/text query/sort mode are reapplied once.
- Status reports local count before replenish, added count, and visible count after reapply.
- Compatibility conflicts stop before the TMDb/service replenish call and report `Conflict: no TMDb call`.

## Target 30 Enforcement

- The GUI uses an explicit default batch size of 30.
- Batch size is clamped to `1..30` before building the replenish intent.
- The domain intent also normalizes `target_add_count`, so service and direct domain callers share the same safety limit.

## Mock Quality Results

- scenario_count: 6
- total_requested: 180
- total_saved: 139
- total_duplicates: 8
- guardrail_violations: 0

Scenario summary:

| Scenario | Saved | Fill rate | Duplicates | Guardrails |
|---|---:|---:|---:|---:|
| A. RU dark TV | 30/30 | 1.00 | 0 | 0 |
| B. Anime JP | 30/30 | 1.00 | 0 | 0 |
| C. K-drama KR | 30/30 | 1.00 | 0 | 0 |
| D. US/GB new movies | 30/30 | 1.00 | 0 | 0 |
| E. Sparse TR | 5/30 | 0.17 | 0 | 0 |
| F. Duplicate-heavy | 14/30 | 0.47 | 8 | 0 |

## Guardrails Status

- Initial Discover params do not include `vote_count.gte` or `vote_average.gte`.
- No broad-origin fallback is used.
- Country-first TMDb discovery uses `with_origin_country`.
- Animation is first-class: `any`, `animation_only`, and `live_action_only`.
- Tests use mocked TMDb clients.

## Verification

- `py -m compileall candidates desktop tests scripts`: passed.
- `py -m pytest tests/test_onboarding_autofill.py -q`: 86 passed.
- `py -m pytest tests/test_candidate_fts_index.py tests/test_search_fts_integration.py -q`: 17 passed.
- `py -m pytest tests/candidate_modules tests/test_runtime_reports.py -q`: 57 passed.
- `py -m pytest tests/test_filter_replenish_intent.py tests/test_filter_replenish_compatibility.py tests/test_filter_replenish_plan.py tests/test_filter_replenish_discover_guardrails.py tests/test_filter_replenish_mocked.py tests/test_filter_replenish_quality_metrics.py -q`: 118 passed.
- `py scripts/reports/run_filter_replenish_quality_report.py --mock --all --output reports/candidates/replenish/mock_filter_replenish_quality.md --json-output reports/candidates/replenish/mock_filter_replenish_quality.json`: passed.

## Known Risks

- Live TMDb was not run in this step; verification is mocked only.
- Sparse and duplicate-heavy scenarios can underfill below 30 by design rather than using unsafe broad fallback.
- Worker cancellation and broader UI polish remain for later hardening/visual queue steps.

## Live TMDb Status

- not_run
