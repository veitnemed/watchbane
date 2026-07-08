# Verification

## Commands Run

```powershell
py -m pytest tests\test_onboarding_autofill.py -q
py scripts\run_onboarding_pool_rebuild.py --mock --all --strategy-matrix --output docs\nightly\03_strategy_comparison_mock_2026-07-08.md --json-output logs\reports\nightly_strategy_comparison_mock_2026-07-08.json
py scripts\run_onboarding_pool_rebuild.py --live --all --require-live --strategy broad_top_seed --output docs\nightly\03_strategy_comparison_live_2026-07-08.md --json-output logs\reports\nightly_strategy_comparison_live_2026-07-08.json
py -m compileall candidates desktop scripts
py -m pytest tests\test_desktop.py::test_onboarding_finish_invalidates_candidate_cache_before_focus -q --basetemp .pytest-tmp-desktop
py scripts\capture_onboarding.py --step source --scale 1.0 --language ru --output screens\tmp_ui\onboarding\source_selection_scale100.png
py scripts\capture_onboarding.py --step plan --scale 1.0 --language ru --output screens\tmp_ui\onboarding\plan_preview_scale100.png
py scripts\capture_onboarding.py --step loading --scale 1.0 --language ru --output screens\tmp_ui\onboarding\loading_scale100.png
py scripts\capture_onboarding.py --step final --scale 0.75 --language ru --output screens\tmp_ui\onboarding\final_scale075.png
py scripts\capture_onboarding.py --step final --scale 1.0 --language ru --output screens\tmp_ui\onboarding\final_scale100.png
py scripts\capture_onboarding.py --step final --scale 1.5 --language ru --output screens\tmp_ui\onboarding\final_scale15.png
```

## Passing

- Onboarding autofill tests: `25 passed`.
- Targeted desktop onboarding finish test: `1 passed` on separate rerun.
- Compileall: passed for `candidates desktop scripts`.
- Mock strategy matrix completed.
- Limited live smoke completed.
- Native screenshots saved and visually inspected.

## Failing

- First live smoke showed seed-stage request starvation on RU-heavy scenarios. This was fixed by capping seed stages to one page per bucket/stage and rerunning tests/live smoke.
- One targeted desktop pytest run failed when launched in parallel with the onboarding suite because Windows locked a sqlite file under shared `.pytest-tmp`. The same test passed when rerun separately with `--basetemp .pytest-tmp-desktop`.

## Not Run and Why

- Full `py -m pytest` was not run. Changes are scoped to onboarding/autofill/scripts, and targeted tests plus compileall passed.
- Full live strategy matrix was not run to avoid excessive TMDb API usage.

## Diff Stat

Main changed areas:

- `candidates/onboarding/autofill.py`
- `candidates/service.py`
- `desktop/onboarding/wizard.py`
- `desktop/onboarding/worker.py`
- `scripts/run_onboarding_pool_rebuild.py`
- `scripts/capture_onboarding.py`
- `tests/test_onboarding_autofill.py`
- `docs/nightly/*`
- `logs/reports/*`

## Risk Assessment

Medium. Strategy hooks are new, but default behavior remains `broad_top_seed` and is covered by mocked regressions. Live RU scenarios still underfill, but warnings and planned/actual counts are explicit.

## Release Readiness Impact

This is suitable for a feature branch. Merge should require review of live RU underfill expectations and the generated reports.
