# ARCHITECTURE_TARGET — целевая структура проекта

Документ фиксирует **целевую** структуру папок Terminal Movies Learn и правила
зависимостей между слоями.

> Статус: **ДОСТИГНУТО**. Рефакторинг выполнен: структура и направление зависимостей
> ниже соответствуют текущему коду. Реальную раскладку файлов по папкам см. в
> [PROJECT_MAP.md](PROJECT_MAP.md); правила добавления функционала — в
> [add_functions.md](add_functions.md). Разделы 4–5 ниже оставлены как история
> миграции (какой старый модуль куда переехал).

Проект: **Terminal Movies Learn** — консольная Python-программа для личной модели
вкуса по фильмам/сериалам.

---

## 1. Целевая структура папок

```
recommended/
│
├─ main.py
│
├─ config/        # настройки, пути, схемы, теги, жанры, секреты, feature catalog
├─ common/        # чистые утилиты: validation, normalize, formatting, text match
├─ storage/       # низкоуровневое файловое хранилище: json, atomic save, backup, paths
├─ dataset/       # пользовательский dataset: records, meta, excel, stats, rename
├─ candidates/    # candidate_pool, TMDb pool, dedupe, filters, retry KP, ranking
├─ model/         # features, predict, metrics (MAE/KP_MAE/IMDb_MAE), LOO, training, weights
├─ apis/          # внешние источники: KP API, TMDb API, IMDb SQL, api logging, retry
├─ ui/            # интерфейсные слои
│  ├─ console/    # текущий консольный UI: input/print, меню, формы, маршрутизация
│  └─ gui/        # место под будущий GUI
├─ tests/         # тесты проекта, regression, тесты архитектурных правил
└─ docs/          # архитектурные документы, карты, roadmap, заметки рефакторинга
```

Порядок слоёв снизу вверх (нижние ничего не знают о верхних):

```
common  <-  config  <-  storage  <-  dataset / apis  <-  candidates / model  <-  ui/console
```

(`common` — самый нижний; `ui/console` — текущий верхний оркестратор консольного интерфейса.)

---

## 2. Зоны ответственности, запреты и кандидаты на переезд

### 2.1 `config/`

**Отвечает за:** настройки проекта, пути, схемы, теги, жанры, constants,
secrets / local API keys loader, feature catalogs.

**Запрещено:**
- импортировать `dataset` / `data_work` / `candidates` / `model` / `ui` / `apis`;
- читать/писать `dataset.json`;
- читать/писать `candidate_pool.json`;
- делать API-запросы;
- вызывать `input()` / `print()` как UI-сценарий.

**Правило:** config — нижний слой. Он не зависит от пользовательских данных и
бизнес-сценариев.

**Текущие файлы, которые относятся сюда:**
- `config/constant.py`
- `config/scheme.py`
- `config/tags.json`
- `config/tags_work.py` *(после Шага 1 — чистый каталог тегов)*
- `config/genre_tags.json`
- `config/genre_tags.py`

---

### 2.2 `common/`

**Отвечает за:** чистые общие функции — validation, normalization, formatting,
text matching, small helpers.

**Будущие файлы:**
- `common/validation.py`
- `common/normalize.py`
- `common/formatting.py`
- `common/text_match.py`

**Запрещено:**
- импортировать `dataset` / `storage` / `candidates` / `model` / `apis` / `ui`;
- работать с файлами;
- делать API-запросы;
- читать `dataset`;
- читать `candidate_pool`;
- вызывать `input()` / `print()`.

**Правило:** common — чистый нижний слой, тестируется без файлов проекта.

**Текущие файлы, которые относятся сюда:**
- `core/valid.py` *(после Шага 2 — без зависимости от storage)*
- `core/format_score.py`
- функции нормализации title/genre/text, если они не зависят от storage/dataset/API
  (сейчас часть такой логики живёт в `data_work/storage_normalize.py` — переедет
  только чистая её часть).

---

### 2.3 `storage/`

**Отвечает за:** низкоуровневое файловое хранение — `load_json`, `save_json`,
atomic save, backup, создание папок, paths, init files.

**Будущие файлы:**
- `storage/json_storage.py`
- `storage/paths.py`
- `storage/backup.py`
- `storage/files.py`

**Запрещено:**
- пользовательские сценарии («добавить фильм», «собрать пулл», «обучить модель»);
- `input()` / `print()` как UI.

**Правило:** storage знает, *как* сохранить файл, но не решает, *зачем*.

**Текущие файлы, которые относятся сюда:**
- `data_work/storage_files.py`
- `data_work/storage_data.py` — **только** низкоуровневая часть чтения/записи;
- backup-логика (часть `data_work/tags_work.py` / прочих backup-функций).

---

### 2.4 `dataset/`

**Отвечает за:** пользовательский dataset, meta, add/update/rename records, Excel,
dataset stats, genre/tag updates в пользовательских данных.

**Будущие файлы:**
- `dataset/records.py`
- `dataset/meta.py`
- `dataset/excel.py`
- `dataset/rename.py`
- `dataset/stats.py`
- `dataset/genre_import.py`
- `dataset/tags_service.py`

**Запрещено:**
- `input()` / `print()`;
- прямые API-запросы из UI-сценариев;
- логика `candidate_pool`;
- обучение модели.

**Правило:** dataset управляет тем, что пользователь **уже** посмотрел и оценил.

**Текущие файлы, которые относятся сюда:**
- `data_work/dataset_records.py`
- `data_work/storage_movie.py`
- `data_work/excel_work.py`
- `data_work/storage_data.py` — частично (сценарии над dataset/meta);
- `data_work/dataset_stats.py`
- `data_work/genre_import.py`
- `data_work/tags_work.py` — **только** мутационная часть (add/delete/backup тегов).

---

### 2.5 `candidates/`

**Отвечает за:** candidate_pool, TMDb pool, импорт TMDb result в общий пул, dedupe,
filters, incomplete candidates, retry KP, top candidates, перенос кандидата в
dataset через сервисы.

**Будущие файлы:**
- `candidates/pool.py`
- `candidates/tmdb_pool.py`
- `candidates/import_tmdb.py`
- `candidates/filters.py`
- `candidates/dedupe.py`
- `candidates/retry_kp.py`
- `candidates/ranking.py`
- `candidates/criteria.py`

**Запрещено:**
- `input()`;
- `print()` как основной сценарий;
- прямое сохранение dataset без dataset-service;
- обучение модели;
- UI-меню.

**Правило:** candidates управляет тем, что пользователь **может** посмотреть, но
ещё не добавил в dataset.

**Текущие файлы, которые относятся сюда:**
- `data_work/candidate_pool.py`
- `data_work/tmdb_candidate_pool.py`
- candidate-логика из `interface/interface_funcs.py` — **без** UI;
- части `build_candidate_pool.py` / `evaluate_candidate_pool.py`, не являющиеся
  чисто CLI-обёртками.

---

### 2.6 `model/`

**Отвечает за:** features, predict, metrics, MAE, KP_MAE, IMDb_MAE, LOO, training,
weights, reports.

**Будущие файлы:**
- `model/features.py`
- `model/predict.py`
- `model/metrics.py`
- `model/loo.py`
- `model/training.py`
- `model/training_linear.py`
- `model/weights.py`
- `model/reports.py`

**Запрещено:**
- импортировать `ui` / `interface`;
- `input()`;
- UI print-сценарии;
- меню;
- прямое изменение dataset/candidate_pool.

**Правило:** model считает, обучает и прогнозирует. Он не знает, как пользователь
нажимает пункты меню.

**Текущие файлы, которые относятся сюда:**
- `model_work/model.py`
- `model_work/linear_regression_train.py`
- `model_work/train_report.py`
- `model_work/noise_experiment.py`
- `model_work/train_modes.py` — **без** UI/input.

> Замечание по текущему долгу: сейчас `model_work/linear_regression_train.py` и
> `model_work/train_modes.py` импортируют `interface`. Это нарушает правило
> «model не импортирует ui» и будет развязано отдельным шагом.

---

### 2.7 `apis/`

**Отвечает за:** внешние источники — KP API, TMDb API, IMDb SQL, API logging, retry,
timeout, raw external data.

**Будущие файлы:**
- `apis/kp_api.py`
- `apis/tmdb_api.py`
- `apis/imdb_sql.py`
- `apis/api_log.py`

**Запрещено:**
- сохранять dataset;
- сохранять candidate_pool;
- вызывать `input()` / `print()` как UI;
- обучать модель;
- принимать пользовательские решения.

**Правило:** apis только получает внешние данные и возвращает результат наверх.

**Текущие файлы, которые относятся сюда:**
- `integrations/api.py`
- `integrations/api_tmdb.py`
- `data_work/sql_search.py`
- secrets-loader `api_token.py` остаётся вне VCS; токен читает `config`-слой, сами
  запросы — `apis`.

---

### 2.8 `ui/`

**Отвечает за:** интерфейсные слои приложения.

**Текущая структура:**
- `ui/console/` - текущий консольный интерфейс: меню, input, print, confirmations,
  формы, красивый вывод, маршрутизация пользовательских действий.
- `ui/gui/` - место под будущий GUI.

**Запрещено:**
- прямое сохранение dataset/candidate_pool;
- прямые API-запросы;
- сложный matching;
- feature building;
- обучение модели;
- бизнес-логика candidate_pool.

**Правило:** `ui/console` спрашивает пользователя и показывает результат. Работу делают
`dataset` / `candidates` / `model` / `apis`.

**Текущие файлы, которые относятся сюда:**
- `ui/console/console_app.py`
- `ui/console/ui.py`
- `ui/console/request.py`
- `ui/console/global_menu.py`
- `ui/console/interface_funcs.py` — **только** UI/оркестрация;
- `ui/console/candidate_pool_ui.py`
- `ui/console/tags_menu.py`
- `ui/console/backup_menu.py`
- `ui/console/menu_state.py`, `ui/console/title_presenters.py`.

---

### 2.9 `tests/`

**Отвечает за:** тесты проекта, regression checks, тесты архитектурных правил
(если будут добавлены). Точка входа — `tests/test.py`.

### 2.10 `docs/`

**Отвечает за:** архитектурные документы, карты проекта, правила добавления записей,
roadmap, notes для рефакторинга. Этот файл живёт здесь.

---

## 3. Разрешённые зависимости слоёв

Стрелка `A → B` означает «`A` может импортировать `B`». Импорт в обратную сторону
запрещён.

```
ui/console  → dataset, candidates, model, apis, storage, config, common
ui/gui      → пока не используется
dataset     → storage, config, common
candidates  → dataset, model, apis, storage, config, common
model       → config, common, storage (только чтобы читать weights); НЕ ui/console или ui/gui
apis        → config, common; НЕ dataset / candidates / ui/console / ui/gui / model
storage     → config, common
config      → common или stdlib only; НЕ dataset/candidates/model/apis/ui/storage
common      → stdlib only (очень нижние безопасные зависимости); НЕ верхние слои
```

### Главные архитектурные запреты

1. `ui/console` не сохраняет dataset/candidate_pool напрямую.
2. `ui/console` не вызывает API напрямую.
3. `apis` не пишут в dataset/candidate_pool.
4. Нижние слои не импортируют `ui/console` или `ui/gui`.
5. `model` не импортирует `ui`.
6. `common` не импортирует dataset/storage/candidates/model/apis/ui.
7. `config` не импортирует dataset/candidates/model/apis/ui/storage.
8. `candidates` не вызывает `input()` / `print()`.
9. `storage` не содержит пользовательские сценарии.
9. `dataset` не содержит меню.
10. `integrations` / `apis` не принимают пользовательские решения.

---

## 4. Соответствие текущих папок целевым

Целевая структура заменяет текущие «рабочие» папки. Переименование/переезд —
постепенный, отдельными шагами.

| Текущая папка   | Куда уходит (целевые зоны)                              | Судьба            |
|-----------------|--------------------------------------------------------|-------------------|
| `core/`         | `common/`                                              | переименование    |
| `integrations/` | `apis/`                                                | переименование    |
| `interface/`    | `ui/`                                                  | переименование    |
| `model_work/`   | `model/`                                               | переименование    |
| `data_work/`    | `storage/` + `dataset/` + `candidates/` + `apis/`      | **разделение**    |
| `config/`       | `config/` (+ чистые helpers в `common/`)               | остаётся          |
| `tests/`        | `tests/`                                               | остаётся          |
| `docs/`         | `docs/`                                                | остаётся          |

`data_work/` — единственная папка, которая не переименовывается, а **раскладывается**
по нескольким зонам:
- `storage_files.py`, низкоуровневое чтение/запись из `storage_data.py` → `storage/`;
- `dataset_records.py`, `storage_movie.py`, `excel_work.py`, `dataset_stats.py`,
  `genre_import.py`, мутации тегов из `tags_work.py`, сценарии над dataset из
  `storage_data.py` → `dataset/`;
- `candidate_pool.py`, `tmdb_candidate_pool.py` → `candidates/`;
- `sql_search.py` → `apis/`.

---

## 5. Текущие папки, которые исчезнут или переименуются

- `data_work/` — **исчезает как единая папка**, разделяется на `storage/`,
  `dataset/`, `candidates/` и `apis/` (часть `sql_search.py`).
- `model_work/` — **переименуется** в `model/`.
- `interface/` — **переименуется** в `ui/`.
- `integrations/` — **переименуется** в `apis/`.
- `core/` — **переименуется** в `common/` (см. раздел 6).

---

## 6. Почему `common/`, а не `core/`

- `core` в Python-экосистеме часто означает «ядро/движок бизнес-логики». Здесь же
  слой содержит только **бесстатусные утилиты** (validation, normalize, formatting,
  text match), без какой-либо доменной логики — название `common` точнее передаёт
  «общие переиспользуемые helpers».
- `common` визуально и семантически в одном ряду с `config`/`storage`/`dataset` —
  все они звучат как «зоны», а `core` выбивается и создаёт ложное ощущение
  центральности/важности.
- Снижается риск, что в `core` со временем «накидают» бизнес-логику (эффект имени).
  `common` явно сигналит: сюда только чистые мелкие функции.
- Имя свободно от текущего модуля `core/` и его истории, что упрощает чистый
  переезд `core/ → common/` без двусмысленности.

---

## 7. Первый безопасный шаг переноса (после фиксации документа)

**Предложение:** начать с самого нижнего и наименее связанного слоя — переименовать
`core/ → common/`.

Почему именно он первым:
- `core/` после Шага 2 уже **чистый** (импортирует только `config.constant`),
  поэтому риск минимальный;
- у него мало входящих рёбер по сравнению с `data_work/`;
- это переименование, а не разделение, — механически проще и безопаснее.

Как сделать безопасно (поэтапно, без изменения поведения):
1. Создать пакет `common/` и перенести `core/valid.py`, `core/format_score.py`.
2. Обновить импорты `from core import ...` → `from common import ...` во всех
   потребителях.
3. На переходный период допустимо оставить тонкий re-export `core/` → `common/`,
   **но** правило задачи запрещает compatibility wrappers, поэтому импорты
   обновляются сразу и полностью, а старая папка удаляется тем же шагом.
4. Прогон проверок:
   ```powershell
   py -m compileall common config data_work interface model_work tests
   py tests\test.py
   ```

Дальнейшие шаги (ориентир, не часть первого шага): `integrations/ → apis/`,
`interface/ → ui/`, `model_work/ → model/`, и в самом конце — самое сложное:
разделение `data_work/` на `storage` / `dataset` / `candidates`.

---

## 8. Статус выполнения

Рефакторинг завершён по шагам, без изменения поведения, JSON-форматов и меню:

- `core/ → common/`, `integrations/ → apis/` (+ `kp_api`/`tmdb_api`/`imdb_sql`),
  `interface/ → ui/`, `model_work/ → model/`;
- выделены пакеты `candidates/`, `storage/`, `dataset/`; `data_work/` удалён;
- разорваны грязные зависимости: `model ≠> ui`, `dataset ≠> ui`, UI не вызывает API
  и не сохраняет данные напрямую, `candidates` не использует `print()/input()`.

Актуальная раскладка файлов — в [PROJECT_MAP.md](PROJECT_MAP.md).
