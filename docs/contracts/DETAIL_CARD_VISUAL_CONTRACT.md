# Визуальный контракт detail card Watchbane

Статус: строгий UI-контракт для `desktop/shared/detail/*` и связанных desktop-тестов.

Контракт существует потому, что detail card уже успела пройти через несколько несовместимых состояний. Будущие агенты должны считать этот файл источником правды до изменения layout карточки, score rings, звёзд или candidate actions.

## 1. Область действия

Контракт применяется к PyQt detail card, используемой в:

- detail view библиотеки watched;
- detail/preview view кандидата;
- add-title preview, когда он переиспользует те же shared detail-card компоненты.

Он не разрешает менять JSON-форматы dataset, JSON-форматы candidate pool, TMDb API flows, хранение poster cache, формулы scoring, скрипты metadata refresh, console flows или файлы в `archive/legacy/`.

## 2. Основная визуальная модель

У карточки одна фиксированная колонка постера и одна гибкая информационная колонка.

```text
[ poster column ]   [ information column ]
[ poster        ]   [ title                ]
[ candidate     ]   [ title meta           ]
[ actions only  ]   [ genre pills           ]
                  [ TMDb ring + stars     ]
                  [ main information     ]

[ overview full-width below both columns ]
[ additional information below overview ]
```

Строка title должна содержать только title. Title meta (`year • seasons / episodes`) — компактная строка сразу под title. Candidate actions никогда не должны размещаться перед title или внутри строки title.

## 3. Семантика rating и score

В detail card три отдельных визуальных сигнала. Их нельзя смешивать.

| Визуальный элемент | Поле-источник | Смысл | Допустимое отображение |
| --- | --- | --- | --- |
| TMDb circle | `tmdb_score` | Внешний публичный рейтинг TMDb, 0..10 | Число внутри круга, подпись `TMDb`, progress кольца, cyan/teal цвет кольца |
| User score badge | `user_score` | Собственная оценка пользователя, 0..10 | Только poster overlay badge `★ 9.0` |
| Final stars | `final_score` | Внутренний recommendation/result score | Только шкала 1..5 звёзд, без числового текста `Итог 75` |

Жёсткое правило: `final_score` никогда не должен управлять progress TMDb circle, цветом TMDb circle или числом внутри TMDb circle.

Жёсткое правило: `tmdb_score` никогда не должен описываться как `Итог`.

Жёсткое правило: `quality_score` — внутренний scoring-сигнал и не должен появляться в этой detail card, пока будущая задача явно не попросит diagnostics/debug view.

## 4. Контракт TMDb circle

TMDb circle — круг публичного рейтинга.

Обязательное поведение:

- display value: отформатированный `tmdb_score` с одним знаком после запятой, или `—` при отсутствии;
- label: точно `TMDb`;
- progress: `clamp(float(tmdb_score) / 10, 0, 1)`, или `0` при отсутствии/невалидности;
- color: выводится из `tmdb_score`, не из `final_score`, в текущем диапазоне cyan/teal темы;
- value color: обычный цвет текста, не rating yellow;
- footer text: нет;
- watched user score не должен появляться как второе кольцо.

Примеры регрессий:

```python
card = {"tmdb_score": 8.0, "final_score": 0.20}
# TMDb circle must look strong: progress 0.80, cyan/teal high-score color.
# It must not look like 20%.

card = {"tmdb_score": 4.0, "final_score": 0.90}
# TMDb circle must look weak/medium by TMDb: progress 0.40.
# It must not change because final_score is high.
```

## 5. Контракт user score badge

Оценка пользователя — poster overlay badge, не круг.

Обязательное поведение:

- display value: отформатированный `user_score` с одним знаком после запятой;
- text format: `★ 9.0`;
- location: top-right poster overlay;
- missing/invalid value: скрыть badge;
- badge не должен влиять на размер постера;
- badge не должен влиять на layout правой колонки.

Показ watched user score как круга, текста в title-row, строки main-info или элемента score-summary запрещён.

## 6. Контракт звёзд final score

`final_score` показывается как звёзды, а не как число под кругом.

Обязательное поведение:

- source: только `final_score`;
- accepted source scale: либо `0..1`, либо `0..100`;
- normalization: значения выше `1` трактуются как percent и делятся на `100`;
- visual scale: 1..5 звёзд, half-star шаги разрешены;
- missing/invalid value: скрыть звёзды или показать тихий placeholder, но зарезервировать достаточно вертикального места, чтобы круги оставались выровненными;
- нет текста `Итог 75`, `Итог —`, `final_score` или сырого percent под кругами;
- звёзды — отдельный widget/row, не footer внутри `RatingCircleIndicator`.
- подпись над звёздами в карточке watched film/series — точно `WatchBane`.

Рекомендуемый mapping:

```python
normalized = normalize_final_score(final_score)  # 0..1
stars = round(normalized * 10) / 2               # half-star scale
stars = max(1.0, min(5.0, stars))                # 1..5 when present
```

Примеры:

```python
final_score = 0.74  # 3.5 or 4.0 stars depending on rounding policy, but never text "Итог 74".
final_score = 86    # normalized to 0.86, shown as stars only.
```

Виджет звёзд не должен расширять ни один слот rating circle. Он не должен сдвигать TMDb circle по горизонтали.

## 7. Layout блока rating

Блок rating имеет слот TMDb ring и звёзды final-score:

```text
[ fixed TMDb slot ][ gap ][ final-score stars ]
```

Обязательное поведение layout:

- TMDb ring сохраняет фиксированный слот;
- звёзды final-score — отдельный виджет рядом с кольцом;
- звёзды final-score сохраняют фиксированный горизонтальный gap от слота TMDb, когда main information свёрнута или раскрыта;
- ширина звёзд не должна влиять на value/progress TMDb ring;
- отсутствующие звёзды не должны заставлять кольцо прыгать по вертикали;
- candidate actions никогда не попадают в эту score row.

Запрещённые паттерны реализации:

- добавление текста звёзд как `footer_label` в `RatingCircleIndicator`;
- размещение звёзд внутри виджета TMDb circle;
- увеличение ширины TMDb widget, чтобы вписать звёзды;
- использование временного модуля `tuning.py` как финального committed состояния.

## 8. Кнопки candidate actions

Candidate actions — это poster actions, не title actions.

Обязательное поведение:

- кнопки `candidateMarkWatchedButton` и `candidateHideButton` появляются только когда candidate profile их включает;
- они размещаются под постером в колонке постера;
- они центрируются или выравниваются влево согласованно под постером, не перед title;
- строка title остаётся стабильной и начинается с label title;
- watched view эти кнопки не показывает.

Размер кнопок может оставаться текущим compact size, но строка должна быть визуально отделена от title.

## 9. Main information и overview

Detail card не должна жертвовать контентом ради того, чтобы верхняя строка оставалась той же высоты, что и постер.

Обязательное поведение:

- `Основная информация` остаётся видимой, когда в ней есть элементы;
- длинные значения переносятся вместо обрезки;
- информационная колонка не должна иметь maximum height, равный высоте постера;
- overview — full-width блок ниже верхней строки poster/info;
- пустой overview скрывает блок overview.

## 10. Media badge фильм/сериал

Media-type badge постера — solid pill поверх постера, не translucent text.

Обязательное поведение:

- text: локализованный uppercase `ФИЛЬМ` или `СЕРИАЛ`;
- location: bottom-center poster overlay;
- fill: непрозрачная тёмная заливка film palette; вариант series использует series badge background token;
- border: cyan/series border token из film palette;
- text color: film/series badge text token;
- должен оставаться читаемым поверх светлых и тёмных постеров при UI scale 75%, 100% и 150%.

Строки main information:

- `Тип` из нормализованного `object_type` или TV-shape fallback;
- `Страна` из `country`, когда присутствует;
- `Где смотреть` из watch providers, или `нет данных` при отсутствии;
- `Голоса TMDb` из `tmdb_votes`, когда значение положительное.

Title meta:

- `Год` показывается под title, не в main information;
- `Сезоны / серии` показываются под title, не в main information.

Строки additional information:

- status;
- episode runtime.

## 10. Границы владения кодом

Ожидаемые файлы для UI-изменений:

- `desktop/shared/detail/card.py` — структура layout и размещение виджетов;
- `desktop/shared/detail/rating_indicator.py` — только circular rating widget;
- `desktop/shared/detail/card_pills.py` — helpers создания/заполнения для rating/meta widgets;
- `desktop/shared/detail/presenters.py` — чистые formatting/payload builders;
- `desktop/shared/detail/profiles.py` — sizing constants/profile values;
- `desktop/theme/*` — shared visual tokens, только когда действительно нужно;
- `tests/test_desktop.py` и/или `tests/desktop/*` — regression-тесты поведения контракта.

Не менять формулы scoring ради визуального запроса. Визуальный слой потребляет score fields; он их не переопределяет.

## 11. Обязательные regression-тесты

Как минимум тесты должны покрывать эти случаи:

```python
def test_tmdb_ring_uses_tmdb_score_not_final_score():
    item = build_score_ring_item({"tmdb_score": 8.0, "final_score": 0.20})
    assert item["display_value"] == "8.0"
    assert item["display_label"] == "TMDb"
    assert item["ring_progress"] == 0.80
    assert item.get("footer_label") in (None, "")


def test_tmdb_ring_color_uses_tmdb_score_not_final_score():
    high_tmdb_low_final = build_score_ring_item({"tmdb_score": 8.0, "final_score": 0.20})
    low_tmdb_high_final = build_score_ring_item({"tmdb_score": 4.0, "final_score": 0.90})
    assert high_tmdb_low_final["accent"] != low_tmdb_high_final["accent"]


def test_final_score_is_stars_not_ring_footer():
    tmdb_item = build_score_ring_item({"tmdb_score": 7.4, "final_score": 0.74})
    stars_item = build_final_score_star_item({"final_score": 0.74})
    assert tmdb_item.get("footer_label") in (None, "")
    assert stars_item is not None
    assert stars_item["kind"] == "final_stars"


def test_watched_user_score_is_badge_not_ring(qapp):
    # user_score must be rendered as detailUserScoreBadge only.
    # It must not create a second score ring in the score summary row.
    ...


def test_title_meta_is_under_title_not_main_info(qapp):
    # year and seasons/episodes must live in detailTitleMeta.
    # Main information must not duplicate them as rows.
    ...


def test_candidate_actions_are_not_in_title_row(qapp):
    # candidateMarkWatchedButton and candidateHideButton must be descendants
    # of the poster/actions column, not of detailTitleActions/title row.
    ...
```

Если существующие тесты всё ещё assert'ят `ring_progress == final_score` или `footer_label == "Итог 74"`, эти тесты сохраняют старый баг и должны быть переписаны.

## 12. Инструкции агенту для будущей UI-работы

Перед изменением detail card агент должен указать, какой инвариант он затрагивает и какие инварианты не трогает.

Допустимая форма ответа для implementation-задачи:

1. Определить текущие нарушения контракта.
2. Изменить минимальное число файлов.
3. Обновить тесты так, чтобы они assert'или контракт, а не предыдущий баг.
4. Запустить `py -m compileall desktop tests` и релевантные desktop-тесты.
5. Отчитаться о точных изменённых файлах и точных проверках контракта, которые удовлетворены.

Агент должен остановиться и объяснить, прежде чем делать любое изменение, которое затронет форматы данных, формулы scoring, поведение TMDb refresh или поведение poster cache.
