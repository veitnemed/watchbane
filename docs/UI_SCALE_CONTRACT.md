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
- Visual constants stay in `desktop/theme/tokens.py` and layout profiles.
- Runtime widgets must not apply their own random multipliers.
- The persisted setting is stored as Watchbane application state, not as a Qt global DPR override.
- `QT_SCALE_FACTOR` must not be written, read as the app setting, or recommended for normal use.

## First Implementation

- Scale changes may require app restart.
- Live apply is not required.
- Bootstrap loads the setting once and calls `desktop.theme.scaling.set_ui_scale(...)`.

## Manual Smoke Checklist

- Windows scale 100%, `ui_scale` 1.0.
- Windows scale 100%, `ui_scale` 1.25.
- Windows scale 150%, `ui_scale` 1.0.
- Windows scale 150%, `ui_scale` 1.15 or 1.25.
- `ui_scale` 0.50 remains usable enough for emergency compact mode.
- `ui_scale` 2.00 keeps dialogs and detail card reachable on a large screen.
- Detail card opens without clipping.
- Candidate pool list remains usable.
- Watched list remains usable.
- Dialogs fit on screen.
- Posters, rating rings and chips scale proportionally.
- Main window does not become unusable.
