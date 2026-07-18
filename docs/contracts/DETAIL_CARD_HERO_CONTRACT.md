# Контракт hero detail card

Документ задаёт строгий визуальный и layout-контракт кинематографической detail card в desktop GUI.

## 1. Общий layout

- Detail view — одна тёмная кинематографическая hero card с objectName `detailHeroCard`.
- Верхняя область — двухколоночный layout:
  - фиксированная колонка постера слева;
  - правая info-колонка справа.
- Порядок правой info-колонки:
  1. title block: title, затем compact title meta;
  2. genre chips;
  3. score summary;
  4. main info panel.
- Блоки overview и additional-info начинаются ниже всей верхней строки.
- Hero frame может занимать всю ширину detail panel.
- Блок `detailContentContainer` центрируется по горизонтали внутри hero frame.
- Title, chips, score summary, main info, overview и additional info остаются выровненными по левому краю относительно границ content block.
- Absolute positioning запрещён.
- Negative margins запрещены.
- Фиксированная высота правой колонки, которая может обрезать main info panel, запрещена.
- Если title, chips, score summary или main info требуют больше высоты, layout должен расти естественно.

## 2. Постер

- Колонка постера имеет фиксированный логический размер постера около `360x530` до пользовательского `ui_scale`.
- Постер рендерится внутри poster shell со скруглёнными углами.
- Изображение постера использует поведение cover-crop.
- Изображение постера никогда не должно искажаться.
- Размер постера независим от высоты title, chips, score summary и main info.
- Состояние missing-poster должно сохранять тот же размер poster shell.

## 3. Candidate actions

- `candidateMarkWatchedButton` и `candidateHideButton` должны быть под постером.
- Candidate actions никогда не должны появляться перед title.
- Candidate actions никогда не должны размещаться в строке score summary.
- Candidate actions не должны менять размер постера.

## 4. Title meta

- Текст title живёт в `detailTitle`.
- Title meta живёт в `detailTitleMeta`, сразу под title.
- Формат title meta компактный: `2020 • 2 сезона / 20 серий`.
- Отсутствующий год или отсутствующие сезоны/серии просто убирают соответствующую часть.
- Title meta не должен дублироваться в main info.
- Title meta не должен рендериться как chips.

## 5. Chips

- Вход для chips — только жанры.
- Year chips запрещены.
- Chips могут занимать не более 2 строк.
- Третья строка chips запрещена.
- Если жанры не помещаются в лимит 2 строк, показать компактный overflow chip `+N`.
- Если chips переносятся на вторую строку, score summary, main info и overview сдвигаются вниз через обычный layout flow.
- Chips не должны перекрывать title, score summary, main info или overview.

## 6. Score summary

- Строка score кандидата содержит:
  - TMDb ring;
  - звёзды final_score.
- Строка score watched содержит:
  - TMDb ring;
  - звёзды final_score.
- Отдельное кольцо «моя оценка» запрещено.
- Score summary не должен содержать кнопки candidate actions.
- Score summary не должен использовать сырые поля рейтинга KP/IMDb.

## 7. TMDb ring

- Отображаемое значение кольца — `tmdb_score`, отформатированный до одного знака после запятой.
- Подпись кольца — `TMDb`.
- Прогресс кольца — `tmdb_score / 10`.
- Цвет кольца основан на прогрессе `tmdb_score` в cyan/teal палитре темы.
- `final_score` не должен влиять на значение, прогресс или цвет TMDb ring.
- Число внутри круга использует обычный цвет текста, не rating yellow.
- Footer-текст под кольцом запрещён.
- Значения `footer_label` вроде `Итог 75` запрещены.
- Если `tmdb_score` отсутствует, TMDb ring может быть скрыт или показывать явный empty state, но не должен использовать `final_score` как fallback.

## 8. final_score

- `final_score` виден только как звёзды.
- Опциональный качественный текст разрешён, например `Отличный рейтинг`.
- Сырой числовой текст вроде `Итог 75` в hero card запрещён.
- Сырой percent, сырой `final_score` и скрытый debug score text запрещены.
- Звёзды final_score не должны менять выравнивание TMDb ring.

## 9. Watched user_score

- `user_score` показывается только как poster overlay badge.
- Badge появляется в верхнем правом углу постера.
- Формат badge: `★ 9.0`.
- Badge скрыт, когда `user_score` отсутствует.
- Badge не должен влиять на размер постера.
- Badge не должен влиять на layout правой колонки.
- Не показывать `Моя оценка: 9.0` рядом с title.
- Не показывать watched user score как ring.

## 10. Main info

- Текст заголовка main info — `ОСНОВНАЯ ИНФОРМАЦИЯ`.
- Main info рендерится как rounded glass panel.
- Строки используют структуру `label/value`.
- Main info содержит type, country, watch providers и TMDb votes.
- Год и сезоны/серии — это title meta, не строки main-info.
- Watch providers всегда рендерятся в main info; при отсутствии использовать `нет данных`.
- TMDb votes рендерятся в main info, когда значение положительное.
- Main info не должен обрезаться после переноса title.
- Main info не должен обрезаться после переноса chips.
- Main info не должен зависеть от высоты постера.
- Пустые optional values не должны создавать пустые строки.

## 11. Overview

- Overview начинается ниже верхней строки.
- У overview есть divider.
- Содержимое overview начинается от левого края content hero card.
- Overview скрыт, когда текст overview пустой.
- Overview не должен перекрывать постер, правую колонку или main info panel.
- Overview должен расти естественно вместе с перенесённым текстом.

## 12. Additional info

- Текст заголовка additional info — `ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ`.
- Additional info использует ту же систему panel/grid, что и main info.
- Строки могут включать status и episode runtime.
- Пустые optional values не должны создавать пустые строки.
- Additional info должен иметь видимый верхний отступ от содержимого overview.

## Non-goals

- Этот контракт не меняет runtime-форматы данных.
- Этот контракт не меняет логику миграции TMDb/KP/IMDb.
- Этот контракт не меняет поведение скачивания poster-cache.
- Этот контракт не меняет candidate ranking или scoring.
