# Onboarding Guardrails

## Initial Discover vote filters

Initial onboarding Discover requests must not include `vote_count.gte` or
`vote_average.gte`.

Vote count and rating are allowed only after Discover as scoring, confidence,
quality-gate, and ranking signals. This keeps the country-first starter sweep
from dropping low-vote regional titles before Details enrichment, localization
fallback, and quality classification can run.

The hardening matrix covers movie, TV, mixed media, selected countries,
new/mixed/classic release ranges, light/dark/mixed vibes, animation modes,
starter presets, and manual mode.
