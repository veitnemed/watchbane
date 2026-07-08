# Onboarding UI Flow Update

## Changed Screens

- Added source selection before plan preview.
- Source selection now shows:
  - local quick starter as planned/disabled;
  - Live TMDb as the active available source;
  - Skip for now.
- Plan preview now shows source, strategy, target, media plan, origin plan for RU, search slices, and underfill behavior.
- Final result now shows planned/actual counts, source mode, strategy, source contributions, API requests, future rejected, and warnings.

## Copy Changes

RU copy was adjusted to avoid exposing raw strategy ids in plan/final screens. Some metric labels still use compact technical headings like `media` and `origin`, but bucket values are localized.

## Result Payload Usage

The UI consumes:

- `planned_counts`
- `actual_counts`
- `source_stats`
- `strategy`
- `api_requests`
- `rejected_future_count`
- `warning`

## Scale Risk

Screenshots at 75%, 100%, and 150% did not show overlap or clipped final-result text. The final screen still has a large empty area by design; it is preferable to crowding the card.

## Screenshots Planned

Completed under `screens/tmp_ui/onboarding/`.

## Tests

- `py -m pytest tests\test_onboarding_autofill.py -q`
- `py -m compileall candidates desktop scripts`

## Remaining UX Gaps

- Loading copy still mirrors low-level progress messages in some paths.
- Local starter catalog is not implemented; it is shown as planned, not available.
- Live RU domestic availability can underfill; final screen handles it honestly.
