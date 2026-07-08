# Watchbane Night Cycle Final Report

Date: 2026-07-08  
Branch: `night-work`  
Base branch: `onboarding-fullscreen-scope-fix` lineage  
Latest commit at report time: pending

## Executive Summary

Implemented the night-cycle strategy harness, strengthened broad seed behavior, improved first-run onboarding source/plan/result UX, generated mock/live reports, and captured native onboarding screenshots.

## What Changed

- Added named onboarding autofill strategies.
- Extended result payload with strategy and rejection counters.
- Added strategy matrix support to `scripts/run_onboarding_pool_rebuild.py`.
- Added source selection to onboarding.
- Improved plan/final result copy and source contribution display.
- Added screenshot support for the new source step.
- Added reports and generated JSON artifacts.

## Files Changed

- `candidates/onboarding/autofill.py`
- `candidates/service.py`
- `desktop/onboarding/wizard.py`
- `desktop/onboarding/worker.py`
- `scripts/run_onboarding_pool_rebuild.py`
- `scripts/capture_onboarding.py`
- `tests/test_onboarding_autofill.py`
- `docs/nightly/*`
- `logs/reports/*`

## Onboarding Flow Changes

Flow now includes language/scale, taste questions, source selection, plan preview, loading, and final result. Local starter catalog is presented as planned, not available. Live TMDb remains the active build path.

## Pool Strategy Changes

Strategies available:

- `baseline_quota_fix`
- `broad_top_seed`
- `focused_first`
- `hybrid_quality_focused`
- `strict_underfill`

Seed pages are capped to one page per bucket/stage so live broad seed cannot starve focused/fallback queries.

## Strategies Tested

### baseline_quota_fix

Mock: all required scenarios reached 120 with quota integrity.

### broad_top_seed

Mock: all required scenarios reached 120 with quota integrity. Live: EN TV reached 120; RU scenarios underfilled honestly with warnings.

### focused_first

Mock: all required scenarios reached 120 with quota integrity.

### hybrid_quality_focused

Mock: all required scenarios reached 120 with quota integrity.

### strict_underfill

Mock: intentionally underfilled all required scenarios and emitted warnings.

## Mock Results

Detailed JSON: `logs/reports/nightly_strategy_comparison_mock_2026-07-08.json`

| Strategy | Scenario | Created/Target | Quota Integrity | Warnings |
| --- | --- | ---: | --- | --- |
| baseline_quota_fix | all 3 | 120/120 | pass | none |
| broad_top_seed | all 3 | 120/120 | pass | none |
| focused_first | all 3 | 120/120 | pass | none |
| hybrid_quality_focused | all 3 | 120/120 | pass | none |
| strict_underfill | all 3 | 63-67/120 | underfilled | explicit |

## Live Results

Detailed JSON: `logs/reports/nightly_strategy_comparison_live_2026-07-08.json`

| Strategy | Scenario | Created/Target | Quota Integrity | Requests |
| --- | --- | ---: | --- | ---: |
| broad_top_seed | en-tv-new-dark | 120/120 | pass | 37 |
| broad_top_seed | ru-balanced | 91/120 | underfilled with warnings | 180 |
| broad_top_seed | ru-domestic-movie-classic-light | 88/120 | underfilled with warnings | 180 |

## Best Strategy

Keep `broad_top_seed` as default. It balances quality seed, focused matching, hard bucket integrity, source explainability, and honest underfill behavior.

## Rejected Strategies

- `baseline_quota_fix`: reliable but no quality reservoir.
- `focused_first`: good candidate for strong preference mode, but less broad-quality oriented.
- `hybrid_quality_focused`: promising but harder to explain as default.
- `strict_underfill`: useful for warnings/regression testing, not default UX.

## UI Screenshot Review

Screenshots:

- `screens/tmp_ui/onboarding/source_selection_scale100.png`
- `screens/tmp_ui/onboarding/plan_preview_scale100.png`
- `screens/tmp_ui/onboarding/loading_scale100.png`
- `screens/tmp_ui/onboarding/final_scale075.png`
- `screens/tmp_ui/onboarding/final_scale100.png`
- `screens/tmp_ui/onboarding/final_scale15.png`

Visual review was performed through image viewer. No clipping/overlap was observed in inspected captures.

## Verification

- `py -m pytest tests\test_onboarding_autofill.py -q`: passed, 25 tests.
- `py -m compileall candidates desktop scripts`: passed.
- Mock strategy matrix: passed.
- Limited live smoke: completed.
- Native screenshots: saved and inspected.

## Known Risks

- RU-heavy live scenarios still underfill at the current request budget.
- Loading progress copy can be made more product-friendly.
- Local starter catalog remains a planned gap.

## Recommended Merge Gate

Before merge, review whether RU live underfill is acceptable for first-run UX or whether the next cycle should add a local starter catalog / RU curated fallback.

## Recommended Next Cycle

Build a token-safe/local starter source or RU starter reservoir, then improve loading copy and add a compact result details expander.
