# Onboarding Discover Quality Report

- Дата: 2026-07-09
- Режим: live TMDb
- TMDb credentials present: True
- Проходов: 1
- Цель на проход: 120 кандидатов
- Временные SQLite базы: `C:\Users\super\AppData\Local\Temp\watchbane-discover-quality-akts2p2k`

## Короткий вывод

- Полный пул 120/120 собран в 0 из 1 проходов.
- Всего создано кандидатов: 82.
- Всего выполнено discover-запросов: 5.
- Discover templates: 1.
- Среднее время discover-запроса: 349.6 ms.
- P95 discover-запроса: 386.1 ms.
- Минимальный country hit rate: 1.0.
- TV candidates with seasons initially: 0/82.

Примечание по сериалам: TMDb `/discover/tv` не отдаёт `number_of_seasons` и `number_of_episodes`. Поэтому в стартовом пуле эти поля ожидаемо пустые до ленивого `/tv/{id}` details enrichment при открытии карточки.

## Before / After

| Flow | Discover templates | Discover HTTP | Raw discover | Final/accepted | Details | Broad origin | Vote/rating Discover filters |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Old onboarding RU-only from `docs/onboarding_discover_quality_report.md` | many bucket templates | 180 | n/a | 19 | 0 | 0 | yes: `vote_count.gte` |
| Manual `candidate_pool v2` reference from user log | 12 templates | 60 | 1200 | 50 | 50 | 0 | no |
| New onboarding `ru-tv-manual-serious-2010` | 1 | 5 | 100 | 82 | 0 | 0 | no |

Notes:

- New onboarding now matches the important Discover contract from the manual run: country-first, `with_origin_country=RU`, genre OR, TV junk excludes, no `vote_count.gte`, no `vote_average.gte`.
- The new onboarding run accepts low-vote titles into the candidate pool. Examples from the live sample include `Плакса` with 1 vote, `Горячая точка` with 2 votes, and `Пять минут тишины` with 5 votes.
- Synchronous Details fan-out is still not moved into onboarding in this iteration. Series details are still loaded by the existing lazy details enrichment when a candidate card is opened.

## Сводная таблица

| Scenario | Created | API req | Time | Avg req | Country plan | Country actual | Media actual | Hit | Warnings |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | --- |
| `ru-tv-manual-serious-2010` | 82 | 5 | 2.43s | 349.6ms | RU: 120 | RU: 82 | tv: 82 | 1.0 | Starter pool underfilled: created 82 of 120.; Media quota underfilled: tv planned 120, actual 82.; Country quota underfilled: RU planned 120, actual 82.; Origin quota underfilled: domestic planned 120, actual 82. |

## ru-tv-manual-serious-2010

- Profile: `{"country_selection": {"country_weights": {"RU": 1.0}, "exclude_home_country": false, "home_country": "RU", "max_countries": 1, "mode": "single_country", "primary_country": "RU", "secondary_country": null, "selected_countries": ["RU"]}, "details_limit": 50, "discover_pages": 5, "exclude_genres": [10766, 10764, 10767, 10763, 10762, 99], "include_genre_mode": "or", "include_genres": [18, 9648, 80], "max_year": null, "media_preference": "tv", "min_year": 2010, "origin_preference": "domestic", "release_preference": "mixed", "ui_language": "ru", "vibe_preference": "dark"}`
- Created/pool: 82 / 82
- API requests: 5; unique/total: 5 / 5
- API budget: templates 1; discover HTTP 5; details 0; broad origin 0; fallback used False
- Yield: raw discover 100; duplicates removed 18; accepted/template 82.0; accepted/discover request 16.4
- Duplicate skipped: 0
- Speed: total 2.43s; discover avg 349.6ms; p50 346.9ms; p95 386.1ms; max 386.1ms
- Planned media: `{"tv": 120}`
- Actual media: `{"tv": 82}`
- Planned country: `{"RU": 120}`
- Actual country: `{"RU": 82}`
- Country hit/leak/wrong: 1.0 / 0.0 / 0
- Fallbacks: `{"base": 82}`; fallback share 0.0
- Avg TMDb score/votes/popularity: 6.1655 / 17.061 / 6.885
- Vibe hit light/dark: 0.2439 / 1.0
- Junk/garbage: 0 (0.0) / 0 (0.0)
- Missing poster/overview: 0 / 0
- TV seasons/episodes present initially: 0/82 and 0/82
- Warnings: `["Starter pool underfilled: created 82 of 120.", "Media quota underfilled: tv planned 120, actual 82.", "Country quota underfilled: RU planned 120, actual 82.", "Origin quota underfilled: domestic planned 120, actual 82."]`

### Top output sample

| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 19 | Невский | 2016 | tv | RU | ru | 9.1 | 14 | 8.8965 | 11.0989 | base |
| 21 | Трудные подростки | 2019 | tv | RU | ru | 8.5 | 53 | 8.0061 | 11.0983 | base |
| 25 | Вампиры средней полосы | 2021 | tv | RU | ru | 8.262 | 84 | 6.076 | 11.0972 | base |
| 26 | Шеф | 2012 | tv | RU | ru | 9.0 | 14 | 8.3705 | 11.0968 | base |
| 45 | Мир! Дружба! Жвачка! | 2020 | tv | RU | ru | 8.6 | 58 | 5.1841 | 11.0966 | base |
| 18 | Лучше, чем люди | 2018 | tv | RU | ru | 7.377 | 455 | 6.6851 | 11.0966 | base |
| 71 | Волшебный участок | 2023 | tv | RU | ru | 9.0 | 42 | 3.8671 | 11.0959 | base |
| 63 | Горячая точка | 2020 | tv | RU | ru | 10.0 | 2 | 4.3085 | 11.0936 | base |
| 49 | Плакса | 2023 | tv | RU | ru | 10.0 | 1 | 3.9773 | 11.0924 | base |
| 2 | И снова здравствуйте! | 2022 | tv | RU | ru | 7.7 | 22 | 26.259 | 11.091 | base |
| 77 | Первый отдел | 2020 | tv | RU | ru | 8.778 | 18 | 4.767 | 11.0894 | base |
| 15 | Екатерина | 2014 | tv | RU | ru | 7.7 | 36 | 7.2361 | 11.0892 | base |
| 24 | Условный мент | 2019 | tv | RU | ru | 8.1 | 9 | 9.5618 | 11.0863 | base |
| 13 | Чистые | 2024 | tv | RU | ru | 8.3 | 3 | 8.0675 | 11.0849 | base |
| 5 | Молодёжка | 2013 | tv | RU | ru | 7.185 | 27 | 14.0725 | 11.0849 | base |
| 22 | Балабол | 2014 | tv | RU | ru | 7.8 | 12 | 8.162 | 11.0848 | base |
| 27 | Склифосовский | 2012 | tv | RU | ru | 7.7 | 18 | 7.5556 | 11.0847 | base |
| 32 | Пять минут тишины | 2017 | tv | RU | ru | 8.2 | 5 | 6.3757 | 11.0834 | base |
| 23 | Метод | 2015 | tv | RU | ru | 6.814 | 78 | 6.795 | 11.0827 | base |
| 74 | Молодёжка. Новая смена | 2024 | tv | RU | ru | 9.0 | 2 | 3.9755 | 11.0823 | base |

### Detailed Discover Requests

1. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&first_air_date.gte=2010-01-01&with_origin_country=RU&with_genres=18%7C9648%7C80&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:dark:domestic:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 14 / 6
   - speed/results: 368.2 ms; returned 20 of total 1280; pages 64
   - params: `{"first_air_date.gte": "2010-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_genres": "18|9648|80", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763...`
   - sample: История его служанки (2026, RU, 0.0/0); И снова здравствуйте! (2022, RU, 7.7/22); Леший (2026, RU, 0.0/0)

2. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&first_air_date.gte=2010-01-01&with_origin_country=RU&with_genres=18%7C9648%7C80&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:dark:domestic:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 15 / 5
   - speed/results: 311.1 ms; returned 20 of total 1280; pages 64
   - params: `{"first_air_date.gte": "2010-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_genres": "18|9648|80", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763...`
   - sample: На автомате (2024, RU, 7.273/11); Екатерина (2014, RU, 7.7/36); Первая ракетка (2026, RU, 8.0/1)

3. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&first_air_date.lte=2026-07-09&first_air_date.gte=2010-01-01&with_origin_country=RU&with_genres=18%7C9648%7C80&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:dark:domestic:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 19 / 1
   - speed/results: 386.1 ms; returned 20 of total 1280; pages 64
   - params: `{"first_air_date.gte": "2010-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 3, "sort_by": "popularity.desc", "with_genres": "18|9648|80", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763...`
   - sample: Скрытые мотивы (2025, RU, 7.5/2); Берлинская жара (2025, RU, 8.0/1); Пять минут тишины (2017, RU, 8.2/5)

4. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=4&first_air_date.lte=2026-07-09&first_air_date.gte=2010-01-01&with_origin_country=RU&with_genres=18%7C9648%7C80&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:dark:domestic:any`
   - fallback/status/page: `base` / `ok` / 4
   - accepted/rejected: 16 / 4
   - speed/results: 335.8 ms; returned 20 of total 1280; pages 64
   - params: `{"first_air_date.gte": "2010-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 4, "sort_by": "popularity.desc", "with_genres": "18|9648|80", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763...`
   - sample: Плакса (2023, RU, 10.0/1); Жить жизнь (2023, RU, 6.0/5); Happy End (2021, RU, 6.25/32)

5. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=5&first_air_date.lte=2026-07-09&first_air_date.gte=2010-01-01&with_origin_country=RU&with_genres=18%7C9648%7C80&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:dark:domestic:any`
   - fallback/status/page: `base` / `ok` / 5
   - accepted/rejected: 18 / 2
   - speed/results: 346.9 ms; returned 20 of total 1280; pages 64
   - params: `{"first_air_date.gte": "2010-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 5, "sort_by": "popularity.desc", "with_genres": "18|9648|80", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763...`
   - sample: Чернобыль: Зона отчуждения (2014, RU, 7.8/86); Шифр (2019, RU, 8.2/10); Будьте счастливы (2024, RU, 0.0/0)
