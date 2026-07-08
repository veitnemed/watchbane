# Watchbane UI Scaling

Watchbane has its own application-level UI scale. It is separate from Windows display scaling and Qt device pixel ratio handling.

Do not use `QT_SCALE_FACTOR` for normal Watchbane UI scaling. Qt already handles OS DPI. `QT_SCALE_FACTOR` is a Qt high-DPI testing/debug override and is multiplied with the native DPR.

## User Scale

The persisted user setting is:

- `ui_scale`
- stored in the SQLite app settings table
- default `1.0`
- clamped to `0.50..2.00`

`WATCHBANE_UI_SCALE` can override it for the current process only.

## Local Theme Tuning

Manual component tuning lives in `desktop/theme/ui_tuning.py`.

For local experiments, copy:

```text
desktop/theme/local_ui_tuning.py.example
```

to:

```text
desktop/theme/local_ui_tuning.py
```

`local_ui_tuning.py` is ignored by git.

Available tuning keys:

- `ui`
- `font`
- `layout`
- `control`
- `list`
- `detail`
- `poster`

Every tuning value defaults to `1.0` and is clamped to `0.50..2.00`.

Effective channel scale:

```text
effective_scale = ui_scale * tuning["ui"] * tuning[channel]
```

## Architecture

- `desktop/settings/app_settings.py` owns persisted `ui_scale`.
- `desktop/theme/ui_tuning.py` owns local channel constants.
- `desktop/theme/scaling.py` owns runtime scale helpers.
- `desktop/theme/tokens.py` exposes semantic wrappers like `control_px`, `list_px`, `detail_px`, `poster_px` and `font_px`.
- `desktop/shared/detail/profiles.py` turns base detail-card tokens into scaled layout profiles.
- Runtime widgets should consume tokens/profiles, not apply local scale multipliers.
