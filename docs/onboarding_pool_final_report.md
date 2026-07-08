# Onboarding Pool Final Report

Date: 2026-07-08

## Startup Scenarios

- Normal startup: no dev flag, existing completed onboarding profile means the starter window is not shown.
- First startup with empty candidate pool: onboarding opens, collects language/scale/taste, builds the pool, then focuses Candidates.
- Console dev startup: `py start_console.py`, option `7 >> Dev GUI: empty candidate pool on startup`; backs up active data root, clears candidate/onboarding tables only, keeps watched records, then starts GUI from zero candidate pool.
- Full empty-profile dev startup: `WATCHBANE_DEV_EMPTY_PROFILE=1` backs up and removes active runtime DB/legacy files; use only when watched records can be reset.
- Isolated scenario rebuild: `py scripts\run_onboarding_pool_rebuild.py --mock|--live --all`; writes temporary SQLite databases and never clears the active profile.

## Pool Build Results

Mock scenarios all reached exact planned quotas:

- EN TV New Dark: 120/120, media 84 TV / 36 movie, no warnings.
- RU Balanced: 120/120, media 60/60, origin 60 domestic / 60 foreign, no warnings.
- RU Domestic Movie Classic Light: 120/120, media 84 movie / 36 TV, origin 84 domestic / 36 foreign, no warnings.

Live scenarios on TMDb:

- EN TV New Dark: 120/120, media 84 TV / 36 movie, no warnings, 33 requests, about 32.2s.
- RU Balanced: 99/120, media 50 TV / 49 movie, origin 39 domestic / 60 foreign, explicit underfill warnings, 180 requests, about 126.0s.
- RU Domestic Movie Classic Light: 90/120, media 62 movie / 28 TV, origin 54 domestic / 36 foreign, explicit underfill warnings, 180 requests, about 83.7s.

Both RU live scenarios are above the minimum acceptable 80 and keep hard media/origin caps instead of silently substituting foreign/movie candidates.

## UI Verification

Native Windows screenshots were generated and visually inspected:

- `screens/tmp_ui/onboarding/pool_rebuild_plan_scale100.png`
- `screens/tmp_ui/onboarding/pool_rebuild_loading_scale100.png`
- `screens/tmp_ui/onboarding/pool_rebuild_final_scale100_localized.png`
- `screens/tmp_ui/onboarding/pool_rebuild_final_scale075.png`
- `screens/tmp_ui/onboarding/pool_rebuild_final_scale15.png`

Platform plugin: `windows`.

Font probe: `family_count=355`, `Segoe UI=True`, `Arial=True`.

No overlap or clipped final-result text was visible at 75%, 100%, or 150%. The final screen now shows actual/planned media and origin counts, API request count, future-title rejection count, and localized underfill warnings.

## Verification

- `py -m pytest tests\test_onboarding_autofill.py -q`
- `py scripts\run_onboarding_pool_rebuild.py --mock --all --output docs\onboarding_pool_mock_report.md --json-output logs\reports\onboarding_pool_mock_report.json`
- `py scripts\run_onboarding_pool_rebuild.py --live --all --require-live --output docs\onboarding_pool_live_report_after_quota_fixes.md --json-output logs\reports\onboarding_pool_live_report_after_quota_fixes.json`
