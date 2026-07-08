# Strategy Comparison

Date: 2026-07-08  
Branch: `night-work`

## Mock Matrix

Full mock matrix was run for 5 strategies across 3 required scenarios.

| Strategy | Scenario Coverage | Quota Integrity | Notes |
| --- | --- | --- | --- |
| `baseline_quota_fix` | 3/3 at 120 | pass | Reliable, no broad source contribution. |
| `broad_top_seed` | 3/3 at 120 | pass | Best explainability and quality source mix. |
| `focused_first` | 3/3 at 120 | pass | More personalized first, still uses seed later. |
| `hybrid_quality_focused` | 3/3 at 120 | pass | Same as broad for mixed, focused-first for strong profiles. |
| `strict_underfill` | 0/3 at 120 | honest underfill | Useful as a guardrail strategy, not a default. |

Detailed mock report:

- `docs/nightly/03_strategy_comparison_mock_2026-07-08.md`
- `logs/reports/nightly_strategy_comparison_mock_2026-07-08.json`

## Live Smoke

Live was run only for `broad_top_seed` to avoid excessive API usage from a full matrix.

| Scenario | Created/Target | Quota Integrity | Requests | Warnings |
| --- | ---: | --- | ---: | --- |
| `en-tv-new-dark` | 120/120 | pass | 37 | none |
| `ru-balanced` | 91/120 | underfilled | 180 | explicit media/origin underfill |
| `ru-domestic-movie-classic-light` | 88/120 | underfilled | 180 | explicit media/origin underfill |

Live artifacts:

- `docs/nightly/03_strategy_comparison_live_2026-07-08.md`
- `logs/reports/nightly_strategy_comparison_live_2026-07-08.json`

## Best Strategy

Recommended default remains `broad_top_seed`.

Reasons:

- Preserves hard quota acceptance.
- Gives quality reservoirs before narrow focused queries.
- Exposes source contribution counters.
- Produces full mock pools with planned/actual integrity.
- In live, underfills RU-heavy cases honestly instead of cross-filling.

## Rejected As Default

- `baseline_quota_fix`: stable but lacks broad quality reservoir.
- `focused_first`: good fallback option, but less direct quality-seed explainability.
- `hybrid_quality_focused`: promising but more complex to explain.
- `strict_underfill`: useful for testing warnings, not for normal users.
