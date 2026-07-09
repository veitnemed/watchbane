# Preset UI Flow

Step `005` adds a starter preset page after the language/scale setup page.

Flow:

1. Setup page keeps language and UI scale controls unchanged.
2. Preset page shows the domain starter presets as localized RU/EN cards.
3. Choosing a preset fills country selection, media type, animation mode,
   release preference, and vibe.
4. Editable pages still follow the country-first shape: countries, media type,
   animation mode, release preference, and vibe.
5. Plan summary shows preset key/name, selected countries, media, animation
   mode, release/vibe, target, and quotas before any TMDb requests.

Notes:

- Manual keeps the old 5-country picker limit.
- Preset-specific country sets such as `TR` or `GB/FR/DE/IT/ES` are displayed
  inside the same 5-country picker cap after the preset is selected.
- Genre editing is intentionally not added here: the current reusable chip
  selector works with display labels, while starter presets keep symbolic genre
  groups that are not yet mapped to safe UI-editable TMDb genre IDs.

Screenshot smoke:

- Command family: `py scripts/screenshots/capture_onboarding.py --step taste`
- Platform plugin: `windows`
- Font probe: `family_count=355`, `Segoe UI=True`, `Arial=True`
- Scales captured under `screens/tmp_ui/onboarding/`: `0.75`, `1.0`, `1.5`
- PNGs were opened for visual inspection; preset card text fits at all three
  checked scales, with vertical scrolling used for the longer preset list.
