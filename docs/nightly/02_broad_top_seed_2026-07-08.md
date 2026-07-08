# Broad Top Seed

Date: 2026-07-08  
Branch: `night-work`

## Implementation Summary

The broad seed stage is implemented as a reservoir inside the existing hard bucket loop. It does not increase final pool size and cannot save more than `STARTER_POOL_TARGET`.

Current broad order for `broad_top_seed`:

1. `origin_top_seed` for RU domestic buckets.
2. `quality_seed`.
3. `focused`.
4. fallback stages inside the same hard bucket.

## Hard Bucket Safety

- Media quota remains hard.
- RU origin quota remains hard.
- Global broad top cannot fill RU domestic unless RU origin is verified.
- Movie-shaped results cannot fill TV buckets.
- Future/unreleased titles are rejected by date checks.

## Live Defect Found and Fixed

Live smoke showed that seed stages with many TMDb pages could consume the request budget before focused queries. Seed stages are now capped to one page per bucket/stage, preserving the reservoir behavior while leaving budget for focused/fallback queries.

Regression added: `test_broad_seed_pages_do_not_starve_focused_queries`.

## Changed Files

- `candidates/onboarding/autofill.py`
- `tests/test_onboarding_autofill.py`
- `scripts/run_onboarding_pool_rebuild.py`

## Mock Result

In mock matrix runs, `broad_top_seed` produced `120/120` for all required scenarios with quota integrity passing.

## Live Result

Limited live smoke on `broad_top_seed`:

| Scenario | Created | Quota Integrity | Requests | Source Mix |
| --- | ---: | --- | ---: | --- |
| `en-tv-new-dark` | 120 | pass | 37 | quality + focused |
| `ru-balanced` | 91 | underfilled with warnings | 180 | origin seed + quality + focused + fallback |
| `ru-domestic-movie-classic-light` | 88 | underfilled with warnings | 180 | origin seed + quality + focused + fallback |

## Risk

RU domestic availability remains constrained in live TMDb even after focused/fallback stages. This is acceptable only because underfill warnings and planned/actual counts are explicit.
