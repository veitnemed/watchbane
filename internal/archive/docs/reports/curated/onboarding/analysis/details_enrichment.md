# Details Enrichment Pipeline

## Tested order

Step `102` hardens the selective Details stage with mocked regression tests.

The onboarding starter sweep must keep this order:

1. Discover pages are fetched with country-first params.
2. Raw TMDb ids are deduped before Details.
3. Normalized title/year duplicate-like rows are deduped before Details.
4. Existing pool records are removed before Details.
5. Already watched or dataset-overlap rows are removed before Details.
6. Preliminary accepted rows are scored.
7. Details requests are capped per bucket.
8. Localization fallback requests share the same Details cap.
9. Enriched candidates are re-scored and quality-gated before pool insertion.

Guardrails:

- Duplicate rows across pages/templates must not trigger repeated Details calls.
- Different TMDb ids with the same normalized title/year must not trigger
  repeated Details calls.
- Watched and existing-pool candidates must not trigger Details calls.
- Disabled Details enrichment must produce zero Details requests.
- The configured Details limit includes localization fallback requests.
