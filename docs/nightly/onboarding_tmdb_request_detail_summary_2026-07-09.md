# Onboarding TMDb Request Detail Summary

Date: 2026-07-09  
Branch: `night-work`  
Strategy: `broad_top_seed`  
Mode: live TMDb, isolated SQLite runtime  
Token printed: no

## Artifacts

- Full markdown report: `docs/nightly/onboarding_tmdb_request_detail_2026-07-09.md`
- Full JSON report: `logs/reports/onboarding_tmdb_request_detail_2026-07-09.json`

The full report includes every captured TMDb discover request, sanitized params, top-20 response rows, title, country, year, genres, votes, average score, language, fit flags, and the final ranked pool.

## Scenario Summary

| Scenario | Created/Target | TMDb Requests | Source Mix | Warnings |
| --- | ---: | ---: | --- | --- |
| `en-tv-new-dark` | 120/120 | 37 | `quality_seed=39`, `focused=81` | none |
| `ru-balanced` | 91/120 | 180 | `origin_top_seed=12`, `quality_seed=20`, `focused=34`, `fallback=25` | 4 |
| `ru-domestic-movie-classic-light` | 88/120 | 180 | `origin_top_seed=22`, `quality_seed=14`, `focused=15`, `fallback=37` | 4 |

## Top-20 Request Fit

Fit is calculated per top-20 TMDb row against the request params:

- hard fit: poster, requested language if present, requested RU origin country if TMDb result exposes it;
- soft fit: requested year, requested genres, vote threshold.

| Scenario | Top-20 Rows Reviewed | Hard Fit | Soft Fit | Full Fit |
| --- | ---: | ---: | ---: | ---: |
| `en-tv-new-dark` | 740 | 100.0% | 100.0% | 100.0% |
| `ru-balanced` | 2269 | 60.1% | 100.0% | 60.1% |
| `ru-domestic-movie-classic-light` | 2685 | 51.1% | 100.0% | 51.1% |

Important: TMDb `discover/movie` often does not return `origin_country` in result rows. For RU domestic movie queries, the request itself contains `with_origin_country=RU`, but per-title country evidence may be absent in the response. The detailed report keeps that visible instead of inventing country values.

## Final Ranking Notes

Final pool ranking is sorted by `candidate_score`, which combines bucket priority, TMDb quality signals, freshness where applicable, and request/page order penalty.

Top 10 final ranked titles:

- `en-tv-new-dark`: FROM; Dutton Ranch; Teach You a Lesson; Breaking Bad; Off Campus; Silo; The Polygamist; Avatar: The Last Airbender; X-Men '97; Regular Show: The Lost Tapes.
- `ru-balanced`: Обсессия; История игрушек 5; Во все тяжкие; Побег из Шоушенка; Проект «Конец света»; Майкл; Ранчо Даттонов; Сверхъестественное; Анатомия страсти; Твоё сердце будет разбито.
- `ru-domestic-movie-classic-light`: Твоё сердце будет разбито; Дурак; Левиафан; Мира; Балканский рубеж; Уроки фарси; Брат; Нелюбовь; Возвращение; Серебряные коньки.

## Findings

- EN TV New Dark is strong: top-20 rows match request constraints cleanly and the final pool reaches 120.
- RU scenarios still hit the request cap and underfill honestly; no silent media/origin cross-fill is used.
- RU domestic movie diagnostics are limited by TMDb result fields: query params verify domestic intent, but many individual movie rows do not expose country in discover response.
- Soft parameters are generally satisfied in top-20 rows; the main availability problem is hard RU origin evidence and candidate acceptance volume.
