# Current State Audit

Date: 2026-07-08
Branch: night-work

## Branch

- Current branch: `night-work` tracking `origin/night-work`.
- Recent committed work already includes candidate filter refresh/sort fixes and broad quality seed support.

## Dirty Working Tree

- Existing unstaged deletions under `.codex-onboarding-fullscreen/` are present before this night cycle.
- They are unrelated to the onboarding/pool work and are intentionally left unstaged.

## Read Files

- `README.md`
- `docs/AGENTS.md`
- `candidates/AGENTS.md`
- `candidates/onboarding/autofill.py`
- `candidates/service.py`
- `desktop/onboarding/wizard.py`
- `desktop/onboarding/worker.py`
- `scripts/run_onboarding_pool_rebuild.py`
- `tests/test_onboarding_autofill.py`
- night prompt pack files `00` through `08`

## Current Onboarding Flow

- Startup shows `OnboardingAutofillDialog` inside the main window stack, not as a small independent modal.
- Existing screens: language/scale, taste questions, plan preview, loading/progress, final result.
- RU users get the origin question; EN users skip it.
- Skip/open Candidates path exists.
- Missing product step: explicit source selection. The current flow effectively means live TMDb autofill or skip.

## Current Autofill Flow

- `build_fetch_buckets()` computes hard parent quotas for media and, for RU, origin.
- `build_discover_request()` builds focused/fallback TMDb discover requests.
- Acceptance is centralized in `candidate_rejection_reason()` and write path is through `run_onboarding_autofill()`.
- Current default query order already includes `origin_top_seed`, `quality_seed`, then focused/fallback stages.
- Underfill warnings are produced by `_build_warnings()` after planned vs actual counts are computed.

## Current Result Payload

- Service returns `created_count`, `pool_size`, `api_requests`, `warnings`, `planned_counts`, `actual_counts`, `source_stats`, `rejected_future_count`, and candidates.
- Missing for experiment comparison: named strategy, broader rejection counters, and explicit quota-mismatch counters.

## Current Tests

- `tests/test_onboarding_autofill.py` covers quota weights, discover params, hard media/origin underfill, future rejection, broad seed isolation, and existing scenario quota integrity.
- UI startup cache invalidation is covered in `tests/test_desktop.py`.

## Screenshot Tooling

- `scripts/capture_onboarding.py` exists for native onboarding screenshots.
- `scripts/capture_onboarding_wizard.py` also exists for wizard screenshots.
- `scripts/capture_film_card.py` must not be used for this cycle.

## Risks

- Strategy harness should not silently change production behavior.
- Broad top candidates must not cross media/origin buckets.
- Source selection must not promise an unavailable local starter catalog.
- Native screenshot checks can be limited by environment/windowing availability.

## Proposed File Change List

- `candidates/onboarding/autofill.py`: strategy names/order, result strategy/rejection stats.
- `candidates/service.py`: pass strategy and expose result fields.
- `desktop/onboarding/worker.py`: pass strategy through worker.
- `desktop/onboarding/wizard.py`: source selection, clearer plan/result copy, source stats display.
- `scripts/run_onboarding_pool_rebuild.py`: `--strategy`, `--strategy-matrix`, richer JSON metrics.
- `tests/test_onboarding_autofill.py`: strategy and metrics regressions.
- `docs/nightly/*`, `logs/reports/*`: night-cycle reports.

## Next Phase Recommendation

Add a minimal strategy switch that preserves current default behavior, then extend the existing scenario runner to emit comparable strategy reports in mock mode.
