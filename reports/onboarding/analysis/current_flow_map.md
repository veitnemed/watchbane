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

## Starter presets added

Step `003` expands the contract into the starter preset catalog and adds
`taste_preset_to_profile_payload()`.

| Preset | Countries | Animation mode | Media | Genre groups |
| --- | --- | --- | --- | --- |
| `hollywood_mainstream` | `US` | `any` | `both` | `action_adventure`, `comedy`, `drama` |
| `russian_mainstream` | `RU` | `any` | `both` | `drama`, `comedy`, `crime` |
| `anime` | `JP` | `animation_only` | `both` | `action_adventure`, `fantasy`, `drama`, `romance`, `comedy` |
| `k_drama` | `KR` | `live_action_only` | `tv` | `drama`, `romance`, `comedy`, `crime`, `thriller` |
| `turkish_dramas` | `TR` | `live_action_only` | `tv` | `drama`, `romance`, `family` |
| `british_european_detective` | `GB`, `FR`, `DE`, `IT`, `ES` | `live_action_only` | `tv` | `detective`, `crime`, `mystery`, `thriller` |
| `family_animation` | `US`, `JP`, `RU` | `animation_only` | `both` | `family`, `comedy`, `adventure`, `fantasy` |
| `dark_thriller_crime` | `US`, `GB`, `KR`, `JP`, `RU` | `any` | `both` | `crime`, `mystery`, `thriller`, `horror`, `drama` |
| `manual` | picker payload, capped at 5 | override or `any` | override or `both` | override |

## Animation mode behavior

Step `004` wires `animation_mode` into initial TMDb Discover params.

| Mode | Discover behavior |
| --- | --- |
| `animation_only` | forces `with_genres=16` without OR-merging other genres |
| `live_action_only` | adds TMDb Animation `16` to `without_genres` |
| `any` | leaves animation unconstrained unless already present in explicit genre filters |

Country-first `with_origin_country`, onboarding `sort_by=popularity.desc`, TV junk
genre excludes, and the no `vote_count.gte` / `vote_average.gte` initial
Discover guardrail remain unchanged.

## Vote confidence scoring formula

Step `006` adds a local scoring multiplier for TMDb rating confidence. This is
not a rejection filter and is not sent to Discover.

| Vote count | Confidence |
| ---: | ---: |
| `0` | `0.15` |
| `1-5` | `0.25` |
| `6-20` | `0.45` |
| `21-50` | `0.65` |
| `51-100` | `0.80` |
| `101-299` | `0.90` |
| `300+` | `1.00` |

Scoring debug now includes `rating_bonus_raw`, `vote_confidence`,
`rating_bonus_adjusted`, and `final_score`. The adjusted rating contribution is
`rating_bonus_raw * vote_confidence`, so a perfect score with one vote cannot
outrank a broadly supported strong rating solely through the rating value.

## Details enrichment behavior

Step `007` adds an optional selective Details enrichment stage after preliminary
Discover acceptance and before candidate records are saved.

Config defaults:

```text
details_enrichment:
  enabled: true
  default_limit_per_bucket: 50
  only_for_final_candidates: true
  fetch_external_ids: true
  fetch_tv_seasons_basic: false
  lazy_tv_details_on_card_open: true
```

Pipeline behavior:

1. Initial Discover remains country-first and uses no vote/rating hard filters.
2. Existing duplicate, watched, hidden/rejected, pool, and future checks happen
   before Details requests.
3. Preliminary accepted rows are scored locally.
4. The highest preliminary scores per country/media bucket are eligible for
   Details, capped by `default_limit_per_bucket`.
5. Details data can update overview, poster/backdrop, genres, countries,
   rating/vote/popularity fields, and external IDs.
6. Enriched rows are re-scored before final candidate records are saved.

Diagnostics:

- `AutofillResult.details_requests` records Details request attempts separately
  from Discover `api_requests`.
- Candidate records include `details_enriched` and `score_debug`.
