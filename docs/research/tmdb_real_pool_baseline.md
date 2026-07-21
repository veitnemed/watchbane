# TMDb real candidate pool baseline — TMDB-1.3a

**Analysis date:** 2026-07-21
**Commit:** `3ed285f`
**App version:** `0.1.1-alpha.1`
**Source:** `%LOCALAPPDATA%/Watchbane/data/watchbane.sqlite3` (redacted)

## Safety of the run

The Watchbane process check passed. A timestamped SQLite Online Backup snapshot
was created outside the production runtime and the exporter read only that copy.
The production file SHA-256, size, mtime, `user_version`, `page_count`,
`data_version`, and WAL/SHM metadata were identical before and after. No WAL or
SHM sidecar was present. No network, migrations, refresh, replenish, or deck
rebuild was run.

## Real pool result

| Metric | Real pool |
| --- | ---: |
| Candidate records / unique identities | 101 / 101 |
| Movie / TV | 101 / 0 |
| Legacy, duplicates, invalid JSON | 0 / 0 / 0 |
| SQL/payload conflicts | 0 |
| Missing title / overview / country codes | 0 / 0 / 0 |
| Poster metadata missing | 0 (0%) |
| Movie runtime missing | 71 (70.3%) |
| TV runtime | not applicable: no TV records |
| Providers missing | 89 (88.1%) |
| Keywords missing | 71 (70.3%) |
| Adult missing | 101 (100%) |
| Content rating missing | 71 (70.3%) |
| EN fallback | 0 |
| Saved active/reserve safety anomalies | 1 |

All records have poster metadata (`poster_path` or `poster_url`) and the
production readonly presenter marks a poster as available. The SQLite
`poster_cache_entries` table contains zero rows, therefore the observed poster
availability comes from candidate metadata and presenter hints, not from a
locally stored poster-cache entry.

Provider region and checked timestamp are unavailable for all records because
the current candidate payload stores only provider names. Raw TMDb responses
are not retained, so endpoint-, language-, region-, and append-level provenance
is **inconclusive without raw API**.

## Comparison with C3-12 synthetic seeds

| Metric | Synthetic P1 | Synthetic P2 | Synthetic P3 | Real pool |
| --- | ---: | ---: | ---: | ---: |
| Records | 43 | 43 | 43 | 101 |
| Poster missing | 100% | 100% | 100% | 0% |
| Movie runtime missing | 100% | 100% | 100% | 70.3% |
| TV runtime missing | 100% | 100% | 100% | N/A |
| Providers missing | 100% | 100% | 100% | 88.1% |
| Keywords missing | 62.8% | 62.8% | 62.8% | 70.3% |
| Adult missing | 0% | 0% | 0% | 100% |
| Content rating missing | 0% | 0% | 0% | 70.3% |
| EN fallback | 0% | 0% | 0% | 0% |
| Invalid payload | 0% | 0% | 0% | 0% |

## Finding classes

- **Synthetic-only limitation:** C3-12 lacks poster metadata completely, while
  the real pool preserves it and UI projection can use it.
- **Real-pool data gaps:** movie runtime, providers, keywords, and content
  rating are incomplete in the real pool. The synthetic 100% missing result
  exaggerates their production prevalence.
- **Confirmed production defect candidate:** `adult` is absent in every real
  candidate payload, despite TMDB-1.1a preserving it in the current TMDb
  normalizer. A separate provenance investigation is required.
- **Not applicable:** TV episode runtime cannot be evaluated because the real
  pool has no TV records.
- **Inconclusive without raw API:** source TMDb request, provider region/time,
  country origin versus production provenance, and losses before stored payload.

The saved-deck safety anomaly is a defect candidate, not proof that a title is
unsafe: it requires a separate privacy-safe inspection of stored safety signals.

## Representative tracing

Ignored evidence contains anonymised traces for one poster-bearing record and
one movie-runtime record. Both demonstrate `stored payload → readonly presenter
UI projection`; the TV trace is marked not applicable because no TV record is
present. No title, TMDb ID, user action, cache path, or full production path is
included here.

## Limits and next investigations

This baseline measures stored local data, not recommendation quality or the
current TMDb API. Follow-up defect tasks should separately trace historical
ingestion paths that omit adult, detail-field persistence for
runtime/providers/keywords, and the single saved-deck safety anomaly. A
controlled live TMDb snapshot is required for raw-request provenance.
