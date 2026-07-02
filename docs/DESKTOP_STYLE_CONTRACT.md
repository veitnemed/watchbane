# Desktop Style Contract

Документ фиксирует визуальные и layout-правила PyQt desktop GUI для `Watchbane`. Он относится к watched/search/analytics интерфейсу и не описывает legacy-сценарии из `archive/legacy/`.

## Принципы

- Интерфейс рабочий и плотный, без декоративных hero-блоков.
- Основной пользовательский сценарий должен быть виден сразу: watched list, поиск, карточка.
- Карточки используются для отдельных объектов, не для вложенных секций.
- Text overflow недопустим: длинные названия должны переноситься.
- GUI-polish не меняет dataset, pool, API pipeline и формат JSON.

## Theme Tokens

Основные значения живут в `desktop/theme/tokens.py`; QSS builders — в `desktop/theme/styles/`.

Правила:

- новые цвета, spacing, radius и font-size добавляются через theme tokens;
- hardcoded visual values в widgets не добавляются без причины;
- layout-правки не смешиваются с feature-wiring;
- geometry-значения допустимы рядом с layout-кодом, если это не visual token.

## Палитра

| Назначение | Значение |
| --- | --- |
| App background | `#0f0f10` / `#111113` |
| Surface | `#171719` |
| Elevated surface | `#1c1c1f` |
| Border | `#2a2a2e` |
| Text | `#f4f4f5` |
| Secondary text | `#a1a1aa` |
| Muted text | `#71717a` |
| Accent | `#10a37f` |

Score ring в карточке использует TMDb-only contract: число внутри круга - `tmdb_score`, подпись - `TMDb`, прогресс и цвет обводки - `final_score`. Цветовая шкала идет от красного к янтарному и зеленому.

## Typography

- основной шрифт: `Segoe UI`;
- fallback: `Arial`, `sans-serif`;
- page/section headings: 20-26px;
- обычный текст: 14-16px;
- compact labels: 12-13px;
- letter spacing: 0.

## Watched Layout

Основная карточка watched:

```text
[ poster ] [ title / chips / ratings / actions ]
[ overview full width                      ]
```

Правила:

- poster имеет стабильный размер и не растягивается от текста;
- title переносится и не перекрывает chips/ratings;
- ratings остаются read-only и не показывают legacy IMDb/KP поля;
- блок "Основная информация" показывает `Голоса TMDb`, если они есть в watched/meta/candidate fallback;
- overview идет отдельным full-width блоком ниже верхней строки;
- если overview пустой, блок скрывается;
- card root не должен прыгать по высоте при hover/action states.

## Sidebar

Структура:

```text
[ + add title ]
[ search input ]
[ sort / filters ]
[ counter ]
[ watched list with thumbnails ]
```

Правила:

- sidebar width примерно 300-400px;
- filters collapsible;
- counter показывает `N из M`;
- list item содержит thumbnail, title, year, score;
- selected state должен быть заметным, но спокойным.

## Poster Actions

Read-only actions:

- открыть локальный poster file;
- показать missing/local/remote state;
- не менять poster-cache без отдельного write-сценария.

## Analytics Layout

Analytics read-only.

Порядок секций:

Active Information/Analytics sections:

1. watched genre distribution;
2. candidate pool genre distribution;
3. chart constructor.

Правила:

- `QScrollArea` с `widgetResizable=True`;
- текстовые секции имеют vertical policy `Minimum`;
- Plotly chart живет в отдельном контейнере;
- fallback должен быть полноценным, а не пустым placeholder;
- analytics не пишет dataset/pool/cache.
- chart constructor controls stay compact and use dedicated object names/styles;
- chart constructor supports bar/function rendering and local-only aggregation.

## Search Layout

Search screen должен быть пригоден для повторного использования:

- filters сверху или слева;
- results list плотная, с быстрым сравнением rating/year/genres;
- selected candidate показывает detail preview;
- incomplete status виден сразу;
- action `add to watched` требует confirmation и идет через service.

## Candidate Pool Layout

Read-only состояние:

- criteria list;
- pool stats;
- ready/incomplete counts;
- duplicates/incomplete diagnostics.

Write actions:

- mark watched;
- delete criteria;
- import saved result.

Каждый write требует preview и confirmation dialog.

## Запреты Для GUI-Polish

GUI-polish не должен менять:

- dataset/meta форматы;
- candidate pool форматы;
- API pipeline;
- poster-cache логику;
- console flows;
- generated JSON policy;
- файлы в `archive/legacy/`.

## Visual QA

Перед merge desktop-правок проверить:

| Watched | Search/Analytics |
| --- | --- |
| long title wraps | filters do not resize layout |
| missing poster state | empty results are explicit |
| missing metadata values | incomplete candidates are visible |
| overview hidden when empty | Plotly fallback works |
| sidebar counter stable | text blocks do not overflow |

Минимальные проверки:

```powershell
py -m compileall desktop dataset candidates storage ui tests
py -m pytest tests/test_desktop.py
```
