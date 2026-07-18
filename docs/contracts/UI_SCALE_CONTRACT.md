# Контракт масштаба UI

## Назначение

Watchbane поддерживает пользовательский масштаб интерфейса приложения.

Этот масштаб отделён от масштаба Windows/OS DPI. Поведение Qt high-DPI остаётся обычным/по умолчанию и продолжает использовать нативный device pixel ratio операционной системы.

`QT_SCALE_FACTOR` — не сохраняемая пользовательская настройка Watchbane. Это override Qt high-DPI для тестов/отладки; его нельзя использовать как механизм реализации масштаба UI приложения.

## Настройка

- Имя: `ui_scale`
- Тип: `float`
- По умолчанию: `1.0`
- Минимум: `0.50`
- Максимум: `2.00`

Пресеты:

- `0.50`
- `0.75`
- `0.85`
- `1.0`
- `1.10`
- `1.25`
- `1.35`
- `1.50`
- `1.75`
- `2.00`

## Область действия

`ui_scale` должен влиять на:

- шрифт приложения;
- размеры шрифтов в QSS;
- margins;
- paddings;
- spacing;
- border radii;
- фиксированные размеры виджетов;
- размер главного окна по умолчанию;
- размер постера в detail card;
- кольца рейтинга;
- chips;
- кнопки;
- диалоги.

## Контракт якорных масштабов

### Якоря QA агента в фазе C (обязательны сейчас)

Пока активен блок C в [PRODUCT_ROADMAP_CONTRACT.md](./PRODUCT_ROADMAP_CONTRACT.md), агент и ручная приёмка UI используют **только два** якоря:

- `1.0` — baseline: пропорции, default sizing.
- `1.25` — stress: readability, clipping, overflow.

Не требовать от агента прогоны `0.75` / `1.50` в фазе C.

### Legacy full-matrix (не обязательны в фазе C)

Ранее три значения были mandatory control modes перед architecture refactor:

- `1.0` — baseline.
- `0.75` — compact working mode.
- `1.50` — stress-check.

Они остаются валидными пресетами runtime и могут использоваться в automated tests, но **не** являются обязательным DoD для agent UI-задач фазы C.

Якорные масштабы — не отдельные desktop UI. Это контрольные точки одной UI-системы.

Правила:

- Не добавлять отдельные ветки QSS для отдельных масштабов (`0.75`, `1.0`, `1.25`, `1.50`, …).
- Не делать scale-specific реализации виджетов.
- Одна система design tokens, layout constants и scaling helpers должна работать на всех якорях.
- Проверки якорей должны валидировать свойства usability, а не pixel-perfect геометрию.

Жёсткий контракт:

- минимальные размеры для строк списка, кнопок, карточек и полей ввода;
- min/max ширина и высота там, где они влияют на usability;
- `wordWrap` для длинного описательного текста;
- нет обрезки ключевых подписей и действий;
- нет перекрытия виджетов;
- видимость и состояние collapse/expanded;
- стабильный layout без резких скачков при переключении вкладок или раскрытии контролов;
- новые размеры проходят через scaling helpers или scaled token constants.

Не жёсткий контракт:

- абсолютные координаты каждого виджета;
- точные пиксели каждого margin и padding на каждом масштабе;
- per-scale QSS;
- визуальная идентичность на всех якорях Phase C / legacy.

## Non-goals

- Не масштабировать значения данных.
- Не масштабировать оценки TMDb.
- Не масштабировать JSON-записи.
- Не масштабировать файлы poster cache.
- Не менять поведение API.
- Не использовать absolute positioning для компенсации масштаба.
- Не менять OS DPI awareness.

## Архитектура

- Всё масштабирование идёт через `desktop/theme/scaling.py`.
- Локальная подстройка каналов — в `desktop/theme/ui_tuning.py`.
- Для локальных экспериментов скопируйте `desktop/theme/local_ui_tuning.py.example` в игнорируемый `desktop/theme/local_ui_tuning.py`.
- Размеры layout, margins, spacing, fixed/min/max dimensions и scaled layout constants живут в `desktop/theme/layout.py`.
- `desktop/theme/shell_layout.py` — compatibility facade для shell-sized constants; новые размеры туда не добавлять.
- `desktop/theme/tokens.py` — для цветов, шрифтов, radii и semantic visual names. Существующие layout aliases могут оставаться только для совместимости.
- Композиция профиля detail-card — в `desktop/shared/detail/profiles.py` и должна использовать геометрию `desktop/theme/layout.py` плюс scaling helpers.
- Новые вкладки должны брать margins, spacing и fixed/min/max dimensions из helpers/constants `layout.py`, а не hardcoded px.
- Runtime-виджеты не должны применять собственные случайные множители.
- Hardcoded фиксированные пиксельные размеры запрещены, если нет задокументированной причины usability и записи в test/whitelist.
- Сохраняемая настройка хранится как состояние приложения Watchbane, а не как глобальный Qt DPR override.
- `QT_SCALE_FACTOR` нельзя записывать, читать как настройку приложения или рекомендовать для обычного использования.

## Удалённая вкладка «Информация»

- Вкладка `Информация` / `Information` не входит в активный desktop shell.
- Проверки якорных масштабов не должны включать отдельную вкладку Information.
- Запросы, где упоминаются `Информация`, `Information`, `Analytics tab` или analytics-вкладка главного окна, неоднозначны и должны быть уточнены до реализации.
- Не возвращать эту вкладку, её регистрацию в shell или watched-entry cross-tab wiring без явно уточнённого требования.

## Первая реализация

- Смена масштаба может требовать перезапуска приложения.
- Live apply не требуется.
- Bootstrap один раз загружает настройку и вызывает `desktop.theme.scaling.set_ui_scale(...)`.

## Язык интерфейса

- `interface_language` — настройка приложения для подписей UI, кнопок, сообщений, placeholders и tooltips.
- Перевод интерфейса применяется после перезапуска приложения; ни один якорный масштаб не требует динамического полного retranslate окна.
- `data_language` независим и не должен использоваться проверками UI scale/layout.
- Якорные масштабы должны валидировать переведённый текст UI на wrapping/visibility, а не pixel-perfect координаты.
- Длина текста, зависящая от языка, должна сохранять `wordWrap`, минимальные размеры и видимость ключевых действий стабильными на якорях Phase C `1.0` и `1.25` (legacy full-matrix также проверял `0.75` / `1.50`).
- Не добавлять language-specific или scale-specific QSS для компенсации более длинных переведённых строк.

## Ручной smoke-чеклист

**Phase C (агент):** запускать при `ui_scale=1.0` и `ui_scale=1.25`.

**Legacy full-matrix (опционально):** `ui_scale=0.75`, `1.0`, `1.50`.

- Моё / Watched: sidebar остаётся usable, строки списка watched читаемы, detail card не обрезает ключевой title/rating/action текст.
- Моё / Watched: раскрытые фильтры показывают контролы score/year/genre, действие reset видно, состояние collapse/expand стабильно.
- Фильтры: intro-текст переносится, действия Apply/Reset видны, слайдеры и chip selectors сохраняют usable высоту.
- Кандидаты: панель списка сохраняет usable min/max ширину, строки читаемы, detail placeholder/card переносит длинный текст и не перекрывает список.
- Настройки: слайдер UI scale, label значения, контролы языка, кнопки reset/save и сообщение о перезапуске остаются видимыми и читаемыми.
- Настройки: сообщения restart/reload при смене interface/data language переносятся без обрезки.
- Диалог поиска add-title: поле title, country combo, действие поиска, progress/status текст помещаются в inactive и active состояниях.
- Диалог preview add-title: preview card, warning-текст, поле score и действия confirm/back остаются видимыми без overlap.
- Переключение окон/вкладок не даёт резких скачков layout и панелей нулевого размера.
- Постеры, кольца рейтинга и chips масштабируются через общие tokens/helpers.

## Автоматические guardrails

- `tests/test_ui_scale_settings.py` может по-прежнему параметризовать legacy-якоря `0.75`, `1.0` и `1.50` (код не менялся в docs-pass фазы C).
- Agent DoD для UI-задач использует только якоря Phase C `1.0` и `1.25`.
- Тесты якорей валидируют свойства layout: minimum/maximum sizes, ненулевые размеры, `wordWrap`, visibility и состояние collapse/expanded.
- Тесты якорей не должны assert'ить абсолютные координаты каждого виджета или pixel-perfect margins/padding.
- `test_hardcoded_px_guard_for_direct_sizing_calls` блокирует новые прямые числовые вызовы `setFixedWidth/Height` и `setMinimumWidth/Height`, если они не добавлены в legacy TODO whitelist.
- Новые размеры должны использовать constants и scaling helpers из `desktop/theme/layout.py`.
