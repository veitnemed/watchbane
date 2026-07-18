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

## quality_gate_edge_cases

Step `107` hardens Candidate Quality Gate v1 edge cases.

Garbage by default:

- wrong selected country;
- wrong media type;
- TV junk genres in starter onboarding;
- missing poster plus missing overview;
- missing overview after fallback with very low vote confidence;
- suspicious adult/erotic title when TMDb does not mark the row as adult;
- duplicate-like candidates.

Weak, not garbage:

- missing localized overview when fallback overview exists;
- low votes alone;
- rating `0` when other metadata is useful.

Default onboarding still blocks `garbage` candidates from normal pool insertion.

## country_first_regressions

Step `108` hardens country-first starter sweep behavior.

Regression guarantees:

- every selected country bucket uses `with_origin_country`;
- 1–5 selected-country plans still sum to the starter target of `120`;
- mocked normal country-first scenarios keep country hit rate at `1.0`;
- default onboarding does not use broad-origin requests;
- default onboarding keeps fallback as `base`;
- high-yield selected-country underfill continues selected-country pages instead
  of falling outside selected countries;
- report metrics count country leakage and wrong-country candidates when an
  off-country row reaches diagnostics.

## report_workspace_hygiene

Step `110` keeps generated onboarding artifacts out of active documentation.

Output contract:

- raw generated payloads and logs live under `reports/onboarding/raw/`;
- generated analytical markdown lives under `reports/onboarding/analysis/`;
- before/after snapshots live under `reports/onboarding/baselines/`;
- UI smoke screenshots live under `screens/tmp_ui/` or
  `screens/tmp_ui/onboarding/`;
- `docs/` is reserved for curated documentation, not raw generated reports.
