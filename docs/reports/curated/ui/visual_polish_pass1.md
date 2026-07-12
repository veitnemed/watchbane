# Visual Polish Pass 1

## Capture Context

- Platform plugin: `windows`.
- Font probe: 355 families, `Segoe UI` available, `Arial` available.
- Screenshot directory: `screens/tmp_ui/pass1_sweep/`.
- PNGs below were generated and visually opened/reviewed.

## Screens Reviewed

- `screens/tmp_ui/pass1_sweep/start_tmdb_gate_scale100.png`
- `screens/tmp_ui/pass1_sweep/onboarding_welcome_scale100.png`
- `screens/tmp_ui/pass1_sweep/onboarding_taste_scale100.png`
- `screens/tmp_ui/pass1_sweep/onboarding_plan_scale100.png`
- `screens/tmp_ui/pass1_sweep/candidates_filters_scale100.png`
- `screens/tmp_ui/pass1_sweep/candidates_list_scale075.png`
- `screens/tmp_ui/pass1_sweep/candidates_list_scale100.png`
- `screens/tmp_ui/pass1_sweep/candidates_list_scale150.png`
- `screens/tmp_ui/pass1_sweep/settings_scale100.png`

## Fixed In This Pass

- Candidate detail card no longer uses the full watched-detail geometry inside the Candidates split pane. At 100% and 1180x760, score/stars and main-info values are fully visible instead of clipping at the right edge.
- Candidate Filters static replenish/country copy now uses localized `tr(...)` strings. The visible RU UI no longer shows the hardcoded English `Countries are...` hint or `Taste / Replenish` section title.

## Remaining Risk

- Candidates split-pane at 150% still clips horizontally at 1180x760. This is now a broader responsive policy issue: the scaled list panel and scaled detail panel do not both fit side-by-side. It should be handled as a focused 150% candidates layout task rather than hidden by enabling horizontal scroll.

## Checks

- `py -m compileall desktop candidates tests`
- `py -m pytest tests/desktop -q --basetemp .pytest-tmp-step022`
- `py -m pytest tests/test_desktop.py::test_candidate_list_view_uses_readonly_detail_builder tests/test_ui_scale_settings.py::test_candidate_detail_card_profile_scales_with_ui_scale tests/test_ui_scale_settings.py::test_scale_anchor_layout_constants_use_scaled_tokens -q --basetemp .pytest-tmp-step022-contracts`
