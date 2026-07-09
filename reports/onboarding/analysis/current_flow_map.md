# Current Onboarding Flow Map

Step: `001_baseline_current_flow_report`

## Runtime Path

1. `desktop/onboarding/wizard.py`
   - collects setup, country, media, release, and vibe answers;
   - builds an onboarding profile payload;
   - starts the worker/autofill flow;
   - renders plan, loading, and final summary pages.

2. `candidates/onboarding/autofill.py`
   - normalizes `OnboardingTasteProfile`;
   - converts country selection into country quotas;
   - builds country-first fetch buckets;
   - builds TMDb Discover requests;
   - filters future, wrong-country, excluded-home-country, duplicate, watched, hidden/rejected candidates;
   - writes incremental starter candidates to the pool;
   - records request audit entries.

3. `tests/test_onboarding_autofill.py`
   - verifies quota behavior;
   - verifies country-first Discover parameters;
   - verifies no `vote_count.gte` or `vote_average.gte` in initial Discover;
   - verifies genre OR default and AND explicit mode;
   - verifies onboarding wizard country chips and payload shape.

## Wizard Question Map

| Order | Key | Current choices |
| ---: | --- | --- |
| 0 | setup | language `ru/en`, UI scale `90/100/115/130` |
| 1 | `country_selection` | `US`, `RU`, `GB`, `KR`, `JP`; default `US` |
| 2 | `media_preference` | `movie`, `tv`, `both` |
| 3 | `release_preference` | `classic`, `new`, `mixed` |
| 4 | `vibe_preference` | `light`, `dark`, `mixed` |
| 5 | plan | quota summary |
| 6 | loading | progress and warnings |
| 7 | final | created count and open candidates action |

## Discover Request Map

| Area | Current behavior |
| --- | --- |
| Movie endpoint | `/discover/movie` |
| TV endpoint | `/discover/tv` |
| Country | `with_origin_country=<bucket.target_country>` |
| Sort | `popularity.desc` |
| Language | `ru-RU` for Russian UI, `en-US` otherwise |
| Adult content | `include_adult=false` |
| Vote filters | absent in initial Discover |
| Movie date fields | `primary_release_date.gte/lte` |
| TV date fields | `first_air_date.gte/lte` |
| Genre include | `|` OR by default, `,` AND when explicitly requested |
| TV genre exclude | `10766,10764,10767,10763,10762,99` |
| Default pages | `DEFAULT_DISCOVER_PAGES=3` |
| Max pages | `MAX_DISCOVER_PAGES=5` |

## Current Test Coverage Notes

- Country-first guardrails exist.
- Discover no-vote-filter guardrails exist.
- Wizard starts with the country question after setup.
- Multi-country chip behavior is covered.
- Include-genre OR default is covered.

## Deferred Work Queue

- Add `TastePreset` and profile mapping.
- Add `animation_mode` behavior.
- Add selective Details enrichment.
- Add overview localization fallback.
- Add Candidate Quality Gate v1.
- Add adaptive pagination.
- Add timeout/retry/outlier diagnostics.
- Add baseline comparison reports.

## TastePreset contract added

Step `002` adds a small serializable domain contract in
`candidates/onboarding/taste_presets.py`.

- `TastePreset` covers media type, animation mode, countries, symbolic genre
  groups, vibe, and release preference.
- `anime` can express `countries=["JP"]`, `animation_mode="animation_only"`,
  and `media_type="both"`.
- `k_drama` can express `countries=["KR"]`,
  `animation_mode="live_action_only"`, and `media_type="tv"`.
- `to_profile_kwargs()` bridges presets to the current `OnboardingTasteProfile`
  constructor without changing Discover behavior.
