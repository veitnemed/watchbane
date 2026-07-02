# Правила добавления и изменения функционала

Документ описывает, **куда класть новый код** и **каких зависимостей нельзя нарушать**
при добавлении или изменении функциональности в Watchbane.

Связанные документы:
- [ARCHITECTURE_TARGET.md](ARCHITECTURE_TARGET.md) - слои и правила зависимостей.
- [PROJECT_MAP.md](PROJECT_MAP.md) - где какой код лежит сейчас.
- [ADD_RECORD_RULES.md](ADD_RECORD_RULES.md) - контракт добавления/изменения записей dataset.
- [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) - контракт внешнего вида PyQt desktop GUI.
- [DESKTOP_GUI_ROADMAP.md](DESKTOP_GUI_ROADMAP.md) - что и в каком порядке переносить в PyQt desktop GUI.

## 1. Слои и направление зависимостей

```
common  <-  config  <-  storage  <-  dataset / apis  <-  candidates  <-  ui
```

Импортировать можно только «вниз» по этой схеме. Разрешённые направления:

| Слой | Может импортировать | Нельзя импортировать |
| --- | --- | --- |
| `ui` | dataset, candidates, apis, storage, config, common | — |
| `candidates` | dataset, apis, storage, config, common | ui |
| `dataset` | storage, apis, config, common | ui, candidates |
| `apis` | config, common | ui, dataset, candidates, storage |
| `storage` | config, common | ui, dataset, candidates, apis |
| `config` | common, stdlib | dataset, candidates, apis, ui, storage |
| `common` | stdlib (+ config) | dataset, storage, candidates, apis, ui |

## 2. Жёсткие запреты

1. `ui` не сохраняет dataset/candidate_pool/tags напрямую — только через сервисы.
2. `ui` не вызывает внешние API напрямую — только через сервисы `dataset` / `candidates`.
3. `apis` не пишет в dataset/candidate_pool и не принимает пользовательских решений.
4. `dataset` не импортирует `ui`.
5. `candidates` не вызывает `input()` и `print()` — прогресс отдаётся наверх через reporter.
6. `storage` не содержит пользовательских сценариев (не знает «зачем» сохраняет).
7. `config` и `common` не зависят от верхних слоёв.
8. Никаких compatibility-wrapper при переносах: импорты обновляются сразу и полностью.

## 3. Куда класть новый код

- Новый пункт меню / экран / форма / prompt → `ui/console/` (`global_menu.py`, `interface_funcs.py`, `request.py`, `ui.py`).
- Новый desktop PyQt экран / карточка / dialog → `desktop/`; visual-polish сверять с [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md).
- Новый сценарий над пользовательским dataset (add/update/stats/excel/tags/genre) → `dataset/`.
- Новая логика пулов кандидатов (сбор, фильтры, dedupe, ranking) → `candidates/`.
- Новый внешний или локальный источник данных → `apis/`.
- Новое низкоуровневое чтение/запись файла, backup, init → `storage/`.
- Новая чистая утилита (валидация, формат, нормализация текста) → `common/`.
- Новая константа/путь/схема/каталог тегов или жанров → `config/`.

Если функция совмещает ввод-вывод и логику — **раздели**: интерактив (input/print)
в `ui/console/`, вычисление/сохранение в нижнем слое, UI вызывает сервис и печатает результат.

## 4. Шаблоны типовых задач

### Добавить пункт меню, который что-то делает с данными

1. Логику-сервис положить в нужный слой (`dataset`/`candidates`/`model`), без `print/input`.
2. В `ui/console/interface_funcs.py` добавить UI-функцию: собрать ввод через `ui.console.request`,
   вызвать сервис, напечатать результат.
3. В `ui/console/global_menu.py` (и `ui/console/ui.py` для отрисовки) подключить пункт.

### Добавить/изменить запись dataset

Только через `dataset.storage_movie.add_movie() -> dataset.dataset_records.add_dataset_record()`
и `dataset.dataset_records.update_dataset_record()`. Подробный контракт — в
[ADD_RECORD_RULES.md](ADD_RECORD_RULES.md). UI не пишет в dataset напрямую.

### Сохранить теги / pool

- теги: `dataset.tags_work.add_tag()/delete_tag()/delete_all_tags()`, не `save_tags` из UI;
- candidate pool: `candidates.service` (facade), `candidates.repositories`, `candidates.pool`, `candidates.sources.tmdb`.

### Добавить вызов внешнего API

1. Реализовать запрос в `apis/` — только получение данных.
2. Обернуть в сервис `dataset/title_resolve.py` (или `candidates/`), если нужен UI.
3. UI вызывает сервис, а не `apis` напрямую.

### Прогресс длинной операции в candidates

Не печатать из `candidates`. Использовать `report_progress(source, status)`;
UI/CLI регистрируют печать через `candidates.sources.tmdb.builder.set_progress_reporter(...)`.
Итоговые отчёты возвращать как данные/строки (`build_summary_lines`), печатает их UI/CLI.

### Candidate pool источники

Public candidate flow сейчас TMDb-only. Для новых candidate-функций не добавлять внешнее rating enrichment, старые режимы добора или обязательный локальный rating dataset.

Подробный контракт: [TMDB_ONLY_CANDIDATE_FLOW.md](TMDB_ONLY_CANDIDATE_FLOW.md).

## 5. Чего не делать без отдельного подтверждения

- Менять JSON-форматы `dataset.json`, `meta_data.json`, `candidate_pool.json`, `config/tags.json`.
- Менять структуру меню и тексты пунктов.
- Менять бизнес-логику добавления записей или сбора пула.
- Делать GUI-polish, который меняет dataset/pool или источники данных.
- Удалять старые функции.
- Делать массовые переименования/рефакторинги.
- Трогать или коммитить секреты (`.env.local`, `tmdb.env`, `api_token.py`).
- Вызывать TMDb Details по всем ID подряд без лимита и без skip-gate по сетевым ошибкам.
- Возвращать KP/IMDb enrichment в публичный candidate flow. Candidate pool сейчас TMDb-only.

## 6. Обязательные проверки перед коммитом

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
py main.py   # если затронут UI: убедиться, что меню открывается
```

Активный test suite запускается через `py -m pytest`.

Быстрая проверка слоёв (должно быть пусто):

```powershell
git grep -nE "from ui|import ui" -- "dataset/*.py" "apis/*.py" "storage/*.py"
git grep -nE "\b(print|input)\(" -- "candidates/*.py"
```

## 7. Порядок работы (по правилу проекта)

1. Найти нужные файлы и слой.
2. Кратко описать план и какие файлы изменятся.
3. Внести минимальную правку в правильном слое.
4. Прогнать проверки из раздела 6.
5. Коммитить отдельным маленьким коммитом.

