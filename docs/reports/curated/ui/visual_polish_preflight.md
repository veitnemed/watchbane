# Visual Polish Preflight

## Capture Context

- Platform plugin: `windows`.
- Font probe: 355 families, `Segoe UI` available, `Arial` available.
- Screenshots were generated under `screens/tmp_ui/onboarding/` and `screens/tmp_ui/candidates/`.
- PNGs listed below were visually opened and reviewed.

## Screens Captured

- `screens/tmp_ui/onboarding/preflight_tmdb_gate_scale100.png`
- `screens/tmp_ui/onboarding/preflight_welcome_scale100.png`
- `screens/tmp_ui/onboarding/preflight_taste_scale075.png`
- `screens/tmp_ui/onboarding/preflight_taste_scale100.png`
- `screens/tmp_ui/onboarding/preflight_taste_scale150.png`
- `screens/tmp_ui/onboarding/preflight_plan_scale100.png`
- `screens/tmp_ui/candidates/preflight_candidates_filters_scale075.png`
- `screens/tmp_ui/candidates/preflight_candidates_filters_scale100.png`
- `screens/tmp_ui/candidates/preflight_candidates_filters_scale150.png`
- `screens/tmp_ui/candidates/preflight_candidates_filters_replenish_scale100.png`
- `screens/tmp_ui/candidates/preflight_candidates_list_scale100.png`
- `screens/tmp_ui/candidates/preflight_settings_scale100.png`

## Structural Problems

1. API key / TMDb gate has clipping inside the central card. The status/input area and help text collide vertically, so the API onboarding step is not visually safe.
2. Candidates filters at 150% clips the Apply button text. This is a real scaling/layout failure in the top bar.
3. Candidates detail view at 1180px width clips the right-side score/stars and metadata values at the viewport edge. This suggests a detail-card width or horizontal scroll policy issue.
4. Preset selection at 150% avoids overlap, but only two cards fit and descriptions elide aggressively. It remains usable, but the scaling density is weak.

## Cosmetic Problems

- Preset cards look visually harsh: strong icon disks, colored left rules, bright selected border/check, and multiple competing glows.
- Welcome and plan onboarding steps have excessive empty space; content is pushed high/left while navigation sits far away at the bottom.
- Candidates filters are stable at 100%, but section cards feel heavy and the new replenish hint text is English inside a Russian UI.
- Primary buttons are much heavier than surrounding controls in onboarding, candidates filters, and settings.
- Settings is readable at 100%, but the large single section panel feels dense and vertically long.

## Recommended Fix Order

1. Fix API key / TMDb gate clipping first because it affects first-run completion.
2. Fix Candidates filters top-bar scaling at 150%, especially Apply button width/text.
3. Fix Candidates detail horizontal clipping or width policy.
4. Soften onboarding preset icons and card visuals.
5. Rebalance onboarding welcome/plan spacing and hierarchy.
6. Polish Candidates filters copy/localization and reduce visual heaviness.

## Likely Files Involved

- `desktop/startup/tmdb_gate.py`
- `desktop/theme/styles/startup.py`
- `desktop/onboarding/wizard.py`
- `desktop/candidates/filters_view.py`
- `desktop/candidates/filters_form.py`
- `desktop/candidates/list_view.py`
- `desktop/theme/styles/candidates_shell.py`
- `desktop/theme/shell_layout.py`
- `desktop/shared/detail/card_layout.py`
- `desktop/shared/detail/profiles.py`
- `desktop/theme/styles/detail_card.py`

## Notes

- No code or behavior was changed in this preflight step.
- Screenshots are temporary ignored artifacts and should not be committed.
