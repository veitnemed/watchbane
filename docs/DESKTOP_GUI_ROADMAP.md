# План: перенос функционала в PyQt desktop GUI

Дата: 2026-06-25  
Статус: активный план  
Связанные документы: [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md), [ADD_RECORD_RULES.md](ADD_RECORD_RULES.md), [PROJECT_MAP.md](PROJECT_MAP.md), [ARCHITECTURE_TARGET.md](ARCHITECTURE_TARGET.md), [add_functions.md](add_functions.md)

Отчёты по polish: [DESKTOP_GUI_REPORT_2026-06-25.md](reports/DESKTOP_GUI_REPORT_2026-06-25.md), [DESKTOP_GUI_REPORT_2026-06-25_layout-polish.md](reports/DESKTOP_GUI_REPORT_2026-06-25_layout-polish.md)

Примечание: визуальный и layout-контракт desktop GUI описан в [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md). Этот документ фиксирует **что и в каком порядке** переносить в GUI, не дублируя правила компоновки.

## Цель

PyQt desktop — **основная оболочка** для повседневной работы с watched-базой, аналитикой и (позже) рекомендациями.

Консоль — **админка и fallback**: сложные импорты, обучение, pool build, массовые операции, отладка.

## Архитектурный каркас

```
PyQt widget (desktop/*)
  → desktop helper / dialog
    → dataset/* | candidates/service | model reports
      → storage / JSON / cache
```

Жёсткое правило: GUI **не пишет JSON напрямую**. Write только через documented services:

- `dataset/dataset_records.py` — add/update записи;
- `dataset/delete_record.py` — удаление watched;
- `candidates/service.py` — candidate pool и top prediction.

Подробнее: [add_functions.md](add_functions.md), [PROJECT_MAP.md](PROJECT_MAP.md).

## Текущее состояние

| Область | Файлы | Статус |
| --- | --- | --- |
| Watched list + карточка | [desktop/watched_view.py](../desktop/watched_view.py), [desktop/app.py](../desktop/app.py) | done |
| Редактирование `user_score` | `app.py` → `update_dataset_record` | done |
| Analytics KPI / dense / insights | [desktop/analytics_view.py](../desktop/analytics_view.py) | done |
| Bar «Распределение оценок» | `analytics_view.py` + [desktop/plotly_charts.py](../desktop/plotly_charts.py) + [dataset/score_analytics.py](../dataset/score_analytics.py) (`chart_distribution`) | done |
| Layout-контракт | [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) | done |

---

## Этап 1. Polish базового GUI

**Цель:** стабильный внешний вид, без новой бизнес-логики.  
**Файлы:** `desktop/watched_view.py`, `desktop/analytics_view.py`, `desktop/plotly_charts.py`, `desktop/app.py`

### Задачи

- [ ] **1.1** Visual QA watched card: короткий title, длинный title (2–3 строки), без IMDb/КП, без постера — overview сразу под info, нет пустот.
- [ ] **1.2** Polish левой панели списка: spacing, selected item, пустой поиск.
- [ ] **1.3** Plotly bar «Распределение оценок»: высота, отступы, стиль под `#analyticsSection`.
- [ ] **1.4** Мелкие визуальные правки analytics (KPI, dense, «Коротко») — через именованные константы `ANALYTICS_*`.

### Критерий готовности

Три крайних кейса из [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) проходят вручную; layout не ломается при resize.

### Не делать на этом этапе

Новые write, новые вкладки, pool, training.

---

## Этап 2. Read-only расширения

### 2.1 Watched (только отображение)

- [x] **2.1.1** Фильтр по диапазону `user_score` — done (`desktop.watched_view.filter_entries_by_user_score`, UI min/max в watched left panel).
- [x] **2.1.2** Фильтр по году — done (`desktop.watched_view.filter_entries_by_year`, UI `year_from/year_to` в watched left panel).
- [x] **2.1.3** Фильтр по жанру — done (`desktop.watched_view.get_available_genres`, `filter_entries_by_genre`, UI genre combo в watched left panel).
- [ ] **2.1.4** Счётчик «найдено N» в status bar.
- [ ] **2.1.5** Быстрый сброс фильтров.

Данные: `load_watched_entries()` + filter/sort, без записи.

### 2.2 Analytics (графики по одному)

Pipeline для **каждого** нового графика:

1. расчёт в [dataset/score_analytics.py](../dataset/score_analytics.py);
2. HTML в [desktop/plotly_charts.py](../desktop/plotly_charts.py);
3. секция в [desktop/analytics_view.py](../desktop/analytics_view.py) + Qt-fallback;
4. smoke в [tests_pytest/test_desktop.py](../tests_pytest/test_desktop.py).

Порядок добавления:

- [ ] **2.2.1** ~~Распределение по корзинам~~ — done (`chart_distribution`).
- [ ] **2.2.2** Мои оценки по годам (bar/line).
- [ ] **2.2.3** Средняя оценка по годам.
- [ ] **2.2.4** Моя vs IMDb (scatter или bar).
- [ ] **2.2.5** Опционально: моя vs КП.

### Критерий готовности

Каждый график работает с Plotly/WebEngine и с Qt-fallback; analytics read-only — не трогает weights, `model_metrics`, pool, dataset (кроме чтения).

---

## Этап 3. Безопасные write в watched

### Задачи

- [x] **3.0** UI-stub будущего добавления watched-тайтла — done (`+ Добавить тайтл` показывает заглушку, без записи данных).
- [ ] **3.1** Удаление записи — **первый новый write** в GUI:
  - ПКМ → «Удалить запись»;
  - preview dialog через `build_watched_delete_preview()` ([dataset/delete_record.py](../dataset/delete_record.py));
  - подтверждение (например, ввод `DELETE`);
  - `delete_watched_record()` — удаление dataset/meta + poster cache (как в [ui/console/interface_funcs.py](../ui/console/interface_funcs.py));
  - обновить list + card.
- [ ] **3.2** Read-only сервисные пункты (опционально): «Открыть локальный постер», «Показать путь poster-cache».

### Тесты

[tests_pytest/test_delete_watched_record.py](../tests_pytest/test_delete_watched_record.py) — уже покрывает service; добавить wiring-тест GUI при реализации.

### Не делать на этом этапе

Полный редактор записи (title, genres, raw_scores).

### Критерий готовности

Delete проходит тот же service path, что и консоль; cancel не трогает данные.

---

## Этап 4. Вкладка «Модель» (read-only)

**Отдельная вкладка**, без обучения и save.

| Блок | Источник |
| --- | --- |
| LOO MAE summary | `config/model_metrics.json`, train reports |
| IMDb / KP baseline | report helpers из `model/` |
| Feature ablation | [ui/console/train_menu.py](../ui/console/train_menu.py) / model diagnostics |
| Top errors | read-only report |

### Задачи

- [ ] **4.1** Вкладка «Модель» с read-only summary из `model_metrics`.
- [ ] **4.2** Кнопка «Посчитать» → фоновый поток + progress (не блокировать UI).
- [ ] **4.3** Результат — текст/таблица; **ничего не сохранять**.

### Не делать

«Обучить модель», save weights, auto-update metrics.

---

## Этап 5. «Рекомендации» (read-only top prediction)

- [ ] **5.1** Вкладка → выбор `criteria_name`.
- [ ] **5.2** [candidates/service.py](../candidates/service.py) `get_global_top_prediction_view()` — единственный источник ranking (как в console ~1638 `interface_funcs.py`).
- [ ] **5.3** Фильтры (runtime, ready/incomplete) через service.
- [ ] **5.4** Карточки кандидатов read-only.

### Не делать

Пересбор pool, import TMDb, retry KP, правка `candidate_criteria.json`. Ranking не дублировать в `desktop/`.

---

## Этап 6. Candidate pool в GUI

### Read-only (сначала)

- [ ] **6.1** Список criteria.
- [ ] **6.2** Stats (raw/watched/active/ready/incomplete).
- [ ] **6.3** Просмотр кандидатов, фильтр incomplete.

### Write (позже, с confirmation dialogs)

- mark watched;
- retry KP;
- delete criteria;
- import saved TMDb result.

### Оставить в консоли

TMDb build, массовые операции, сложный import.

---

## Этап 7. Постеры и metadata

### Read-only (сначала)

- [ ] **7.1** Диагностика: сколько постеров local / missing / без description.

### Позже

- update metadata;
- download missing posters.

Отдельный риск-этап: сеть, TMDb, SSL.

---

## Этап 8. Роль консоли

Консоль **не удалять**. Навсегда остаётся для:

- Excel import/export;
- LOO training / weights;
- rating comparison / drafts;
- TMDb pool build;
- backup/restore;
- отладки.

---

## Ближайшие 8 шагов

| # | Шаг | Этап |
| --- | --- | --- |
| 1 | Visual QA + polish watched/analytics | 1 |
| 2 | Plotly bar: высота/стиль под секцию | 1 |
| 3 | Polish watched list (left panel) | 1 |
| 4 | График «оценки по годам» | 2 |
| 5 | GUI delete watched | 3 |
| 6 | Structure-тесты на новые wiring | — |
| 7 | Вкладка «Модель» read-only summary | 4 |
| 8 | Вкладка «Рекомендации» read-only top-N | 5 |

---

## Чеклист перед GUI-PR

- [ ] Нет прямой записи JSON из PyQt.
- [ ] Write идёт через documented service + `source_name`.
- [ ] Layout/size policy по [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md).
- [ ] Spacing/fonts через именованные константы в `analytics_view.py`.
- [ ] Три крайних кейса вручную (см. style contract).
- [ ] `tests_pytest/test_desktop.py` (+ smoke для plotly при графиках).
- [ ] Не тронуты: training, pool build, weights без отдельного этапа.

## Что не трогать без отдельного решения

- формат dataset / meta;
- автообучение после правки оценки;
- TMDb/KP pipeline, poster cache logic;
- `candidate_pool` write из GUI на ранних этапах;
- web GUI;
- console flows (кроме reuse helpers).
