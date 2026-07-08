# Onboarding Scenario Pool Report

Date: 2026-07-08

Runtime: isolated temp SQLite databases under `.pytest-tmp/onboarding_scenarios/`.

Token policy: live TMDb calls were used; credentials were not printed.

## Scenario 1: RU Balanced

Answers:

- Language: `ru`
- Media: `both`
- Release: `mixed`
- Vibe: `mixed`
- Origin: `mixed`

Plan:

- Target: 120 candidates
- Search buckets: 32
- Media quota: movie 60, tv 60
- Release quota: classic 36, new 36, top all-time 48
- Vibe quota: light 60, dark 60
- Origin quota: domestic 60, foreign 60

Result:

- OK: true
- Created: 120
- Pool size: 120
- API requests: 22
- Warning: none
- Actual media: movie 60, tv 60
- Source: onboarding_autofill 120
- Top languages: en 67, ko 20, ja 20, fr 5, ru 4, it 2

First saved candidates:

- Истинное образование (2026, tv)
- Гоблин (2016, tv)
- Алхимия душ (2022, tv)
- Любовь приходит с неба (2019, tv)
- Отель «Дель Луна» (2019, tv)
- Винченцо (2021, tv)
- Алые сердца: Корё (2016, tv)
- Королева Чхорин (2020, tv)

## Scenario 2: RU Domestic Movie Classic Light

Answers:

- Language: `ru`
- Media: `movie`
- Release: `classic`
- Vibe: `light`
- Origin: `domestic`

Plan:

- Target: 120 candidates
- Search buckets: 23
- Media quota: movie 84, tv 36
- Release quota: classic 72, top all-time 48
- Vibe quota: light 84, dark 36
- Origin quota: domestic 84, foreign 36

Result:

- OK: true
- Created: 120
- Pool size: 120
- API requests: 18
- Warning: none
- Actual media: movie 82, tv 38
- Source: onboarding_autofill 120
- Top languages: en 66, ja 20, de 12, ko 9, fr 6, it 4

First saved candidates:

- 9 рота (2005, movie)
- Лучше, чем люди (2018, tv)
- Маша и Медведь (2009, tv)
- Хроники Нарнии: Лев, Колдунья и Волшебный Шкаф (2005, movie)
- Гарри Поттер и Кубок огня (2005, movie)
- Труп невесты (2005, movie)
- Царство небесное (2005, movie)
- Гордость и предубеждение (2005, movie)

Observation: the actual split is close to the planned 84/36 media target, but not exact after TMDb availability, watched/dataset overlap, and duplicate filtering.

## Scenario 3: EN TV New Dark

Answers:

- Language: `en`
- Media: `tv`
- Release: `new`
- Vibe: `dark`
- Origin: skipped for non-RU UI

Plan:

- Target: 120 candidates
- Search buckets: 8
- Media quota: movie 36, tv 84
- Release quota: new 84, top all-time 36
- Vibe quota: light 36, dark 84
- Origin quota: any 120

Result:

- OK: true
- Created: 120
- Pool size: 120
- API requests: 9
- Warning: none
- Actual media: movie 59, tv 61
- Source: onboarding_autofill 120
- Top languages: en 82, ja 19, ko 8, it 2, es 2, zu 1

First saved candidates:

- Dutton Ranch (2026, tv)
- The Polygamist (2026, tv)
- Off Campus (2026, tv)
- Teach You a Lesson (2026, tv)
- I Will Find You (2026, tv)
- Spider-Noir (2026, tv)
- Widow's Bay (2026, tv)
- Marshals (2026, tv)

Observation: the planned tv-heavy quota was not preserved in the final saved pool. The candidate builder reached 120 items, but fallback/availability made movie entries overrepresented. This is not a UI failure, but it is a recommendation-quality risk worth a focused follow-up if exact media quotas become a product contract.
