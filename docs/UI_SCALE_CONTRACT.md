# UI Scale Contract

## Purpose

Watchbane supports user-controlled application UI scale.

This scale is separate from Windows/OS DPI scale. Qt high-DPI behavior remains normal/default and continues to use the native device pixel ratio provided by the operating system.

`QT_SCALE_FACTOR` is not the persisted user setting for Watchbane. It is a Qt high-DPI testing/debugging override and must not be used as the implementation mechanism for application UI scale.

## Setting

- Name: `ui_scale`
- Type: `float`
- Default: `1.0`
- Minimum: `0.50`
- Maximum: `2.00`

Presets:

- `0.50`
- `0.75`
- `0.85`
- `1.0`
- `1.10`
- `1.25`
- `1.35`
- `1.50`
- `1.75`
- `2.00`

## Scope

`ui_scale` should affect:

- app font;
- QSS font sizes;
- margins;
- paddings;
- spacing;
- border radii;
- fixed widget sizes;
- main window default size;
- detail card poster size;
- rating rings;
- chips;
- buttons;
- dialogs.

## Scale Anchor Contract

Three `ui_scale` values are mandatory control modes before the desktop architecture refactor:

- `1.0` is the baseline reference for design proportions and default sizing.
- `0.75` is the compact working mode.
- `1.50` is a stress-check for readability, text clipping and overflow.

Scale anchors are not three separate desktop UIs. They are checkpoints for one UI system.

Rules:

- Do not add separate QSS branches for `0.75`, `1.0` or `1.50`.
- Do not make scale-specific widget implementations.
- One system of design tokens, layout constants and scaling helpers must work across all three anchors.
- Anchor checks should validate usability properties, not pixel-perfect geometry.

Hard contract:

- minimum sizes for list rows, buttons, cards and inputs;
- min/max width and height where they affect usability;
- `wordWrap` for long descriptive text;
- no clipping of key labels and actions;
- no widget overlap;
- visibility and collapse/expanded state;
- stable layout without abrupt jumps when switching tabs or expanding controls;
- new dimensions go through scaling helpers or scaled token constants.

Not a hard contract:

- absolute coordinates of every widget;
- exact pixels for every margin and padding at every scale;
- per-scale QSS;
- visual identity across all three scales.

## Non-goals

- Do not scale data values.
- Do not scale TMDb scores.
- Do not scale JSON records.
- Do not scale poster cache files.
- Do not change API behavior.
- Do not use absolute positioning to compensate for scale.
- Do not change OS DPI awareness.

## Architecture

- All scaling goes through `desktop/theme/scaling.py`.
- Local channel tuning lives in `desktop/theme/ui_tuning.py`; see [ui-scaling.md](ui-scaling.md).
- Layout sizes, margins, spacing, fixed/min/max dimensions and scaled layout constants live in `desktop/theme/layout.py`.
- `desktop/theme/shell_layout.py` is a compatibility facade for shell-sized constants; do not add new sizes there.
- `desktop/theme/tokens.py` is for colors, fonts, radii and semantic visual names. Existing layout aliases may remain only for compatibility.
- Detail-card profile composition lives in `desktop/shared/detail/profiles.py` and must use `desktop/theme/layout.py` geometry plus scaling helpers.
- New tabs must take margins, spacing and fixed/min/max dimensions from `layout.py` helpers/constants, not hardcoded px.
- Runtime widgets must not apply their own random multipliers.
- Hardcoded fixed pixel sizes are prohibited unless there is a documented usability reason and a test/whitelist entry.
- The persisted setting is stored as Watchbane application state, not as a Qt global DPR override.
- `QT_SCALE_FACTOR` must not be written, read as the app setting, or recommended for normal use.

## Removed Information Tab

- The `Информация` / `Information` tab is not part of the active desktop shell.
- Scale anchor checks must not include a separate Information tab.
- Requests that mention `Информация`, `Information`, `Analytics tab` or an analytics main-window tab are ambiguous and must be clarified before implementation.
- Do not re-add this tab, its shell registration or watched-entry cross-tab wiring without an explicit clarified requirement.

## First Implementation

- Scale changes may require app restart.
- Live apply is not required.
- Bootstrap loads the setting once and calls `desktop.theme.scaling.set_ui_scale(...)`.

## Interface Language

- `interface_language` is an application setting for UI labels, buttons, messages, placeholders and tooltips.
- Interface translation applies after app restart; no scale anchor requires dynamic full-window retranslate.
- `data_language` is independent and must not be used by UI scale/layout checks.
- Scale anchors must validate translated UI text for wrapping/visibility, not pixel-perfect coordinates.

## Manual Smoke Checklist

Run this checklist at each anchor: `ui_scale=0.75`, `ui_scale=1.0`, `ui_scale=1.50`.

- Моё / Watched: sidebar remains usable, watched list rows are readable, detail card does not clip key title/rating/action text.
- Моё / Watched: expanded filters show score/year/genre controls, reset action is visible, collapse/expand state is stable.
- Фильтры: intro copy wraps, Apply/Reset actions are visible, sliders and chip selectors keep usable height.
- Кандидаты: list panel keeps usable min/max width, rows are readable, detail placeholder/card wraps long text and does not overlap the list.
- Настройки: UI scale slider, value label, language controls, reset/save buttons and restart message remain visible and readable.
- Add-title search dialog: title input, country combo, search action, progress/status text fit in inactive and active states.
- Add-title preview dialog: preview card, warning text, score input and confirm/back actions remain visible without overlap.
- Window/tab switching does not produce abrupt layout jumps or zero-sized panels.
- Posters, rating rings and chips scale through the shared tokens/helpers.

## Automated Guardrails

- `tests/test_ui_scale_settings.py` parametrizes anchor checks for `0.75`, `1.0` and `1.50`.
- Anchor tests validate layout properties: minimum/maximum sizes, non-zero dimensions, `wordWrap`, visibility and collapse/expanded state.
- Anchor tests must not assert absolute coordinates for every widget or pixel-perfect margins/padding.
- `test_hardcoded_px_guard_for_direct_sizing_calls` blocks new direct `setFixedWidth/Height` and `setMinimumWidth/Height` numeric calls unless added to the legacy TODO whitelist.
- New dimensions must use `desktop/theme/layout.py` constants and scaling helpers.
