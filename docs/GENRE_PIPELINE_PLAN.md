# План: жанры и перенос кандидата в dataset

Дата: 2026-06-23  
Статус: archived draft, частично устарел после перехода candidate pool на TMDb-only flow
Связанные документы: [ADD_RECORD_RULES.md](ADD_RECORD_RULES.md), [candidates/README.md](../candidates/README.md)

Примечание: desktop GUI visual-polish описан отдельно в [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) и не меняет жанровый pipeline, mapper или формат dataset.

## Цель

Сделать цепочку **TMDb → candidate pool → dataset** предсказуемой по жанрам:

- один маппер из внешних жанров в `has_*` модели;
- без тихой потери разметки при переносе из пула;
- явный контракт на границе `add_dataset_record()`.

## Текущая проблема

| Слой | Где | Что ломается |
|------|-----|--------------|
| Пул | `genre_schema.py` | `Mystery` → key `mystery`, label «Детектив» |
| Dataset | `genre_tags.json` | `Mystery` → slug `has_mystery`, которого нет в каталоге → жанр отбрасывается |
| Transfer | `build_genre_defaults()` | unknown жанры игнорируются без предупреждения |
| UX | `mark_candidate_as_watched()` | нет шага `confirm_genres`, как при ручном добавлении |

## Принципы

1. **Не расширять жанровый каталог по ходу transfer-flow** — все внешние жанры маппятся в существующие `has_*` из `config/genre_tags.json`.
2. **Один источник правды для маппинга** — не дублировать правила в pool schema и dataset отдельно.
3. **Форма остаётся обязательной** — автоматического save в dataset не добавляем.
4. **Минимальный diff** — не менять формат `candidate_pool.json` без отдельной миграции.

---

## Фаза 0. Диагностика (без правок логики)

**Срок:** 0.5–1 день  
**Ответственные файлы:** скрипт-отчёт, `docs/`

### Задачи

- [ ] **0.1** Таблица маппинга: TMDb строка → pool `genre_key` → `has_*`.
- [ ] **0.2** Скрипт/отчёт по текущему `candidate_pool.json`:
  - сколько кандидатов с непустыми `genres`;
  - сколько после `build_genre_defaults()` получают все `has_* = 0`;
  - топ unknown жанров.
- [ ] **0.3** Сверка документации с кодом:
  - `docs/add_functions.md` — актуальный TMDb-only candidate build;
  - `docs/ADD_RECORD_RULES.md` — различие pool transfer vs ручное добавление.

### Критерий готовности

Есть численный отчёт и список жанров, которые систематически теряются при transfer.

---

## Фаза 1. Единый маппер жанров (P0)

**Срок:** 1 день  
**Новый модуль:** `dataset/genre_mapping.py` (или секция в `config/genre_tags.py`)

### Задачи

- [ ] **1.1** Явные правила EN → `has_*`:
  - `Mystery` → `has_detective`
  - `Thriller` → `has_thriller`
  - `Crime` → `has_crime`
  - `Drama` → `has_drama`
  - `Comedy` → `has_comedy`
  - `Romance` → `has_romance` или `has_melodrama` (зафиксировать одно правило)
  - `Action`, `Adventure` → `has_action`
  - `Fantasy`, `Sci-Fi`, `Science Fiction` → `has_fantasy`
- [ ] **1.2** Правила RU из `GENRE_NAME_TO_FEATURE` — переиспользовать, не дублировать.
- [ ] **1.3** Правила pool keys (`mystery`, `sci_fi_fantasy`, …) → `has_*`.
- [ ] **1.4** API функции:
  - `map_genre_names_to_features(genres: list[str]) -> dict[str, int]` — полный вектор `has_*`;
  - `split_mapped_genres(genres) -> (mapped, unknown)` — для UI-предупреждений.
- [ ] **1.5** Подключить в `build_genre_defaults()` и `split_known_genres()` (`dataset/title_resolve.py`).
- [ ] **1.6** Тесты в `tests/`:
  - `Mystery` → `has_detective=1`;
  - merged IMDb+TMDb списки;
  - unknown жанр попадает в `unknown`, не в silent drop.

### Критерий готовности

Одинаковый `has_*` для одних и тех же исходных жанров при pool transfer и ручном add-flow.

### Не делать

- Не добавлять новые `has_*` в `genre_tags.json` без отдельной задачи на миграцию жанрового каталога.

---

## Фаза 2. Transfer UX (P1)

**Срок:** 0.5 дня  
**Файлы:** `ui/console/interface_funcs.py`, `ui/console/request.py`

### Задачи

- [ ] **2.1** В `mark_candidate_as_watched()` перед формой показать:
  - `genres` / `genres_tmdb`;
  - результат маппинга в `has_*`;
  - список `unknown` жанров, если есть.
- [ ] **2.2** Предупреждение, если все `has_* = 0` при непустых исходных жанрах.
- [ ] **2.3** (Опционально) Шаг `confirm_or_edit_model_genres()` — как в `request_object(confirm_genres=True)`.
- [ ] **2.4** Сохранить обязательный вызов `request_all_scores()` — без silent save.

### Критерий готовности

Пользователь видит источник и результат жанровой разметки до сохранения в dataset.

---

## Фаза 3. Обогащение жанров при transfer (P2)

**Срок:** 0.5 дня  
**Файлы:** `dataset/title_resolve.py`

### Задачи

- [ ] **3.1** При сборе defaults для pool transfer объединять:
  - `candidate["genres"]`
  - `candidate["genres_tmdb"]`
  (как в `genre_schema.build_genre_keys()`).
- [ ] **3.2** Дедупликация с сохранением порядка.
- [ ] **3.3** Тест: кандидат с пустым `genres`, но непустым `genres_tmdb` — defaults не нулевые.

### Критерий готовности

Transfer не зависит от того, в какое поле попали жанры при build.

---

## Фаза 4. Gates на границах pipeline (P3)

**Срок:** 1 день  
**Файлы:** `candidates/sources/tmdb/importer.py`, `ui/console/interface_funcs.py`, `candidates/sources/tmdb/builder.py`

### Задачи

- [ ] **4.1 Import:** при импорте snapshot повторно проверять `country_score >= 0.40` и TMDb metadata gate — отклонённые помечать или не импортировать (выбрать одну политику и задокументировать).
- [ ] **4.2 Migration:** при `is_pool_candidate_incomplete()` — блокировать save, пока пользователь не заполнит все `raw_scores` в форме, либо явное подтверждение «продолжить с неполными данными».
- [ ] **4.3 Build:** подключить `SERIOUS_GENRES_TMDB` / `WITHOUT_GENRES_TMDB` к Discover **или** удалить мёртвые константы.

### Критерий готовности

В dataset не попадают записи с невалидными scores без явного согласия; import не ослабляет build без пометки.

---

## Фаза 5. Документация и регрессия (P4)

**Срок:** 0.5 дня

### Задачи

- [ ] **5.1** Обновить `docs/ADD_RECORD_RULES.md` — жанровый контракт и pool transfer.
- [ ] **5.2** Обновить `docs/add_functions.md` — актуальный TMDb-only candidate flow.
- [ ] **5.3** Добавить в `candidates/AGENTS.md` ссылку на маппер и запрет смешивать три слоя жанров.
- [ ] **5.4** Прогон:
  ```powershell
  python.exe -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
  python.exe -m pytest
  ```

### Критерий готовности

Документация совпадает с кодом; тесты на маппер и transfer зелёные.

---

## Фаза 6. Мониторинг (опционально, после стабилизации)

**Срок:** по необходимости

### Задачи

- [ ] **6.1** Регулярный отчёт: `scripts/build_tmdb_dataset_genre_report.py` — coverage pool vs dataset.
- [ ] **6.2** Согласовать `scripts/evaluate_candidate_pool.py::SERIOUS_GENRES` с pool keys и `has_*`.
- [ ] **6.3** Отдельная задача: ретро-разметка существующих записей dataset (только с бэкапом).

---

## MVP (минимальный релиз)

Если нужен быстрый результат — только три пункта:

1. Фаза **1** — единый маппер + тесты.
2. Фаза **2.1–2.2** — preview жанров в `mark_candidate_as_watched`.
3. Фаза **5.1** — обновление `ADD_RECORD_RULES.md`.

Остальное — следующий итерационный релиз.

---

## Порядок выполнения

```text
Фаза 0 (диагностика)
    ↓
Фаза 1 (маппер) ──→ Фаза 2 (UX) ──→ Фаза 3 (enrich genres)
    ↓
Фаза 4 (gates)
    ↓
Фаза 5 (docs + tests)
    ↓
Фаза 6 (мониторинг, опционально)
```

---

## Риски

| Риск | Митигация |
|------|-----------|
| Смена маппинга изменит defaults для старых кандидатов | Форма всё равно требует подтверждения пользователя |
| `Romance` vs `has_melodrama` — неоднозначность | Зафиксировать правило в Фазе 1.1, покрыть тестом |
| Расширение `genre_tags.json` «по ходу» | Явный запрет без отдельной миграции жанрового каталога |
| Изменение формата pool JSON | Только через отдельную миграцию и тесты |

---

## Definition of Done (весь план)

- [ ] Единый маппер покрыт тестами и используется в `build_genre_defaults()`.
- [ ] Pool transfer показывает preview жанров и unknown.
- [ ] `Mystery` / `детектив` / pool key `mystery` → `has_detective`.
- [ ] Документация актуальна; `py -m pytest` проходит.
- [ ] Нет silent drop жанров без trace (unknown список или warning).

