# Pool Experiment Harness

Date: 2026-07-08  
Branch: `night-work`

## Summary

Added an explicit onboarding autofill strategy switch and extended the isolated scenario runner so pool strategies can be compared on the same profiles without touching the active user database.

## Strategies

- `baseline_quota_fix`: focused/fallback flow without broad seed stages.
- `broad_top_seed`: origin top seed, quality seed, focused, then fallback.
- `focused_first`: focused first, then seed reservoirs, then fallback.
- `hybrid_quality_focused`: broad-first for mixed profiles, focused-first for stronger profiles.
- `strict_underfill`: focused-only, intentionally less fallback.

## CLI

Supported commands:

```powershell
py scripts\run_onboarding_pool_rebuild.py --mock --all --strategy baseline_quota_fix
py scripts\run_onboarding_pool_rebuild.py --mock --all --strategy broad_top_seed
py scripts\run_onboarding_pool_rebuild.py --mock --all --strategy focused_first
py scripts\run_onboarding_pool_rebuild.py --mock --all --strategy hybrid_quality_focused
py scripts\run_onboarding_pool_rebuild.py --mock --all --strategy strict_underfill
py scripts\run_onboarding_pool_rebuild.py --mock --all --strategy-matrix
```

## Metrics Added

Each result now includes strategy, target, created, pool count, quota integrity, planned/actual media, planned/actual origin, source contributions, fallback counts, future rejected, quota mismatch rejected, duplicate rejected, top languages, warnings, and rejection counts.

## Output

- Mock JSON: `logs/reports/nightly_pool_experiment_mock_2026-07-08.json`
- Strategy JSON: `logs/reports/nightly_strategy_comparison_mock_2026-07-08.json`
- Strategy markdown: `docs/nightly/03_strategy_comparison_mock_2026-07-08.md`

## Notes

The default remains `broad_top_seed`, matching the current product behavior. Strategy selection is available for experiments and scripts.
