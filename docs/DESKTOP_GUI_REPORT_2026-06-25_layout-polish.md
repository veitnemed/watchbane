# Отчёт: desktop GUI layout-polish после коммита ea9cd74

Базовый коммит: `ea9cd74 Polish desktop watched card style`.

## Цель сессии

Убрать «плавающий» layout (описание уезжает вниз, analytics растягивается на viewport), выровнять блоки вкладки «Аналитика», зафиксировать layout-правила в документации и вынести spacing/типографику analytics в именованные константы.

## Watched: карточка выбранного тайтла

Файл: `desktop/watched_view.py`

### Исправления layout

- Убран `addStretch()` в info-колонке — пустота больше не копится под рейтингами.
- Title: снят жёсткий `maximumHeight(70)`, включён `wordWrap` + `QSizePolicy.Minimum` — длинные названия не обрезаются.
- Info-колонка обёрнута в `_info_column_widget` для измерения высоты контента.
- Постер подстраивается под высоту info (`min(330px, measured height)`), пересчёт через `heightForWidth` и `_measure_info_column_height`.
- `_overview_frame` и карточка: vertical size policy `Minimum`.
- Один `root.addStretch(1)` **в конце** карточки — лишняя высота scroll уходит вниз, не между info и «Описание».
- `resizeEvent` на карточке только планирует sync через `QTimer.singleShot`.

### Поведение

- Save pipeline, контекстное меню, read-only карточка — без изменений.
- Dataset/model/candidate_pool не трогались.

## Analytics: вкладка «Аналитика»

Файл: `desktop/analytics_view.py`

### KPI (Всего / Средняя / …)

- Фиксированный размер карточки `124×80`.
- Подпись и значение по центру, без stretch «вниз».
- Значение **26px**, подпись **13px**.

### «Одинаковые оценки»

- Оценка в badge `#denseScoreBadge` **56×56**, число **22px**, по центру badge.
- Badge `AlignVCenter` в строке; справа «N тайтлов» + список тайтлов.

### «Коротко» и общая типографика

- Insights **14px**, цвет `#d4d4d8`; spacing между строками **4px**.
- Заголовки секций **16px**; базовый текст вкладки **14px**.
- Отступы root/секций/KPI/dense уменьшены (root 14/10, section 10/6 и т.д.).

### Scroll / viewport

- Read-only блоки не растягиваются на высоту viewport.
- `addStretch(1)` в конце root analytics — пустота под контентом, не внутри серых карточек.

### Шаг B: константы

- В начале `analytics_view.py`: блоки `ANALYTICS_FONT_*`, `ANALYTICS_*_MARGIN/SPACING/PADDING`, размеры виджетов.
- К каждой константе — комментарий на русском: за какой элемент UI отвечает.
- QSS собирается через `_build_analytics_style()` из font-констант.

## Документация

Файл: `docs/DESKTOP_STYLE_CONTRACT.md`

- Добавлена секция **Layout-контракт**: watched, analytics scroll, KPI, dense scores, insights.
- Обновлён блок «Где менять» и чеклист ручной проверки (3 крайних кейса watched + analytics).

## Что не входило в коммит

- `config/model_metrics.json` — побочный `is_stale` после правки оценки через desktop GUI; не часть GUI-polish.
- `desktop_image/icons/*` — untracked logo assets, не в style contract.
- Plotly HTML, dataset, model, console UI — без изменений.

## Изменённые файлы

- `desktop/watched_view.py`
- `desktop/analytics_view.py`
- `docs/DESKTOP_STYLE_CONTRACT.md`
- `docs/DESKTOP_GUI_REPORT_2026-06-25_layout-polish.md` (этот отчёт)

## Проверки

```powershell
python -m pytest tests_pytest/test_desktop.py tests_pytest/test_score_analytics.py
```

Рекомендуется вручную: watched (короткий/длинный title), analytics (KPI, «Коротко», «Одинаковые оценки», график или fallback).
