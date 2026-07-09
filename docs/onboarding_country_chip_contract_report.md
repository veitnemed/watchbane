# Onboarding Country Chip Contract Report

Дата: 2026-07-09

## Что изменилось

- Стартовый выбор стран больше не preset-список `foreign / mixed / any`.
- Первый taste-шаг теперь показывает 5 отдельных country chips:
  - США
  - Россия
  - Великобритания
  - Южная Корея
  - Япония
- Чипы работают как multi-select: можно выбрать любую комбинацию от 1 до 5 стран.
- По умолчанию выбран только `US`, чтобы пустой выбор не превращался в "все страны".
- В profile contract теперь уходит явный список:
  - `country_selection.selected_countries`
  - `country_selection.country_weights`
  - `country_selection.mode`
  - `country_selection.max_countries`
- Для нового UI веса стран равные. Примеры:
  - `["US"]` -> `US: 120`
  - `["US", "GB"]` -> `US: 60, GB: 60`
  - `["US", "RU", "GB"]` -> `US: 40, RU: 40, GB: 40`
  - `["US", "RU", "GB", "KR", "JP"]` -> по 24 кандидата на страну
- Старые backend fallback-presets сохранены для совместимости старых профилей.

## Проверки UI

Скриншоты созданы и визуально просмотрены:

- `screens/tmp_ui/onboarding/country_chips_75.png`
- `screens/tmp_ui/onboarding/country_chips_100.png`
- `screens/tmp_ui/onboarding/country_chips_150.png`
- `screens/tmp_ui/onboarding/country_chips_plan_100.png`

Параметры screenshot smoke:

- platform plugin: `windows`
- font probe: `family_count=355`, `Segoe UI=True`, `Arial=True`
- scale: `0.75`, `1.0`, `1.5`

Итог визуальной проверки:

- country chips читаются на 0.75 / 1.0 / 1.5;
- текст не обрезается;
- выбранный `US` виден сразу;
- кнопка `Далее` остаётся доступной при выбранной стране;
- subtitle теперь говорит, что можно выбрать одну или несколько стран.

## Автотесты

Запущены проверки:

- `py -m compileall desktop tests scripts candidates`
- `py -m pytest tests\test_onboarding_autofill.py`
- `py -m pytest`

Итог полного pytest:

- `929 passed`
- `1 skipped`

Новые/обновлённые проверки покрывают:

- первый вопрос onboarding теперь `country_selection`;
- country chips не exclusive;
- стартовое значение: `US`;
- UI-клики могут выбрать несколько стран;
- все 31 комбинация из 5 стран строит валидный `country_selection`;
- план квот всегда суммируется в 120;
- план показывает локализованные названия стран, а не ISO-коды.

## Mock Quality Run

Команда:

```powershell
py scripts\run_onboarding_pool_rebuild.py --mock --all --output screens/tmp_ui/onboarding/country_chips_mock_report.md --json-output screens/tmp_ui/onboarding/country_chips_mock_report.json
```

Результат по всем 14 mock-сценариям:

- minimum `country_hit_rate`: `1.0`
- `requests_without_country`: `0`
- `duplicate_requests_observed`: `0`
- предупреждений по новым country-chip сценариям: нет

Новые сценарии:

| Scenario | Created | Plan | Actual | Hit rate |
| --- | ---: | --- | --- | ---: |
| `ru-countries-us-only` | 120 | `US: 120` | `US: 120` | 1.0 |
| `ru-countries-ru-only` | 120 | `RU: 120` | `RU: 120` | 1.0 |
| `ru-countries-us-ru-gb` | 120 | `US/RU/GB: 40 each` | `US/RU/GB: 40 each` | 1.0 |
| `ru-countries-all-five` | 120 | `US/RU/GB/KR/JP: 24 each` | `US/RU/GB/KR/JP: 24 each` | 1.0 |

## Live Quality Smoke

Команда запускалась отдельно по новым сценариям с `--live --require-live`.

| Scenario | Created | Country actual | Hit rate | Requests without country | Warning |
| --- | ---: | --- | ---: | ---: | --- |
| `ru-countries-us-only` | 120 | `US: 120` | 1.0 | 0 | нет |
| `ru-countries-ru-only` | 19 | `RU: 19` | 1.0 | 0 | сильный недобор RU |
| `ru-countries-us-ru-gb` | 95 | `US: 40, GB: 40, RU: 15` | 1.0 | 0 | недобор RU |
| `ru-countries-all-five` | 113 | `US: 24, GB: 24, KR: 24, JP: 24, RU: 17` | 1.0 | 0 | недобор RU |

Вывод:

- Новый контракт корректно держит выбранные страны: hit rate 1.0, wrong country 0.
- Запросы не теряют `with_origin_country`.
- `US`, `GB`, `KR`, `JP` закрываются нормально.
- Строгий RU-only и RU-heavy mix на live TMDb недобирают пул, потому что при `with_origin_country=RU` доступной выдачи меньше, чем целевые 120.
- Это не ломает contract: приложение сохраняет предупреждения и может открыть кандидатов с частичным пулом.

## Оставшийся риск

RU-only теперь доступен как явный chip-комбинационный выбор. Live smoke показывает, что этот сценарий может собрать мало кандидатов. Если нужно гарантировать полный пул для RU-heavy выбора, следующая отдельная задача должна быть не UI polish, а policy-задача:

- разрешать country-relax fallback после исчерпания строгого RU;
- или заранее предупреждать пользователя, что RU-only может быть коротким;
- или уменьшать целевой размер стартового пула для RU-only.
