# Onboarding Discover Quality Report

- Дата: 2026-07-09
- Режим: live TMDb
- TMDb credentials present: True
- Проходов: 10
- Цель на проход: 120 кандидатов
- Временные SQLite базы: `C:\Users\super\AppData\Local\Temp\watchbane-discover-quality-r4389vhe`

## Короткий вывод

- Полный пул 120/120 собран в 9 из 10 проходов.
- Всего создано кандидатов: 1162.
- Всего выполнено discover-запросов: 77.
- Discover templates: 33.
- Среднее время discover-запроса: 475.5 ms.
- P95 discover-запроса: 415.2 ms.
- Минимальный country hit rate: 1.0.
- TV candidates with seasons initially: 0/682.

Примечание по сериалам: TMDb `/discover/tv` не отдаёт `number_of_seasons` и `number_of_episodes`. Поэтому в стартовом пуле эти поля ожидаемо пустые до ленивого `/tv/{id}` details enrichment при открытии карточки.

## Где оптимизировать

- API бюджет сейчас выглядит нормальным: 33 discover-template дали 77 HTTP `/discover/*` запросов и 1162 кандидата, то есть примерно 15.1 принятого кандидата на discover-запрос. Broad-origin fallback не включался ни разу, дублирующие fallback-запросы не раздувают пул.
- Главная проблема скорости - один выброс: `ru-countries-us-only` занял 19.02s, из них `/discover/tv` US page 1 занял 16201.5 ms. Остальные самые медленные запросы лежат примерно в зоне 362-575 ms. Для оптимизации скорости первым делом стоит смотреть timeout/retry/caching вокруг одиночных TMDb outlier-запросов, а не уменьшать число обычных discover-страниц.
- Главная проблема качества - не попадание по стране, а мусорность отдельных страновых комбинаций. Country hit rate во всех 10 проходах равен 1.0, но `garbage_rate` высокий у `ru-manual-jp-kr` 39.17%, `ru-foreign-new-movies-us-gb` 24.17%, `ru-countries-all-five` 23.33%, `ru-manual-us-kr` 20.83%. Тут вероятнее полезен дополнительный quality gate/скоринг для нулевых голосов, слабой локализации и слишком свежих малооценённых тайтлов.
- Единственный недобор пула - `ru-tv-manual-serious-2010`: 82/120 при 5 запросах и 100 raw results. Это ожидаемый эффект узкого RU TV + жанры `18|9648|80` + исключение дневных/реалити/документальных жанров. Если нужен полный пул именно для такого режима, оптимизация должна быть в расширении страниц или ослаблении genre-фильтра, а не в fallback на чужие страны.
- Сезоны и серии не приходят в стартовом `/discover/tv`: 0/682 TV candidates имеют `number_of_seasons` на этапе пула. Это не баг discover-запроса, а ограничение ответа TMDb; для показа сразу в пуле нужен отдельный батч `/tv/{id}` details, что увеличит API бюджет.

## Сводная таблица

| Scenario | Created | API req | Time | Avg req | Country plan | Country actual | Media actual | Hit | Warnings |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | --- |
| `ru-tv-manual-serious-2010` | 82 | 5 | 1.77s | 213.7ms | RU: 120 | RU: 82 | tv: 82 | 1.0 | Starter pool underfilled: created 82 of 120.; Media quota underfilled: tv planned 120, actual 82.; Country quota underfilled: RU planned 120, actual 82.; Origin quota underfilled: domestic planned 120, actual 82. |
| `ru-countries-us-only` | 120 | 8 | 19.02s | 2247.1ms | US: 120 | US: 120 | movie: 60, tv: 60 | 1.0 | - |
| `ru-countries-ru-only` | 120 | 8 | 4.12s | 386.7ms | RU: 120 | RU: 120 | movie: 60, tv: 60 | 1.0 | - |
| `ru-countries-all-five` | 120 | 10 | 4.12s | 291.8ms | GB: 24, JP: 24, KR: 24, RU: 24, US: 24 | RU: 24, GB: 24, JP: 24, KR: 24, US: 24 | movie: 60, tv: 60 | 1.0 | - |
| `ru-foreign-new-movies-us-gb` | 120 | 8 | 3.72s | 333.6ms | GB: 60, US: 60 | GB: 60, US: 60 | movie: 120 | 1.0 | - |
| `ru-foreign-new-tv-us-gb` | 120 | 7 | 3.36s | 336.1ms | GB: 60, US: 60 | GB: 60, US: 60 | tv: 120 | 1.0 | - |
| `ru-mixed-ru-us` | 120 | 8 | 2.67s | 208.8ms | RU: 60, US: 60 | RU: 60, US: 60 | movie: 60, tv: 60 | 1.0 | - |
| `ru-manual-us-kr` | 120 | 8 | 2.73s | 214.1ms | KR: 60, US: 60 | KR: 60, US: 60 | movie: 60, tv: 60 | 1.0 | - |
| `ru-manual-jp-kr` | 120 | 8 | 2.88s | 228.9ms | JP: 60, KR: 60 | JP: 60, KR: 60 | movie: 60, tv: 60 | 1.0 | - |
| `dark-new-tv-us-gb` | 120 | 7 | 2.34s | 188.9ms | GB: 60, US: 60 | GB: 60, US: 60 | tv: 120 | 1.0 | - |

## ru-tv-manual-serious-2010

- Profile: `{"country_selection": {"country_weights": {"RU": 1.0}, "exclude_home_country": false, "home_country": "RU", "max_countries": 1, "mode": "single_country", "primary_country": "RU", "secondary_country": null, "selected_countries": ["RU"]}, "details_limit": 50, "discover_pages": 5, "exclude_genres": [10766, 10764, 10767, 10763, 10762, 99], "include_genre_mode": "or", "include_genres": [18, 9648, 80], "max_year": null, "media_preference": "tv", "min_year": 2010, "origin_preference": "domestic", "release_preference": "mixed", "ui_language": "ru", "vibe_preference": "dark"}`
- Created/pool: 82 / 82
- API requests: 5; unique/total: 5 / 5
- API budget: templates 1; discover HTTP 5; details 0; broad origin 0; fallback used False
- Yield: raw discover 100; duplicates removed 18; accepted/template 82.0; accepted/discover request 16.4
- Duplicate skipped: 0
- Speed: total 1.77s; discover avg 213.7ms; p50 216.9ms; p95 236.4ms; max 236.4ms
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
   - speed/results: 218.7 ms; returned 20 of total 1280; pages 64
   - params: `{"first_air_date.gte": "2010-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_genres": "18|9648|80", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763...`
   - sample: История его служанки (2026, RU, 0.0/0); И снова здравствуйте! (2022, RU, 7.7/22); Леший (2026, RU, 0.0/0)

2. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&first_air_date.gte=2010-01-01&with_origin_country=RU&with_genres=18%7C9648%7C80&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:dark:domestic:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 15 / 5
   - speed/results: 216.9 ms; returned 20 of total 1280; pages 64
   - params: `{"first_air_date.gte": "2010-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_genres": "18|9648|80", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763...`
   - sample: На автомате (2024, RU, 7.273/11); Екатерина (2014, RU, 7.7/36); Первая ракетка (2026, RU, 8.0/1)

3. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&first_air_date.lte=2026-07-09&first_air_date.gte=2010-01-01&with_origin_country=RU&with_genres=18%7C9648%7C80&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:dark:domestic:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 19 / 1
   - speed/results: 190.3 ms; returned 20 of total 1280; pages 64
   - params: `{"first_air_date.gte": "2010-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 3, "sort_by": "popularity.desc", "with_genres": "18|9648|80", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763...`
   - sample: Скрытые мотивы (2025, RU, 7.5/2); Берлинская жара (2025, RU, 8.0/1); Пять минут тишины (2017, RU, 8.2/5)

4. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=4&first_air_date.lte=2026-07-09&first_air_date.gte=2010-01-01&with_origin_country=RU&with_genres=18%7C9648%7C80&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:dark:domestic:any`
   - fallback/status/page: `base` / `ok` / 4
   - accepted/rejected: 16 / 4
   - speed/results: 206.2 ms; returned 20 of total 1280; pages 64
   - params: `{"first_air_date.gte": "2010-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 4, "sort_by": "popularity.desc", "with_genres": "18|9648|80", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763...`
   - sample: Плакса (2023, RU, 10.0/1); Жить жизнь (2023, RU, 6.0/5); Happy End (2021, RU, 6.25/32)

5. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=5&first_air_date.lte=2026-07-09&first_air_date.gte=2010-01-01&with_origin_country=RU&with_genres=18%7C9648%7C80&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:dark:domestic:any`
   - fallback/status/page: `base` / `ok` / 5
   - accepted/rejected: 18 / 2
   - speed/results: 236.4 ms; returned 20 of total 1280; pages 64
   - params: `{"first_air_date.gte": "2010-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 5, "sort_by": "popularity.desc", "with_genres": "18|9648|80", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763...`
   - sample: Чернобыль: Зона отчуждения (2014, RU, 7.8/86); Шифр (2019, RU, 8.2/10); Будьте счастливы (2024, RU, 0.0/0)


## ru-countries-us-only

- Profile: `{"country_selection": {"country_weights": {"US": 1.0}, "exclude_home_country": false, "home_country": "RU", "max_countries": 1, "mode": "single_country", "primary_country": "US", "secondary_country": null, "selected_countries": ["US"]}, "details_limit": 50, "discover_pages": 3, "exclude_genres": [], "include_genre_mode": "or", "include_genres": [], "max_year": null, "media_preference": "both", "min_year": null, "origin_preference": "foreign", "release_preference": "mixed", "ui_language": "ru", "vibe_preference": "mixed"}`
- Created/pool: 120 / 120
- API requests: 8; unique/total: 8 / 8
- API budget: templates 2; discover HTTP 8; details 0; broad origin 0; fallback used False
- Yield: raw discover 160; duplicates removed 40; accepted/template 60.0; accepted/discover request 15.0
- Duplicate skipped: 0
- Speed: total 19.02s; discover avg 2247.1ms; p50 215.9ms; p95 16201.5ms; max 16201.5ms
- Planned media: `{"movie": 60, "tv": 60}`
- Actual media: `{"movie": 60, "tv": 60}`
- Planned country: `{"US": 120}`
- Actual country: `{"US": 120}`
- Country hit/leak/wrong: 1.0 / 0.0 / 0
- Fallbacks: `{"base": 120}`; fallback share 0.0
- Avg TMDb score/votes/popularity: 7.6161 / 5697.7833 / 140.3284
- Vibe hit light/dark: 0.5167 / 0.6833
- Junk/garbage: 0 (0.0) / 3 (0.025)
- Missing poster/overview: 0 / 3
- TV seasons/episodes present initially: 0/60 and 0/60
- Warnings: `[]`

### Top output sample

| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | Обсессия | 2026 | movie | US | en | 8.269 | 2418 | 722.1192 | 10.6645 | base |
| 21 | Извне | 2022 | tv | US | en | 8.504 | 3945 | 422.8659 | 10.6613 | base |
| 22 | Дом Дракона | 2022 | tv | US | en | 8.367 | 6515 | 412.7348 | 10.661 | base |
| 2 | История игрушек 5 | 2026 | movie | US | en | 7.4 | 534 | 658.6359 | 10.6492 | base |
| 14 | Побег из Шоушенка | 1994 | movie | US | en | 8.724 | 30719 | 166.9172 | 10.6455 | base |
| 3 | День разоблачения | 2026 | movie | US | en | 6.688 | 833 | 496.6377 | 10.6436 | base |
| 35 | Игра Престолов | 2011 | tv | US | en | 8.465 | 27185 | 177.1762 | 10.6433 | base |
| 4 | Закулисье реальности | 2026 | movie | US | en | 6.8 | 946 | 466.6709 | 10.6421 | base |
| 25 | Новичок | 2018 | tv | US | en | 8.5 | 3362 | 231.9076 | 10.6411 | base |
| 37 | Рик и Морти | 2013 | tv | US | en | 8.679 | 11078 | 170.7749 | 10.6407 | base |
| 65 | Во все тяжкие | 2008 | tv | US | en | 8.947 | 18070 | 129.9362 | 10.6406 | base |
| 24 | Закон и порядок. Специальный корпус | 1999 | tv | US | en | 7.953 | 4277 | 270.275 | 10.6406 | base |
| 29 | Сверхъестественное | 2005 | tv | US | en | 8.311 | 8516 | 207.6063 | 10.6404 | base |
| 32 | Анатомия страсти | 2005 | tv | US | en | 8.209 | 10957 | 204.731 | 10.6399 | base |
| 36 | Пацаны | 2019 | tv | US | en | 8.445 | 13072 | 171.7548 | 10.6393 | base |
| 13 | Проект «Конец света» | 2026 | movie | US | en | 8.676 | 5834 | 164.3082 | 10.6377 | base |
| 30 | Менталист | 2008 | tv | US | en | 8.357 | 4390 | 205.5285 | 10.6376 | base |
| 9 | Майкл | 2026 | movie | US | en | 8.706 | 3362 | 178.3103 | 10.6374 | base |
| 31 | Ранчо Даттонов | 2026 | tv | US | en | 9.3 | 393 | 204.5176 | 10.6364 | base |
| 26 | Укрытие | 2023 | tv | US | en | 8.2 | 2191 | 228.8736 | 10.6358 | base |

### Detailed Discover Requests

1. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=US`
   - bucket: `US:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 188.0 ms; returned 20 of total 407512; pages 20376
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Обсессия (2026, , 8.269/2418); История игрушек 5 (2026, , 7.4/534); День разоблачения (2026, , 6.688/833)

2. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 16201.5 ms; returned 20 of total 20219; pages 1011
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Извне (2022, US, 8.504/3945); Дом Дракона (2022, US, 8.367/6515); Xplay (2003, US, 8.5/4)

3. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&primary_release_date.lte=2026-07-09&with_origin_country=US`
   - bucket: `US:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 20 / 0
   - speed/results: 175.2 ms; returned 20 of total 407512; pages 20376
   - params: `{"include_adult": false, "language": "ru-RU", "page": 2, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Супергёрл (2026, , 6.217/410); Мумия (2026, , 8.001/2142); Мандалорец и Грогу (2026, , 6.68/562)

4. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 19 / 1
   - speed/results: 227.5 ms; returned 20 of total 20219; pages 1011
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Тайны Смолвиля (2001, US, 8.192/4503); Флэш (2014, US, 7.756/11655); Йеллоустоун (2018, US, 8.268/3215)

5. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&primary_release_date.lte=2026-07-09&with_origin_country=US`
   - bucket: `US:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 19 / 1
   - speed/results: 204.4 ms; returned 20 of total 407512; pages 20376
   - params: `{"include_adult": false, "language": "ru-RU", "page": 3, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Чумовая пятница 2 (2025, , 6.8/741); Зловещие мертвецы: Пекло (2026, , 7.6/16); Война миров (2025, , 4.104/1023)

6. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&first_air_date.lte=2026-07-09&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 20 / 0
   - speed/results: 197.7 ms; returned 20 of total 20219; pages 1011
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 3, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Люцифер (2016, US, 8.433/15536); Стрела (2012, US, 6.837/6374); ФБР (2018, US, 7.935/918)

7. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=4&primary_release_date.lte=2026-07-09&with_origin_country=US`
   - bucket: `US:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 4
   - accepted/rejected: 1 / 0
   - speed/results: 438.0 ms; returned 20 of total 407512; pages 20376
   - params: `{"include_adult": false, "language": "ru-RU", "page": 4, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Тёмный рыцарь (2008, , 8.532/36042); Дьявол носит Prada (2006, , 7.4/13855); Хокум (2026, , 6.87/490)

8. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=4&first_air_date.lte=2026-07-09&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 4
   - accepted/rejected: 1 / 0
   - speed/results: 344.5 ms; returned 20 of total 20219; pages 1011
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 4, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Медведь (2022, US, 8.137/1796); Гримм (2011, US, 8.27/3562); Сайнфелд (1989, US, 8.262/2371)


## ru-countries-ru-only

- Profile: `{"country_selection": {"country_weights": {"RU": 1.0}, "exclude_home_country": false, "home_country": "RU", "max_countries": 1, "mode": "single_country", "primary_country": "RU", "secondary_country": null, "selected_countries": ["RU"]}, "details_limit": 50, "discover_pages": 3, "exclude_genres": [], "include_genre_mode": "or", "include_genres": [], "max_year": null, "media_preference": "both", "min_year": null, "origin_preference": "domestic", "release_preference": "mixed", "ui_language": "ru", "vibe_preference": "mixed"}`
- Created/pool: 120 / 120
- API requests: 8; unique/total: 8 / 8
- API budget: templates 2; discover HTTP 8; details 0; broad origin 0; fallback used False
- Yield: raw discover 160; duplicates removed 40; accepted/template 60.0; accepted/discover request 15.0
- Duplicate skipped: 0
- Speed: total 4.12s; discover avg 386.7ms; p50 358.9ms; p95 574.9ms; max 574.9ms
- Planned media: `{"movie": 60, "tv": 60}`
- Actual media: `{"movie": 60, "tv": 60}`
- Planned country: `{"RU": 120}`
- Actual country: `{"RU": 120}`
- Country hit/leak/wrong: 1.0 / 0.0 / 0
- Fallbacks: `{"base": 120}`; fallback share 0.0
- Avg TMDb score/votes/popularity: 5.5753 / 96.35 / 10.3248
- Vibe hit light/dark: 0.5667 / 0.575
- Junk/garbage: 4 (0.0333) / 8 (0.0667)
- Missing poster/overview: 0 / 4
- TV seasons/episodes present initially: 0/60 and 0/60
- Warnings: `[]`

### Top output sample

| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | Твоё сердце будет разбито | 2026 | movie | RU | ru | 7.079 | 108 | 212.5677 | 10.6104 | base |
| 55 | Жуки | 2019 | tv | RU | ru | 8.5 | 51 | 10.3253 | 10.599 | base |
| 66 | Полярный | 2019 | tv | RU | ru | 8.7 | 44 | 8.4214 | 10.5989 | base |
| 47 | Пальма | 2021 | movie | RU | ru | 8.1 | 184 | 3.8983 | 10.5988 | base |
| 5 | Время | 2021 | movie | RU | ru | 10.0 | 1 | 6.5585 | 10.5983 | base |
| 38 | Мира | 2022 | movie | RU | ru | 7.539 | 444 | 3.7013 | 10.598 | base |
| 28 | This is Хорошо | 2010 | tv | RU | ru | 10.0 | 1 | 10.0611 | 10.5978 | base |
| 36 | Раз жена, два жена. Дагестанские истории. | 2011 | movie | RU | ru | 10.0 | 1 | 3.9792 | 10.5964 | base |
| 112 | Невский | 2016 | tv | RU | ru | 9.1 | 14 | 8.8965 | 10.5952 | base |
| 115 | Трудные подростки | 2019 | tv | RU | ru | 8.5 | 53 | 8.0061 | 10.5945 | base |
| 43 | Вторжение | 2020 | movie | RU | ru | 6.861 | 895 | 4.5577 | 10.5939 | base |
| 106 | Лучше, чем люди | 2018 | tv | RU | ru | 7.377 | 455 | 6.6851 | 10.5931 | base |
| 76 | Хардкор | 2015 | movie | RU | en | 6.412 | 2692 | 4.089 | 10.5924 | base |
| 72 | Он - дракон | 2015 | movie | RU | ru | 7.168 | 417 | 3.591 | 10.5922 | base |
| 110 | Девушки с Макаровым | 2021 | tv | RU | ru | 8.478 | 23 | 7.8824 | 10.5912 | base |
| 22 | И снова здравствуйте! | 2022 | tv | RU | ru | 7.7 | 22 | 26.259 | 10.591 | base |
| 92 | Однажды в России | 2014 | tv | RU | ru | 8.2 | 23 | 10.1859 | 10.5904 | base |
| 12 | Конёк-Горбунок | 2021 | movie | RU | ru | 6.8 | 313 | 5.2892 | 10.5904 | base |
| 62 | Реальные Пацаны | 2010 | tv | RU | ru | 7.5 | 72 | 11.2768 | 10.5899 | base |
| 81 | Притяжение | 2017 | movie | RU | ru | 6.667 | 919 | 3.4883 | 10.5898 | base |

### Detailed Discover Requests

1. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=RU`
   - bucket: `RU:movie:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 331.3 ms; returned 20 of total 16433; pages 822
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "RU"}`
   - sample: Твоё сердце будет разбито (2026, , 7.079/108); Непослушная (2023, , 6.229/106); Сводишь с ума (2025, , 7.7/14)

2. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=RU&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 15 / 5
   - speed/results: 371.4 ms; returned 20 of total 2867; pages 144
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: История его служанки (2026, RU, 0.0/0); И снова здравствуйте! (2022, RU, 7.7/22); Леший (2026, RU, 0.0/0)

3. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&primary_release_date.lte=2026-07-09&with_origin_country=RU`
   - bucket: `RU:movie:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 18 / 2
   - speed/results: 574.9 ms; returned 20 of total 16433; pages 822
   - params: `{"include_adult": false, "language": "ru-RU", "page": 2, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "RU"}`
   - sample: Раз жена, два жена. Дагестанские истории. (2011, , 10.0/1); 14+ Продолжение (2023, , 6.6/10); Мира (2022, , 7.539/444)

4. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&with_origin_country=RU&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 18 / 2
   - speed/results: 339.8 ms; returned 20 of total 2867; pages 144
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Камеди Клаб (2005, RU, 6.4/25); Жуки (2019, RU, 8.5/51); След (2007, RU, 6.833/12)

5. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&primary_release_date.lte=2026-07-09&with_origin_country=RU`
   - bucket: `RU:movie:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 19 / 1
   - speed/results: 360.2 ms; returned 20 of total 16433; pages 822
   - params: `{"include_adult": false, "language": "ru-RU", "page": 3, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "RU"}`
   - sample: Он - дракон (2015, , 7.168/417); Здоровый человек (2023, , 5.5/2); Невероятные приключения Шурика (2025, , 5.5/9)

6. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&first_air_date.lte=2026-07-09&with_origin_country=RU&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 16 / 4
   - speed/results: 357.7 ms; returned 20 of total 2867; pages 144
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 3, "sort_by": "popularity.desc", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Слово пацана. Кровь на асфальте (2023, RU, 8.643/214); СашаТаня (2013, RU, 5.9/24); Однажды в России (2014, RU, 8.2/23)

7. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=4&primary_release_date.lte=2026-07-09&with_origin_country=RU`
   - bucket: `RU:movie:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 4
   - accepted/rejected: 3 / 0
   - speed/results: 422.5 ms; returned 20 of total 16433; pages 822
   - params: `{"include_adult": false, "language": "ru-RU", "page": 4, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "RU"}`
   - sample: Простоквашино (2026, , 3.5/4); Гранит (2021, , 7.0/45); Кукушка (2002, , 7.1/118)

8. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=4&first_air_date.lte=2026-07-09&with_origin_country=RU&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 4
   - accepted/rejected: 11 / 2
   - speed/results: 335.5 ms; returned 20 of total 2867; pages 144
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 4, "sort_by": "popularity.desc", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Девушки с Макаровым (2021, RU, 8.478/23); Литейный, 4 (2008, RU, 5.0/1); Невский (2016, RU, 9.1/14)


## ru-countries-all-five

- Profile: `{"country_selection": {"country_weights": {"GB": 0.2, "JP": 0.2, "KR": 0.2, "RU": 0.2, "US": 0.2}, "exclude_home_country": false, "home_country": "RU", "max_countries": 5, "mode": "multi_country", "primary_country": "US", "secondary_country": "RU", "selected_countries": ["US", "RU", "GB", "KR", "JP"]}, "details_limit": 50, "discover_pages": 3, "exclude_genres": [], "include_genre_mode": "or", "include_genres": [], "max_year": null, "media_preference": "both", "min_year": null, "origin_preference": "mixed", "release_preference": "mixed", "ui_language": "ru", "vibe_preference": "mixed"}`
- Created/pool: 120 / 120
- API requests: 10; unique/total: 10 / 10
- API budget: templates 10; discover HTTP 10; details 0; broad origin 0; fallback used False
- Yield: raw discover 200; duplicates removed 80; accepted/template 12.0; accepted/discover request 12.0
- Duplicate skipped: 0
- Speed: total 4.12s; discover avg 291.8ms; p50 317.2ms; p95 415.2ms; max 415.2ms
- Planned media: `{"movie": 60, "tv": 60}`
- Actual media: `{"movie": 60, "tv": 60}`
- Planned country: `{"GB": 24, "JP": 24, "KR": 24, "RU": 24, "US": 24}`
- Actual country: `{"GB": 24, "JP": 24, "KR": 24, "RU": 24, "US": 24}`
- Country hit/leak/wrong: 1.0 / 0.0 / 0
- Fallbacks: `{"base": 120}`; fallback share 0.0
- Avg TMDb score/votes/popularity: 6.544 / 2144.5 / 112.0963
- Vibe hit light/dark: 0.55 / 0.7
- Junk/garbage: 1 (0.0083) / 28 (0.2333)
- Missing poster/overview: 0 / 27
- TV seasons/episodes present initially: 0/60 and 0/60
- Warnings: `[]`

### Top output sample

| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 49 | Обсессия | 2026 | movie | US | en | 8.269 | 2418 | 722.1192 | 10.2645 | base |
| 109 | Извне | 2022 | tv | US | en | 8.504 | 3945 | 422.8659 | 10.2613 | base |
| 110 | Дом Дракона | 2022 | tv | US | en | 8.367 | 6515 | 412.7348 | 10.261 | base |
| 50 | История игрушек 5 | 2026 | movie | US | en | 7.4 | 534 | 658.6359 | 10.2492 | base |
| 85 | Реинкарнация безработного: История о приключениях в другом мире | 2021 | tv | JP | ja | 8.479 | 1552 | 310.3409 | 10.2457 | base |
| 51 | День разоблачения | 2026 | movie | US | en | 6.688 | 833 | 496.6377 | 10.2436 | base |
| 52 | Закулисье реальности | 2026 | movie | US | en | 6.8 | 946 | 466.6709 | 10.2421 | base |
| 113 | Новичок | 2018 | tv | US | en | 8.5 | 3362 | 231.9076 | 10.2411 | base |
| 112 | Закон и порядок. Специальный корпус | 1999 | tv | US | en | 7.953 | 4277 | 270.275 | 10.2406 | base |
| 117 | Сверхъестественное | 2005 | tv | US | en | 8.311 | 8516 | 207.6063 | 10.2404 | base |
| 120 | Анатомия страсти | 2005 | tv | US | en | 8.209 | 10957 | 204.731 | 10.2399 | base |
| 118 | Менталист | 2008 | tv | US | en | 8.357 | 4390 | 205.5285 | 10.2376 | base |
| 57 | Майкл | 2026 | movie | US | en | 8.706 | 3362 | 178.3103 | 10.2374 | base |
| 119 | Ранчо Даттонов | 2026 | tv | US | en | 9.3 | 393 | 204.5176 | 10.2364 | base |
| 114 | Укрытие | 2023 | tv | US | en | 8.2 | 2191 | 228.8736 | 10.2358 | base |
| 99 | Истинное образование | 2026 | tv | KR | ko | 9.467 | 629 | 134.6042 | 10.2339 | base |
| 54 | Дьявол носит Prada 2 | 2026 | movie | US | en | 7.019 | 1331 | 349.8566 | 10.2339 | base |
| 75 | Острые козырьки | 2013 | tv | GB | en | 8.527 | 11188 | 83.5895 | 10.2319 | base |
| 19 | Начало | 2010 | movie | GB | en | 8.372 | 39497 | 45.0453 | 10.2316 | base |
| 87 | Табакошка | 2026 | tv | JP | ja | 8.5 | 10 | 378.8917 | 10.2307 | base |

### Detailed Discover Requests

1. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=RU`
   - bucket: `RU:movie:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 12 / 0
   - speed/results: 415.2 ms; returned 20 of total 16433; pages 822
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "RU"}`
   - sample: Твоё сердце будет разбито (2026, , 7.079/108); Непослушная (2023, , 6.229/106); Сводишь с ума (2025, , 7.7/14)

2. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=GB`
   - bucket: `GB:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 12 / 0
   - speed/results: 319.1 ms; returned 20 of total 52762; pages 2639
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "GB"}`
   - sample: Ущерб (1992, , 6.6/701); Следствие ведут овечки (2026, , 7.818/785); Graphic Desires (2023, , 7.068/118)

3. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=JP`
   - bucket: `JP:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 12 / 0
   - speed/results: 366.4 ms; returned 20 of total 50184; pages 2510
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "JP"}`
   - sample: Истребитель демонов: Бесконечный замок (2025, , 7.726/888); 名探偵コナン ハイウェイの堕天使 (2026, , 8.0/11); まいちゃんの日常 (2014, , 5.167/18)

4. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=KR`
   - bucket: `KR:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 12 / 0
   - speed/results: 315.4 ms; returned 20 of total 14287; pages 715
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "KR"}`
   - sample: 버려진 청춘 (1982, , 0.0/0); Паразиты (2019, , 8.492/20834); Колония (2026, , 7.134/82)

5. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=US`
   - bucket: `US:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 12 / 0
   - speed/results: 167.4 ms; returned 20 of total 407512; pages 20376
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Обсессия (2026, , 8.269/2418); История игрушек 5 (2026, , 7.4/534); День разоблачения (2026, , 6.688/833)

6. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=RU&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 12 / 5
   - speed/results: 193.5 ms; returned 20 of total 2867; pages 144
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: История его служанки (2026, RU, 0.0/0); И снова здравствуйте! (2022, RU, 7.7/22); Леший (2026, RU, 0.0/0)

7. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=GB&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `GB:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 12 / 0
   - speed/results: 307.8 ms; returned 20 of total 7774; pages 389
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "GB", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Доктор Кто (2005, GB, 7.613/3392); Чисто английские убийства (1997, GB, 7.469/358); Острые козырьки (2013, GB, 8.527/11188)

8. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=JP&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `JP:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 12 / 0
   - speed/results: 340.0 ms; returned 20 of total 13625; pages 682
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "JP", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Реинкарнация безработного: История о приключениях в другом мире (2021, JP, 8.479/1552); Мучайся, Адам (2024, JP, 6.875/36); Табакошка (2026, JP, 8.5/10)

9. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=KR&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `KR:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 12 / 0
   - speed/results: 325.7 ms; returned 20 of total 6740; pages 337
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "KR", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Агент Ким возобновил свою деятельность (2026, KR, 7.386/22); 검사실의 제안 (2026, KR, 5.0/4); Истинное образование (2026, KR, 9.467/629)

10. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 12 / 0
   - speed/results: 167.8 ms; returned 20 of total 20219; pages 1011
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Извне (2022, US, 8.504/3945); Дом Дракона (2022, US, 8.367/6515); Xplay (2003, US, 8.5/4)


## ru-foreign-new-movies-us-gb

- Profile: `{"country_selection": {"country_weights": {"GB": 0.5, "US": 0.5}, "exclude_home_country": true, "home_country": "RU", "max_countries": 2, "mode": "preset_foreign", "primary_country": "US", "secondary_country": "GB", "selected_countries": ["US", "GB"]}, "details_limit": 50, "discover_pages": 3, "exclude_genres": [], "include_genre_mode": "or", "include_genres": [], "max_year": null, "media_preference": "movie", "min_year": null, "origin_preference": "foreign", "release_preference": "new", "ui_language": "ru", "vibe_preference": "mixed"}`
- Created/pool: 120 / 120
- API requests: 8; unique/total: 8 / 8
- API budget: templates 2; discover HTTP 8; details 0; broad origin 0; fallback used False
- Yield: raw discover 160; duplicates removed 40; accepted/template 60.0; accepted/discover request 15.0
- Duplicate skipped: 0
- Speed: total 3.72s; discover avg 333.6ms; p50 339.0ms; p95 353.5ms; max 353.5ms
- Planned media: `{"movie": 120}`
- Actual media: `{"movie": 120}`
- Planned country: `{"GB": 60, "US": 60}`
- Actual country: `{"GB": 60, "US": 60}`
- Country hit/leak/wrong: 1.0 / 0.0 / 0
- Fallbacks: `{"base": 120}`; fallback share 0.0
- Avg TMDb score/votes/popularity: 6.7113 / 1238.5667 / 71.3774
- Vibe hit light/dark: 0.475 / 0.6833
- Junk/garbage: 5 (0.0417) / 29 (0.2417)
- Missing poster/overview: 0 / 24
- TV seasons/episodes present initially: 0/0 and 0/0
- Warnings: `[]`

### Top output sample

| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 21 | Обсессия | 2026 | movie | US | en | 8.269 | 2418 | 722.1192 | 10.6745 | base |
| 22 | История игрушек 5 | 2026 | movie | US | en | 7.4 | 534 | 658.6359 | 10.6592 | base |
| 23 | День разоблачения | 2026 | movie | US | en | 6.688 | 833 | 496.6377 | 10.6536 | base |
| 24 | Закулисье реальности | 2026 | movie | US | en | 6.8 | 946 | 466.6709 | 10.6521 | base |
| 33 | Проект «Конец света» | 2026 | movie | US | en | 8.676 | 5834 | 164.3082 | 10.6477 | base |
| 29 | Майкл | 2026 | movie | US | en | 8.706 | 3362 | 178.3103 | 10.6474 | base |
| 26 | Дьявол носит Prada 2 | 2026 | movie | US | en | 7.019 | 1331 | 349.8566 | 10.6439 | base |
| 36 | Супер Марио: Галактическое кино | 2026 | movie | US | en | 8.249 | 2999 | 136.6925 | 10.6374 | base |
| 64 | В чужой шкуре | 2026 | movie | US | en | 8.916 | 1893 | 90.1445 | 10.6365 | base |
| 35 | Мортал Комбат 2 | 2026 | movie | US | en | 7.98 | 1903 | 149.3051 | 10.6341 | base |
| 25 | Очень страшное кино | 2026 | movie | US | en | 5.4 | 429 | 462.1724 | 10.6341 | base |
| 39 | Мумия | 2026 | movie | US | en | 8.001 | 2142 | 110.0089 | 10.6304 | base |
| 67 | Каратель: Последнее убийство | 2026 | movie | US | en | 8.34 | 1804 | 83.313 | 10.6296 | base |
| 66 | Прыгуны | 2026 | movie | US | en | 8.197 | 1850 | 84.2429 | 10.6285 | base |
| 37 | Аватар: Пламя и пепел | 2025 | movie | US | en | 7.618 | 3721 | 112.4172 | 10.6274 | base |
| 1 | Следствие ведут овечки | 2026 | movie | GB | en | 7.818 | 785 | 118.7959 | 10.627 | base |
| 68 | Сообщения для Изабель | 2026 | movie | US | en | 8.386 | 494 | 74.8817 | 10.6235 | base |
| 110 | Дикий робот | 2024 | movie | US | en | 8.313 | 6238 | 37.3913 | 10.6233 | base |
| 28 | Глубокие воды | 2026 | movie | US | en | 7.176 | 170 | 214.656 | 10.6228 | base |
| 27 | Гражданин-мститель | 2026 | movie | US | en | 6.6 | 209 | 254.4411 | 10.622 | base |

### Detailed Discover Requests

1. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&primary_release_date.gte=2022-01-01&with_origin_country=GB`
   - bucket: `GB:movie:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 338.7 ms; returned 20 of total 11574; pages 579
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.gte": "2022-01-01", "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "GB"}`
   - sample: Следствие ведут овечки (2026, , 7.818/785); Graphic Desires (2023, , 7.068/118); Грязные деньги (2026, , 7.221/416)

2. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&primary_release_date.gte=2022-01-01&with_origin_country=US`
   - bucket: `US:movie:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 19 / 1
   - speed/results: 352.0 ms; returned 20 of total 73661; pages 3684
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.gte": "2022-01-01", "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Обсессия (2026, , 8.269/2418); История игрушек 5 (2026, , 7.4/534); День разоблачения (2026, , 6.688/833)

3. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&primary_release_date.lte=2026-07-09&primary_release_date.gte=2022-01-01&with_origin_country=GB`
   - bucket: `GB:movie:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 20 / 0
   - speed/results: 353.5 ms; returned 20 of total 11574; pages 579
   - params: `{"include_adult": false, "language": "ru-RU", "page": 2, "primary_release_date.gte": "2022-01-01", "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "GB"}`
   - sample: Наследник (2026, , 6.93/536); Острые козырьки: бессмертный (2026, , 7.244/1060); Флавия. Юный детектив (2026, , 6.2/6)

4. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&primary_release_date.lte=2026-07-09&primary_release_date.gte=2022-01-01&with_origin_country=US`
   - bucket: `US:movie:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 18 / 2
   - speed/results: 317.2 ms; returned 20 of total 73661; pages 3684
   - params: `{"include_adult": false, "language": "ru-RU", "page": 2, "primary_release_date.gte": "2022-01-01", "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Мандалорец и Грогу (2026, , 6.68/562); Моана (2026, , 4.8/29); Братик (2026, , 6.422/205)

5. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&primary_release_date.lte=2026-07-09&primary_release_date.gte=2022-01-01&with_origin_country=GB`
   - bucket: `GB:movie:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 19 / 1
   - speed/results: 289.7 ms; returned 20 of total 11574; pages 579
   - params: `{"include_adult": false, "language": "ru-RU", "page": 3, "primary_release_date.gte": "2022-01-01", "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "GB"}`
   - sample: Static Moon (2025, , 0.0/0); 1000 Men and Me: The Bonnie Blue Story (2025, , 5.2/22); Jamie Vardy (2026, , 7.194/31)

6. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&primary_release_date.lte=2026-07-09&primary_release_date.gte=2022-01-01&with_origin_country=US`
   - bucket: `US:movie:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 18 / 2
   - speed/results: 328.6 ms; returned 20 of total 73661; pages 3684
   - params: `{"include_adult": false, "language": "ru-RU", "page": 3, "primary_release_date.gte": "2022-01-01", "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Властелины вселенной (2026, , 6.937/380); Горничная (2025, , 7.266/2576); Убежище (2026, , 7.726/1431)

7. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=4&primary_release_date.lte=2026-07-09&primary_release_date.gte=2022-01-01&with_origin_country=GB`
   - bucket: `GB:movie:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 4
   - accepted/rejected: 1 / 0
   - speed/results: 350.0 ms; returned 20 of total 11574; pages 579
   - params: `{"include_adult": false, "language": "ru-RU", "page": 4, "primary_release_date.gte": "2022-01-01", "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "GB"}`
   - sample: Как заниматься сексом (2023, , 6.233/512); Ophelia (2026, , 0.0/0); Хоровое пение (2025, , 6.427/41)

8. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=4&primary_release_date.lte=2026-07-09&primary_release_date.gte=2022-01-01&with_origin_country=US`
   - bucket: `US:movie:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 4
   - accepted/rejected: 5 / 0
   - speed/results: 339.4 ms; returned 20 of total 73661; pages 3684
   - params: `{"include_adult": false, "language": "ru-RU", "page": 4, "primary_release_date.gte": "2022-01-01", "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: На помощь! (2026, , 7.046/1911); Миньоны: Грювитация (2022, , 7.263/4045); Гадкий я 4 (2024, , 6.982/3252)


## ru-foreign-new-tv-us-gb

- Profile: `{"country_selection": {"country_weights": {"GB": 0.5, "US": 0.5}, "exclude_home_country": true, "home_country": "RU", "max_countries": 2, "mode": "preset_foreign", "primary_country": "US", "secondary_country": "GB", "selected_countries": ["US", "GB"]}, "details_limit": 50, "discover_pages": 3, "exclude_genres": [], "include_genre_mode": "or", "include_genres": [], "max_year": null, "media_preference": "tv", "min_year": null, "origin_preference": "foreign", "release_preference": "new", "ui_language": "ru", "vibe_preference": "mixed"}`
- Created/pool: 120 / 120
- API requests: 7; unique/total: 7 / 7
- API budget: templates 2; discover HTTP 7; details 0; broad origin 0; fallback used False
- Yield: raw discover 140; duplicates removed 20; accepted/template 60.0; accepted/discover request 17.1429
- Duplicate skipped: 0
- Speed: total 3.36s; discover avg 336.1ms; p50 327.4ms; p95 383.1ms; max 383.1ms
- Planned media: `{"tv": 120}`
- Actual media: `{"tv": 120}`
- Planned country: `{"GB": 60, "US": 60}`
- Actual country: `{"GB": 60, "US": 60}`
- Country hit/leak/wrong: 1.0 / 0.0 / 0
- Fallbacks: `{"base": 120}`; fallback share 0.0
- Avg TMDb score/votes/popularity: 7.6242 / 840.125 / 40.5849
- Vibe hit light/dark: 0.3833 / 0.9167
- Junk/garbage: 0 (0.0) / 3 (0.025)
- Missing poster/overview: 0 / 3
- TV seasons/episodes present initially: 0/120 and 0/120
- Warnings: `[]`

### Top output sample

| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 21 | Извне | 2022 | tv | US | en | 8.504 | 3945 | 422.8659 | 10.6633 | base |
| 22 | Дом Дракона | 2022 | tv | US | en | 8.367 | 6515 | 412.7348 | 10.663 | base |
| 24 | Ранчо Даттонов | 2026 | tv | US | en | 9.3 | 393 | 204.5176 | 10.6471 | base |
| 26 | Вне кампуса | 2026 | tv | US | en | 8.942 | 649 | 155.8569 | 10.6406 | base |
| 23 | Укрытие | 2023 | tv | US | en | 8.2 | 2191 | 228.8736 | 10.6401 | base |
| 25 | Аватар: Легенда об Аанге | 2024 | tv | US | en | 7.8 | 1231 | 190.0948 | 10.6315 | base |
| 32 | Больница Питт | 2025 | tv | US | en | 8.727 | 831 | 76.1387 | 10.629 | base |
| 30 | Люди Икс '97 | 2024 | tv | US | en | 8.586 | 730 | 94.5919 | 10.6271 | base |
| 39 | Уэнздей | 2022 | tv | US | en | 8.342 | 10618 | 49.7687 | 10.6269 | base |
| 77 | Одни из нас | 2023 | tv | US | en | 8.421 | 7108 | 37.8123 | 10.6249 | base |
| 28 | Ричер | 2022 | tv | US | en | 8.1 | 2912 | 93.6796 | 10.6243 | base |
| 66 | Паук-Нуар | 2026 | tv | US | en | 8.457 | 671 | 45.1562 | 10.6229 | base |
| 72 | Отель Хазбин | 2024 | tv | US | en | 8.566 | 1598 | 40.0471 | 10.6226 | base |
| 27 | Большой потенциал | 2024 | tv | US | en | 8.19 | 575 | 94.9453 | 10.6224 | base |
| 29 | Я тебя отыщу | 2026 | tv | US | en | 8.217 | 224 | 91.8228 | 10.6221 | base |
| 35 | Король Талсы | 2022 | tv | US | en | 8.294 | 2679 | 62.219 | 10.622 | base |
| 80 | Рыцарь Семи Королевств | 2026 | tv | US | en | 8.428 | 988 | 35.5484 | 10.6219 | base |
| 2 | Гангстерленд | 2025 | tv | GB | en | 8.346 | 715 | 35.2481 | 10.6214 | base |
| 31 | Медведь | 2022 | tv | US | en | 8.137 | 1796 | 82.0674 | 10.6211 | base |
| 69 | Разделение | 2022 | tv | US | en | 8.398 | 2737 | 44.368 | 10.62 | base |

### Detailed Discover Requests

1. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=GB&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `GB:tv:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 300.2 ms; returned 20 of total 868; pages 44
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "GB", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Медленные лошади (2022, GB, 8.006/882); Гангстерленд (2025, GB,US, 8.346/715); Заключённый (2026, GB, 5.5/23)

2. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 325.8 ms; returned 20 of total 5136; pages 257
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Извне (2022, US, 8.504/3945); Дом Дракона (2022, US, 8.367/6515); Укрытие (2023, US, 8.2/2191)

3. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=GB&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `GB:tv:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 20 / 0
   - speed/results: 327.4 ms; returned 20 of total 868; pages 44
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "GB", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Харри Холе (2026, NO,GB,US, 7.3/101); Крукхейвен (2026, GB, 8.778/9); Скотт Пилигрим жмет на газ (2023, JP,GB,US, 7.957/409)

4. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 20 / 0
   - speed/results: 338.5 ms; returned 20 of total 5136; pages 257
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Властелин колец: Кольца Власти (2022, US, 7.2/3759); Целую, Китти (2023, US, 8.099/678); Уидоус-Бэй (2026, US, 8.185/274)

5. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=GB&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `GB:tv:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 20 / 0
   - speed/results: 313.5 ms; returned 20 of total 868; pages 44
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 3, "sort_by": "popularity.desc", "with_origin_country": "GB", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: The Gold (2023, GB, 7.31/71); Война между сушей и морем (2025, GB, 7.542/177); Турист (2022, GB, 6.751/229)

6. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 19 / 1
   - speed/results: 383.1 ms; returned 20 of total 5136; pages 257
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 3, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Andor (2022, US, 8.298/2080); Гангстерленд (2025, GB,US, 8.346/715); «Монарх»: Наследие монстров (2023, US, 7.751/1343)

7. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=4&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:new_sweep:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 4
   - accepted/rejected: 1 / 0
   - speed/results: 364.1 ms; returned 20 of total 5136; pages 257
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 4, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Третий лишний (2024, US, 7.953/697); Песочный человек (2022, US, 7.865/2635); Лунный рыцарь (2022, US, 7.645/3545)


## ru-mixed-ru-us

- Profile: `{"country_selection": {"country_weights": {"RU": 0.5, "US": 0.5}, "exclude_home_country": false, "home_country": "RU", "max_countries": 2, "mode": "preset_mixed", "primary_country": "RU", "secondary_country": "US", "selected_countries": ["RU", "US"]}, "details_limit": 50, "discover_pages": 3, "exclude_genres": [], "include_genre_mode": "or", "include_genres": [], "max_year": null, "media_preference": "both", "min_year": null, "origin_preference": "mixed", "release_preference": "mixed", "ui_language": "ru", "vibe_preference": "mixed"}`
- Created/pool: 120 / 120
- API requests: 8; unique/total: 8 / 8
- API budget: templates 4; discover HTTP 8; details 0; broad origin 0; fallback used False
- Yield: raw discover 160; duplicates removed 40; accepted/template 30.0; accepted/discover request 15.0
- Duplicate skipped: 0
- Speed: total 2.67s; discover avg 208.8ms; p50 194.6ms; p95 317.6ms; max 317.6ms
- Planned media: `{"movie": 60, "tv": 60}`
- Actual media: `{"movie": 60, "tv": 60}`
- Planned country: `{"RU": 60, "US": 60}`
- Actual country: `{"RU": 60, "US": 60}`
- Country hit/leak/wrong: 1.0 / 0.0 / 0
- Fallbacks: `{"base": 120}`; fallback share 0.0
- Avg TMDb score/votes/popularity: 6.5811 / 2143.9 / 108.9126
- Vibe hit light/dark: 0.5583 / 0.625
- Junk/garbage: 4 (0.0333) / 8 (0.0667)
- Missing poster/overview: 0 / 4
- TV seasons/episodes present initially: 0/60 and 0/60
- Warnings: `[]`

### Top output sample

| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 21 | Обсессия | 2026 | movie | US | en | 8.269 | 2418 | 722.1192 | 10.4145 | base |
| 56 | Извне | 2022 | tv | US | en | 8.504 | 3945 | 422.8659 | 10.4113 | base |
| 57 | Дом Дракона | 2022 | tv | US | en | 8.367 | 6515 | 412.7348 | 10.411 | base |
| 22 | История игрушек 5 | 2026 | movie | US | en | 7.4 | 534 | 658.6359 | 10.3992 | base |
| 34 | Побег из Шоушенка | 1994 | movie | US | en | 8.724 | 30719 | 166.9172 | 10.3955 | base |
| 23 | День разоблачения | 2026 | movie | US | en | 6.688 | 833 | 496.6377 | 10.3936 | base |
| 70 | Игра Престолов | 2011 | tv | US | en | 8.465 | 27185 | 177.1762 | 10.3933 | base |
| 24 | Закулисье реальности | 2026 | movie | US | en | 6.8 | 946 | 466.6709 | 10.3921 | base |
| 60 | Новичок | 2018 | tv | US | en | 8.5 | 3362 | 231.9076 | 10.3911 | base |
| 72 | Рик и Морти | 2013 | tv | US | en | 8.679 | 11078 | 170.7749 | 10.3907 | base |
| 115 | Во все тяжкие | 2008 | tv | US | en | 8.947 | 18070 | 129.9362 | 10.3906 | base |
| 59 | Закон и порядок. Специальный корпус | 1999 | tv | US | en | 7.953 | 4277 | 270.275 | 10.3906 | base |
| 64 | Сверхъестественное | 2005 | tv | US | en | 8.311 | 8516 | 207.6063 | 10.3904 | base |
| 67 | Анатомия страсти | 2005 | tv | US | en | 8.209 | 10957 | 204.731 | 10.3899 | base |
| 71 | Пацаны | 2019 | tv | US | en | 8.445 | 13072 | 171.7548 | 10.3893 | base |
| 33 | Проект «Конец света» | 2026 | movie | US | en | 8.676 | 5834 | 164.3082 | 10.3877 | base |
| 65 | Менталист | 2008 | tv | US | en | 8.357 | 4390 | 205.5285 | 10.3876 | base |
| 29 | Майкл | 2026 | movie | US | en | 8.706 | 3362 | 178.3103 | 10.3874 | base |
| 66 | Ранчо Даттонов | 2026 | tv | US | en | 9.3 | 393 | 204.5176 | 10.3864 | base |
| 61 | Укрытие | 2023 | tv | US | en | 8.2 | 2191 | 228.8736 | 10.3858 | base |

### Detailed Discover Requests

1. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=RU`
   - bucket: `RU:movie:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 317.6 ms; returned 20 of total 16433; pages 822
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "RU"}`
   - sample: Твоё сердце будет разбито (2026, , 7.079/108); Непослушная (2023, , 6.229/106); Сводишь с ума (2025, , 7.7/14)

2. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=US`
   - bucket: `US:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 159.6 ms; returned 20 of total 407512; pages 20376
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Обсессия (2026, , 8.269/2418); История игрушек 5 (2026, , 7.4/534); День разоблачения (2026, , 6.688/833)

3. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=RU&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 15 / 5
   - speed/results: 191.0 ms; returned 20 of total 2867; pages 144
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: История его служанки (2026, RU, 0.0/0); И снова здравствуйте! (2022, RU, 7.7/22); Леший (2026, RU, 0.0/0)

4. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 198.1 ms; returned 20 of total 20219; pages 1011
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Извне (2022, US, 8.504/3945); Дом Дракона (2022, US, 8.367/6515); Xplay (2003, US, 8.5/4)

5. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&primary_release_date.lte=2026-07-09&with_origin_country=RU`
   - bucket: `RU:movie:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 10 / 0
   - speed/results: 184.6 ms; returned 20 of total 16433; pages 822
   - params: `{"include_adult": false, "language": "ru-RU", "page": 2, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "RU"}`
   - sample: Раз жена, два жена. Дагестанские истории. (2011, , 10.0/1); 14+ Продолжение (2023, , 6.6/10); Мира (2022, , 7.539/444)

6. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&primary_release_date.lte=2026-07-09&with_origin_country=US`
   - bucket: `US:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 10 / 0
   - speed/results: 139.5 ms; returned 20 of total 407512; pages 20376
   - params: `{"include_adult": false, "language": "ru-RU", "page": 2, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Супергёрл (2026, , 6.217/410); Мумия (2026, , 8.001/2142); Мандалорец и Грогу (2026, , 6.68/562)

7. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&with_origin_country=RU&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `RU:tv:mixed:mixed:domestic:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 15 / 2
   - speed/results: 264.2 ms; returned 20 of total 2867; pages 144
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "RU", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Камеди Клаб (2005, RU, 6.4/25); Жуки (2019, RU, 8.5/51); След (2007, RU, 6.833/12)

8. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 10 / 0
   - speed/results: 215.8 ms; returned 20 of total 20219; pages 1011
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Тайны Смолвиля (2001, US, 8.192/4503); Флэш (2014, US, 7.756/11655); Йеллоустоун (2018, US, 8.268/3215)


## ru-manual-us-kr

- Profile: `{"country_selection": {"country_weights": {"KR": 0.5, "US": 0.5}, "exclude_home_country": false, "home_country": "RU", "max_countries": 2, "mode": "country_pair", "primary_country": "US", "secondary_country": "KR", "selected_countries": ["US", "KR"]}, "details_limit": 50, "discover_pages": 3, "exclude_genres": [], "include_genre_mode": "or", "include_genres": [], "max_year": null, "media_preference": "both", "min_year": null, "origin_preference": "foreign", "release_preference": "mixed", "ui_language": "ru", "vibe_preference": "mixed"}`
- Created/pool: 120 / 120
- API requests: 8; unique/total: 8 / 8
- API budget: templates 4; discover HTTP 8; details 0; broad origin 0; fallback used False
- Yield: raw discover 160; duplicates removed 40; accepted/template 30.0; accepted/discover request 15.0
- Duplicate skipped: 0
- Speed: total 2.73s; discover avg 214.1ms; p50 189.4ms; p95 331.9ms; max 331.9ms
- Planned media: `{"movie": 60, "tv": 60}`
- Actual media: `{"movie": 60, "tv": 60}`
- Planned country: `{"KR": 60, "US": 60}`
- Actual country: `{"KR": 60, "US": 60}`
- Country hit/leak/wrong: 1.0 / 0.0 / 0
- Fallbacks: `{"base": 120}`; fallback share 0.0
- Avg TMDb score/votes/popularity: 7.2359 / 2802.725 / 119.1284
- Vibe hit light/dark: 0.575 / 0.725
- Junk/garbage: 1 (0.0083) / 25 (0.2083)
- Missing poster/overview: 0 / 24
- TV seasons/episodes present initially: 0/60 and 0/60
- Warnings: `[]`

### Top output sample

| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 20 | Обсессия | 2026 | movie | US | en | 8.269 | 2418 | 722.1192 | 10.4145 | base |
| 60 | Извне | 2022 | tv | US | en | 8.504 | 3945 | 422.8659 | 10.4113 | base |
| 61 | Дом Дракона | 2022 | tv | US | en | 8.367 | 6515 | 412.7348 | 10.411 | base |
| 21 | История игрушек 5 | 2026 | movie | US | en | 7.4 | 534 | 658.6359 | 10.3992 | base |
| 33 | Побег из Шоушенка | 1994 | movie | US | en | 8.724 | 30719 | 166.9172 | 10.3955 | base |
| 22 | День разоблачения | 2026 | movie | US | en | 6.688 | 833 | 496.6377 | 10.3936 | base |
| 74 | Игра Престолов | 2011 | tv | US | en | 8.465 | 27185 | 177.1762 | 10.3933 | base |
| 23 | Закулисье реальности | 2026 | movie | US | en | 6.8 | 946 | 466.6709 | 10.3921 | base |
| 64 | Новичок | 2018 | tv | US | en | 8.5 | 3362 | 231.9076 | 10.3911 | base |
| 76 | Рик и Морти | 2013 | tv | US | en | 8.679 | 11078 | 170.7749 | 10.3907 | base |
| 115 | Во все тяжкие | 2008 | tv | US | en | 8.947 | 18070 | 129.9362 | 10.3906 | base |
| 63 | Закон и порядок. Специальный корпус | 1999 | tv | US | en | 7.953 | 4277 | 270.275 | 10.3906 | base |
| 68 | Сверхъестественное | 2005 | tv | US | en | 8.311 | 8516 | 207.6063 | 10.3904 | base |
| 71 | Анатомия страсти | 2005 | tv | US | en | 8.209 | 10957 | 204.731 | 10.3899 | base |
| 75 | Пацаны | 2019 | tv | US | en | 8.445 | 13072 | 171.7548 | 10.3893 | base |
| 32 | Проект «Конец света» | 2026 | movie | US | en | 8.676 | 5834 | 164.3082 | 10.3877 | base |
| 69 | Менталист | 2008 | tv | US | en | 8.357 | 4390 | 205.5285 | 10.3876 | base |
| 28 | Майкл | 2026 | movie | US | en | 8.706 | 3362 | 178.3103 | 10.3874 | base |
| 70 | Ранчо Даттонов | 2026 | tv | US | en | 9.3 | 393 | 204.5176 | 10.3864 | base |
| 65 | Укрытие | 2023 | tv | US | en | 8.2 | 2191 | 228.8736 | 10.3858 | base |

### Detailed Discover Requests

1. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=KR`
   - bucket: `KR:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 19 / 1
   - speed/results: 184.4 ms; returned 20 of total 14287; pages 715
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "KR"}`
   - sample: 버려진 청춘 (1982, , 0.0/0); Паразиты (2019, , 8.492/20834); Колония (2026, , 7.134/82)

2. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=US`
   - bucket: `US:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 158.4 ms; returned 20 of total 407512; pages 20376
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Обсессия (2026, , 8.269/2418); История игрушек 5 (2026, , 7.4/534); День разоблачения (2026, , 6.688/833)

3. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=KR&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `KR:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 228.6 ms; returned 20 of total 6740; pages 337
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "KR", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Агент Ким возобновил свою деятельность (2026, KR, 7.386/22); 검사실의 제안 (2026, KR, 5.0/4); Истинное образование (2026, KR, 9.467/629)

4. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 172.9 ms; returned 20 of total 20219; pages 1011
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Извне (2022, US, 8.504/3945); Дом Дракона (2022, US, 8.367/6515); Xplay (2003, US, 8.5/4)

5. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&primary_release_date.lte=2026-07-09&with_origin_country=KR`
   - bucket: `KR:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 11 / 0
   - speed/results: 331.9 ms; returned 20 of total 14287; pages 715
   - params: `{"include_adult": false, "language": "ru-RU", "page": 2, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "KR"}`
   - sample: 귀신과 함께 춤을 (2018, , 6.5/2); 여자 하숙집 2 (2018, , 5.5/6); Гангстер, коп и дьявол (2019, , 7.883/1509)

6. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&primary_release_date.lte=2026-07-09&with_origin_country=US`
   - bucket: `US:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 10 / 0
   - speed/results: 141.6 ms; returned 20 of total 407512; pages 20376
   - params: `{"include_adult": false, "language": "ru-RU", "page": 2, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "US"}`
   - sample: Супергёрл (2026, , 6.217/410); Мумия (2026, , 8.001/2142); Мандалорец и Грогу (2026, , 6.68/562)

7. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&with_origin_country=KR&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `KR:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 10 / 0
   - speed/results: 300.4 ms; returned 20 of total 6740; pages 337
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "KR", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Без остановки (2000, KR, 5.333/6); TMI SHOW (2019, KR, 0.0/0); Стойкий доктор (2026, KR, 7.682/11)

8. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 10 / 0
   - speed/results: 194.4 ms; returned 20 of total 20219; pages 1011
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Тайны Смолвиля (2001, US, 8.192/4503); Флэш (2014, US, 7.756/11655); Йеллоустоун (2018, US, 8.268/3215)


## ru-manual-jp-kr

- Profile: `{"country_selection": {"country_weights": {"JP": 0.5, "KR": 0.5}, "exclude_home_country": false, "home_country": "RU", "max_countries": 2, "mode": "country_pair", "primary_country": "JP", "secondary_country": "KR", "selected_countries": ["JP", "KR"]}, "details_limit": 50, "discover_pages": 3, "exclude_genres": [], "include_genre_mode": "or", "include_genres": [], "max_year": null, "media_preference": "both", "min_year": null, "origin_preference": "foreign", "release_preference": "mixed", "ui_language": "ru", "vibe_preference": "mixed"}`
- Created/pool: 120 / 120
- API requests: 8; unique/total: 8 / 8
- API budget: templates 4; discover HTTP 8; details 0; broad origin 0; fallback used False
- Yield: raw discover 160; duplicates removed 40; accepted/template 30.0; accepted/discover request 15.0
- Duplicate skipped: 0
- Speed: total 2.88s; discover avg 228.9ms; p50 196.9ms; p95 362.4ms; max 362.4ms
- Planned media: `{"movie": 60, "tv": 60}`
- Actual media: `{"movie": 60, "tv": 60}`
- Planned country: `{"JP": 60, "KR": 60}`
- Actual country: `{"JP": 60, "KR": 60}`
- Country hit/leak/wrong: 1.0 / 0.0 / 0
- Fallbacks: `{"base": 120}`; fallback share 0.0
- Avg TMDb score/votes/popularity: 6.7646 / 1496.3667 / 53.1732
- Vibe hit light/dark: 0.6417 / 0.6333
- Junk/garbage: 2 (0.0167) / 47 (0.3917)
- Missing poster/overview: 0 / 45
- TV seasons/episodes present initially: 0/60 and 0/60
- Warnings: `[]`

### Top output sample

| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 40 | Реинкарнация безработного: История о приключениях в другом мире | 2021 | tv | JP | ja | 8.479 | 1552 | 310.3409 | 10.3957 | base |
| 62 | Истинное образование | 2026 | tv | KR | ko | 9.467 | 629 | 134.6042 | 10.3839 | base |
| 42 | Табакошка | 2026 | tv | JP | ja | 8.5 | 10 | 378.8917 | 10.3807 | base |
| 8 | Унесённые призраками | 2001 | movie | JP | ja | 8.535 | 18503 | 36.4351 | 10.379 | base |
| 22 | Паразиты | 2019 | movie | KR | ko | 8.492 | 20834 | 29.8527 | 10.379 | base |
| 51 | МАГИЧЕСКАЯ БИТВА | 2020 | tv | JP | ja | 8.577 | 4523 | 96.9663 | 10.3789 | base |
| 53 | Охотник х Охотник | 2011 | tv | JP | ja | 8.7 | 2133 | 90.8118 | 10.3761 | base |
| 13 | Твоё имя | 2016 | movie | JP | ja | 8.481 | 12673 | 26.8368 | 10.3753 | base |
| 59 | Стальной Алхимик: Братство | 2009 | tv | JP | ja | 8.7 | 2496 | 72.6509 | 10.3743 | base |
| 66 | Игра в кальмара | 2021 | tv | KR | ko | 7.855 | 17510 | 58.5697 | 10.3741 | base |
| 15 | Ходячий замок | 2004 | movie | JP | ja | 8.388 | 11182 | 20.1731 | 10.373 | base |
| 55 | Блич | 2004 | tv | JP | ja | 8.361 | 2163 | 88.1564 | 10.3723 | base |
| 104 | Семья шпиона | 2022 | tv | JP | ja | 8.5 | 2282 | 61.4814 | 10.3703 | base |
| 79 | Принцесса Мононоке | 1997 | movie | JP | ja | 8.321 | 9074 | 15.5402 | 10.3703 | base |
| 39 | Олдбой | 2003 | movie | KR | ko | 8.235 | 9943 | 12.7789 | 10.3697 | base |
| 106 | Фрирен, провожающая в последний путь | 2023 | tv | JP | ja | 8.794 | 873 | 67.1618 | 10.3694 | base |
| 109 | Ранма ½ | 1989 | tv | JP | ja | 8.621 | 1527 | 61.4543 | 10.3692 | base |
| 118 | Гоблин | 2016 | tv | KR | ko | 8.613 | 3100 | 23.9312 | 10.3686 | base |
| 64 | Слабый герой | 2022 | tv | KR | ko | 8.712 | 477 | 69.4267 | 10.3683 | base |
| 30 | Служанка | 2016 | movie | KR | ko | 8.184 | 4368 | 19.5125 | 10.3673 | base |

### Detailed Discover Requests

1. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=JP`
   - bucket: `JP:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 216.1 ms; returned 20 of total 50184; pages 2510
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "JP"}`
   - sample: Истребитель демонов: Бесконечный замок (2025, , 7.726/888); 名探偵コナン ハイウェイの堕天使 (2026, , 8.0/11); まいちゃんの日常 (2014, , 5.167/18)

2. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&primary_release_date.lte=2026-07-09&with_origin_country=KR`
   - bucket: `KR:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 19 / 1
   - speed/results: 162.6 ms; returned 20 of total 14287; pages 715
   - params: `{"include_adult": false, "language": "ru-RU", "page": 1, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "KR"}`
   - sample: 버려진 청춘 (1982, , 0.0/0); Паразиты (2019, , 8.492/20834); Колония (2026, , 7.134/82)

3. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=JP&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `JP:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 202.2 ms; returned 20 of total 13625; pages 682
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "JP", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Реинкарнация безработного: История о приключениях в другом мире (2021, JP, 8.479/1552); Мучайся, Адам (2024, JP, 6.875/36); Табакошка (2026, JP, 8.5/10)

4. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&with_origin_country=KR&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `KR:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 19 / 1
   - speed/results: 182.5 ms; returned 20 of total 6740; pages 337
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "KR", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Агент Ким возобновил свою деятельность (2026, KR, 7.386/22); 검사실의 제안 (2026, KR, 5.0/4); Истинное образование (2026, KR, 9.467/629)

5. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&primary_release_date.lte=2026-07-09&with_origin_country=JP`
   - bucket: `JP:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 10 / 0
   - speed/results: 331.2 ms; returned 20 of total 50184; pages 2510
   - params: `{"include_adult": false, "language": "ru-RU", "page": 2, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "JP"}`
   - sample: Принцесса Мононоке (1997, , 8.321/9074); Подопытная свинка: Эксперимент дьявола (1985, , 4.8/161); Orozco el embalsamador (2001, , 6.3/35)

6. `/discover/movie?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&primary_release_date.lte=2026-07-09&with_origin_country=KR`
   - bucket: `KR:movie:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 11 / 0
   - speed/results: 191.6 ms; returned 20 of total 14287; pages 715
   - params: `{"include_adult": false, "language": "ru-RU", "page": 2, "primary_release_date.lte": "2026-07-09", "sort_by": "popularity.desc", "with_origin_country": "KR"}`
   - sample: 귀신과 함께 춤을 (2018, , 6.5/2); 여자 하숙집 2 (2018, , 5.5/6); Гангстер, коп и дьявол (2019, , 7.883/1509)

7. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&with_origin_country=JP&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `JP:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 10 / 1
   - speed/results: 362.4 ms; returned 20 of total 13625; pages 682
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "JP", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Re:ZERO – Жизнь с нуля в альтернативном мире (2016, JP, 7.982/697); Искренние гетеросексуальные отношения, которые меняют дурнушку (2021, JP, 6.4/25); ぼくとぼくが好きな彼と、君と。 (2024, JP, 0.0/0)

8. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&with_origin_country=KR&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `KR:tv:mixed:mixed:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 11 / 0
   - speed/results: 182.3 ms; returned 20 of total 6740; pages 337
   - params: `{"first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "KR", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Без остановки (2000, KR, 5.333/6); TMI SHOW (2019, KR, 0.0/0); Стойкий доктор (2026, KR, 7.682/11)


## dark-new-tv-us-gb

- Profile: `{"country_selection": {"country_weights": {"GB": 0.5, "US": 0.5}, "exclude_home_country": true, "home_country": "RU", "max_countries": 2, "mode": "preset_foreign", "primary_country": "US", "secondary_country": "GB", "selected_countries": ["US", "GB"]}, "details_limit": 50, "discover_pages": 3, "exclude_genres": [], "include_genre_mode": "or", "include_genres": [], "max_year": null, "media_preference": "tv", "min_year": null, "origin_preference": "foreign", "release_preference": "new", "ui_language": "ru", "vibe_preference": "dark"}`
- Created/pool: 120 / 120
- API requests: 7; unique/total: 7 / 7
- API budget: templates 2; discover HTTP 7; details 0; broad origin 0; fallback used False
- Yield: raw discover 140; duplicates removed 20; accepted/template 60.0; accepted/discover request 17.1429
- Duplicate skipped: 0
- Speed: total 2.34s; discover avg 188.9ms; p50 191.1ms; p95 207.9ms; max 207.9ms
- Planned media: `{"tv": 120}`
- Actual media: `{"tv": 120}`
- Planned country: `{"GB": 60, "US": 60}`
- Actual country: `{"GB": 60, "US": 60}`
- Country hit/leak/wrong: 1.0 / 0.0 / 0
- Fallbacks: `{"base": 120}`; fallback share 0.0
- Avg TMDb score/votes/popularity: 7.6242 / 840.125 / 40.5849
- Vibe hit light/dark: 0.3833 / 0.9167
- Junk/garbage: 0 (0.0) / 3 (0.025)
- Missing poster/overview: 0 / 3
- TV seasons/episodes present initially: 0/120 and 0/120
- Warnings: `[]`

### Top output sample

| Rank | Title | Year | Media | Country | Lang | TMDb | Votes | Popularity | Final | Fallback |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 21 | Извне | 2022 | tv | US | en | 8.504 | 3945 | 422.8659 | 10.6633 | base |
| 22 | Дом Дракона | 2022 | tv | US | en | 8.367 | 6515 | 412.7348 | 10.663 | base |
| 24 | Ранчо Даттонов | 2026 | tv | US | en | 9.3 | 393 | 204.5176 | 10.6471 | base |
| 26 | Вне кампуса | 2026 | tv | US | en | 8.942 | 649 | 155.8569 | 10.6406 | base |
| 23 | Укрытие | 2023 | tv | US | en | 8.2 | 2191 | 228.8736 | 10.6401 | base |
| 25 | Аватар: Легенда об Аанге | 2024 | tv | US | en | 7.8 | 1231 | 190.0948 | 10.6315 | base |
| 32 | Больница Питт | 2025 | tv | US | en | 8.727 | 831 | 76.1387 | 10.629 | base |
| 30 | Люди Икс '97 | 2024 | tv | US | en | 8.586 | 730 | 94.5919 | 10.6271 | base |
| 39 | Уэнздей | 2022 | tv | US | en | 8.342 | 10618 | 49.7687 | 10.6269 | base |
| 77 | Одни из нас | 2023 | tv | US | en | 8.421 | 7108 | 37.8123 | 10.6249 | base |
| 28 | Ричер | 2022 | tv | US | en | 8.1 | 2912 | 93.6796 | 10.6243 | base |
| 66 | Паук-Нуар | 2026 | tv | US | en | 8.457 | 671 | 45.1562 | 10.6229 | base |
| 72 | Отель Хазбин | 2024 | tv | US | en | 8.566 | 1598 | 40.0471 | 10.6226 | base |
| 27 | Большой потенциал | 2024 | tv | US | en | 8.19 | 575 | 94.9453 | 10.6224 | base |
| 29 | Я тебя отыщу | 2026 | tv | US | en | 8.217 | 224 | 91.8228 | 10.6221 | base |
| 35 | Король Талсы | 2022 | tv | US | en | 8.294 | 2679 | 62.219 | 10.622 | base |
| 80 | Рыцарь Семи Королевств | 2026 | tv | US | en | 8.428 | 988 | 35.5484 | 10.6219 | base |
| 2 | Гангстерленд | 2025 | tv | GB | en | 8.346 | 715 | 35.2481 | 10.6214 | base |
| 31 | Медведь | 2022 | tv | US | en | 8.137 | 1796 | 82.0674 | 10.6211 | base |
| 69 | Разделение | 2022 | tv | US | en | 8.398 | 2737 | 44.368 | 10.62 | base |

### Detailed Discover Requests

1. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=GB&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `GB:tv:new_sweep:dark:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 192.1 ms; returned 20 of total 868; pages 44
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "GB", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Медленные лошади (2022, GB, 8.006/882); Гангстерленд (2025, GB,US, 8.346/715); Заключённый (2026, GB, 5.5/23)

2. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=1&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:new_sweep:dark:foreign:any`
   - fallback/status/page: `base` / `ok` / 1
   - accepted/rejected: 20 / 0
   - speed/results: 172.5 ms; returned 20 of total 5136; pages 257
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 1, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Извне (2022, US, 8.504/3945); Дом Дракона (2022, US, 8.367/6515); Укрытие (2023, US, 8.2/2191)

3. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=GB&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `GB:tv:new_sweep:dark:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 20 / 0
   - speed/results: 205.4 ms; returned 20 of total 868; pages 44
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "GB", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Харри Холе (2026, NO,GB,US, 7.3/101); Крукхейвен (2026, GB, 8.778/9); Скотт Пилигрим жмет на газ (2023, JP,GB,US, 7.957/409)

4. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=2&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:new_sweep:dark:foreign:any`
   - fallback/status/page: `base` / `ok` / 2
   - accepted/rejected: 20 / 0
   - speed/results: 185.9 ms; returned 20 of total 5136; pages 257
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 2, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Властелин колец: Кольца Власти (2022, US, 7.2/3759); Целую, Китти (2023, US, 8.099/678); Уидоус-Бэй (2026, US, 8.185/274)

5. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=GB&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `GB:tv:new_sweep:dark:foreign:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 20 / 0
   - speed/results: 167.4 ms; returned 20 of total 868; pages 44
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 3, "sort_by": "popularity.desc", "with_origin_country": "GB", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: The Gold (2023, GB, 7.31/71); Война между сушей и морем (2025, GB, 7.542/177); Турист (2022, GB, 6.751/229)

6. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=3&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:new_sweep:dark:foreign:any`
   - fallback/status/page: `base` / `ok` / 3
   - accepted/rejected: 19 / 1
   - speed/results: 207.9 ms; returned 20 of total 5136; pages 257
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 3, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Andor (2022, US, 8.298/2080); Гангстерленд (2025, GB,US, 8.346/715); «Монарх»: Наследие монстров (2023, US, 7.751/1343)

7. `/discover/tv?include_adult=False&language=ru-RU&sort_by=popularity.desc&page=4&first_air_date.lte=2026-07-09&first_air_date.gte=2022-01-01&with_origin_country=US&without_genres=10766%2C10764%2C10767%2C10763%2C10762%2C99`
   - bucket: `US:tv:new_sweep:dark:foreign:any`
   - fallback/status/page: `base` / `ok` / 4
   - accepted/rejected: 1 / 0
   - speed/results: 191.1 ms; returned 20 of total 5136; pages 257
   - params: `{"first_air_date.gte": "2022-01-01", "first_air_date.lte": "2026-07-09", "include_adult": false, "language": "ru-RU", "page": 4, "sort_by": "popularity.desc", "with_origin_country": "US", "without_genres": "10766,10764,10767,10763,10762,99"}`
   - sample: Третий лишний (2024, US, 7.953/697); Песочный человек (2022, US, 7.865/2635); Лунный рыцарь (2022, US, 7.645/3545)
