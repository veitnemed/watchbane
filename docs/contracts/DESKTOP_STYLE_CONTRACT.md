# Desktop Style Contract

Документ фиксирует визуальные и layout-правила PyQt desktop GUI для `Watchbane`. Он относится к watched/search/settings интерфейсу и не описывает legacy-сценарии из `archive/legacy/`.

## Принципы

- Интерфейс рабочий и плотный, без декоративных hero-блоков.
- Основной пользовательский сценарий должен быть виден сразу: watched list, поиск, карточка.
- Карточки используются для отдельных объектов, не для вложенных секций.
- Text overflow недопустим: длинные названия должны переноситься.
- GUI-polish не меняет dataset, pool, API pipeline и формат JSON.

## Theme Tokens

Цвета, шрифты, радиусы и семантические visual names живут в `desktop/theme/tokens.py`.
Spacing, margins, min/max sizes и scaled layout constants живут в `desktop/theme/layout.py`.
QSS builders — в `desktop/theme/styles/`.
Правила пользовательского масштаба UI описаны в [UI_SCALE_CONTRACT.md](UI_SCALE_CONTRACT.md).

Правила:

- новые цвета, radius и font-size добавляются через theme tokens;
- новые spacing/margins/min/max/fixed dimensions добавляются через `theme/layout.py` и scaling helpers;
- hardcoded visual values в widgets не добавляются без причины;
- layout-правки не смешиваются с feature-wiring;
- geometry-значения допустимы рядом с layout-кодом, если это не visual token.

## Палитра

| Назначение | Значение |
| --- | --- |
| App background | `#050B16` |
| Surface | `#07101D` |
| Card | `#0D1726` |
| Elevated surface | `#111D2E` / `#142238` |
| Border | `#1D2B40` |
| Text | `#F5F7FB` |
| Secondary text | `#B8C2D3` |
| Muted text | `#78879B` |
| Accent | `#0EA5D8` |
| Accent hover / teal | `#22D3C5` |
| Rating / stars | `#F5B82E` |

Detail-card правила зафиксированы в отдельном строгом контракте: [DETAIL_CARD_HERO_CONTRACT.md](DETAIL_CARD_HERO_CONTRACT.md). Если правила ниже конфликтуют с hero-contract, главным считается hero-contract.

Score ring в карточке использует TMDb-only contract: число внутри круга - `tmdb_score`, подпись - `TMDb`, прогресс - `tmdb_score / 10`. Цвет обводки находится в cyan/teal палитре темы. `final_score` не влияет на круг и показывается только отдельной строкой звезд. Жёлтый используется только для рейтинговых звёзд и score badge, не для section headers.

## Typography

- основной шрифт: `Segoe UI`;
- fallback: `Arial`, `sans-serif`;
- page/section headings: 20-26px;
- обычный текст: 14-16px;
- compact labels: 12-13px;
- letter spacing: 0.

## Watched Layout

Основная карточка watched/candidate должна следовать [DETAIL_CARD_HERO_CONTRACT.md](DETAIL_CARD_HERO_CONTRACT.md). Краткая схема:

```text
[ poster ] [ title / chips / score summary / main info ]
[ overview full width                      ]
```

Правила:

- poster имеет стабильный размер и не растягивается от текста;
- title переносится и не перекрывает title meta/chips/ratings;
- под title отображается компактная meta-строка вида `2020 • 2 сезона / 20 серий`;
- genre chips показывают только жанры, год не должен попадать в chips;
- ratings остаются read-only и не показывают legacy IMDb/KP поля;
- watched user score показывается только как poster overlay badge `heart + 1..3`, не как ring и не как длинный текстовый label;
- candidate actions находятся под poster и никогда не появляются перед title;
- блок "Основная информация" показывает тип и страну; год и сезоны/серии находятся под title;
- блок "Дополнительная информация" показывает providers/status/runtime/TMDb votes, если эти поля есть;
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

- sidebar width примерно 260-340px;
- filters collapsible;
- counter показывает `N из M`;
- list item содержит thumbnail, title, year, score;
- selected state должен быть заметным, но спокойным.

## Poster Actions

Read-only actions:

- открыть локальный poster file;
- показать missing/local/remote state;
- не менять poster-cache без отдельного write-сценария.

## Removed Information Layout

Вкладка `Информация` / `Information` удалена из активного desktop shell.

Правила:

- не добавлять `Information`/analytics tab в `build_main_tabs()` без уточненного нового требования;
- не добавлять watched-entry cross-tab wiring для removed analytics tab;
- если задача упоминает `Информация`, `Information`, `Analytics tab` или analytics как вкладку главного окна, сначала уточнить сценарий;
- внутренние analytics helpers не считаются активным экраном desktop GUI.

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

| Watched | Search/Settings |
| --- | --- |
| long title wraps | filters do not resize layout |
| missing poster state | empty results are explicit |
| missing metadata values | incomplete candidates are visible |
| overview hidden when empty | settings controls stay readable |
| sidebar counter stable | text blocks do not overflow |

Минимальные проверки:

```powershell
py -m compileall desktop dataset candidates storage ui tests
py -m pytest tests/test_desktop.py
```

Для layout/scaling-правок также снимаются и открываются screenshots на application scale `0.75`, `1.0` и `1.5`; временные PNG хранятся в `screens/tmp_ui/` и не коммитятся.
