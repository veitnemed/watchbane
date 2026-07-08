# Watchbane

Локальный Python-проект для ведения личного списка просмотренных фильмов и сериалов, поиска новых тайтлов, работы с candidate pool и desktop-интерфейсом.

Старая ML-модель и старые ручные тесты сохранены в `archive/legacy/`, но больше не являются активной частью runtime.

## Что умеет проект

- хранить watched/dataset, meta, candidate pool, settings, actions и poster metadata в локальной SQLite-базе;
- добавлять записи через безопасный путь `dataset.storage_movie.add_movie() -> dataset.dataset_records.add_dataset_record()`;
- подтягивать defaults из локальных/внешних источников перед сохранением watched-записи;
- поддерживать жанры, vibe-теги, оценки и постеры;
- открывать desktop PyQt GUI для watched-базы;
- показывать read-only карточку тайтла, постер, метаданные, оценки и аналитику;
- собирать TMDb-only candidate pool;
- импортировать TMDb result в общий candidate pool;
- строить top prediction из общего пула по runtime-фильтрам;
- переносить кандидатов из пула в watched/dataset через форму ручного подтверждения;
- экспортировать watched/add-title карточки через read-only слой `web/`.

## Запуск

Требуется Python 3.13+.

Консольный вход:

```powershell
py start_console.py
```

Desktop GUI:

```powershell
py start_app.py
```

Для TMDb-потока нужен токен:

- переменная окружения `TMDB_TOKEN`;
- или `.env.local`;
- или `tmdb.env`.

Токен не должен попадать в git и в консольный вывод.

## Основные папки

- `app/` - входные сценарии приложения.
- `desktop/` - текущий PyQt desktop GUI.
- `ui/console/` - консольное меню, prompts и UI-оркестрация.
- `dataset/` - записи, meta, Excel, статистика, теги, резолв тайтлов.
- `candidates/` - общий candidate pool и TMDb pipeline.
- `posters/` - poster-cache и загрузка постеров.
- `web/` - read-only экспорт карточек watched/add-title.
- `storage/` - SQLite runtime storage, legacy JSON import/export, backup, файлы, нормализация.
- `apis/` - внешние и локальные источники данных.
- `common/` - чистые утилиты.
- `config/` - константы, схемы, каталоги тегов/жанров.
- `scripts/` - ручные diagnostic/build utilities.
- `assets/desktop/` - desktop assets.
- `tests/` - активный pytest-набор.
- `archive/legacy/` - старые ML/model и прежние ручные тесты.
- `screens/tmp_ui/` - локальные временные UI-скриншоты; содержимое не коммитится.

## Candidate Pool

Общий пул хранится в SQLite (`data/watchbane.sqlite3`). Named pools больше не создаются: TMDb build и import обновляют один pool. Defaults фильтров и параметров сбора хранятся в SQLite criteria (`"pool"`).

Счётчики в UI/console:

- **уникальных** — число кандидатов после нормализации по `title|year`;
- **в storage** — сколько физических записей сохранено, если есть лишние дубли после merge старых пуллов.

Очистка дублей (console: **Поиск сериалов → Управление pool → Очистить дубли в pool**):

- exact-дубли и legacy-ключи;
- похожие названия одного года (остаётся лучшая запись).

TMDb candidate pool:

1. TMDb Discover.
2. TMDb Details.
3. TMDb-only нормализация и scoring.
4. Сохранение отдельного JSON/CSV результата.
5. При необходимости импорт в общий SQLite candidate pool.

CLI-примеры:

```powershell
python scripts/build_candidate_pool.py --country RU --pages 3 --details-limit 50 --mode quality
python scripts/build_candidate_pool.py --country KR --pages 3 --details-limit 50 --mode hidden_gems
```

## Добавление записи

Есть два основных сценария:

1. Ручное добавление из раздела `Данные`.
2. Перенос кандидата из `candidate_pool`.

В обоих случаях запись не добавляется молча. Сначала пользователь получает defaults, затем открывается форма подтверждения и ручного заполнения.

Форма позволяет:

- проверить `title` и `year`;
- выставить `user_score`;
- проверить и поправить `raw_scores`;
- подтвердить или поправить жанры;
- заполнить или изменить vibe-теги.

## Полезные команды

Компиляция активных пакетов:

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
```

Тесты:

```powershell
py -m pytest
```

## Где лежат данные

| Назначение | Путь |
| --- | --- |
| SQLite runtime DB | `data/watchbane.sqlite3` |
| Legacy JSON import/export only | `data/watched/`, `data/candidates/`, `data/settings.json`, `data/cache/posters/posters.json` |
| API log | `data/logs/api_requests.log` |
| Backup | `data/backups/` |
| Excel/export | `data/exports/` |
| Cache | `data/cache/` |

## Документация

- [PROJECT_MAP.md](PROJECT_MAP.md) - карта активных модулей.
- [STRUCTURE_PLAN.md](STRUCTURE_PLAN.md) - план структурной чистки.
- [ARCHITECTURE_TARGET.md](ARCHITECTURE_TARGET.md) - целевая архитектура и правила зависимостей.
- [REFACTORING_CHECKLIST.md](REFACTORING_CHECKLIST.md) - чеклист безопасного завершения структурных правок.
- [DATA_STORAGE_PLAN.md](DATA_STORAGE_PLAN.md) - структура локального хранения данных.
- [add_functions.md](add_functions.md) - правила добавления нового функционала.
- [ADD_RECORD_RULES.md](ADD_RECORD_RULES.md) - контракт добавления/изменения записей.
- [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) - визуальный контракт desktop GUI.
- [DESKTOP_GUI_ROADMAP.md](DESKTOP_GUI_ROADMAP.md) - roadmap desktop GUI.
- [TMDB_ONLY_CANDIDATE_FLOW.md](TMDB_ONLY_CANDIDATE_FLOW.md) - public TMDb-only candidate flow, contract, migration, refresh and scoring.

## Legacy JSON import/export

SQLite is canonical runtime storage. Legacy JSON is explicit compatibility only:

```powershell
py scripts/migrate_json_to_sqlite.py --dry-run
py scripts/migrate_json_to_sqlite.py --apply
py scripts/export_sqlite_to_json.py --output-dir data/exports/legacy-json
```

For recovery, restore a SQLite backup from `data/backups/` first. Legacy JSON
exports are useful for inspection, migration, and compatibility, not as an
active backend.

## Важно

- SQLite candidate pool не должен меняться от runtime-фильтра перед top prediction.
- Обычный top prediction работает только по ready/complete-кандидатам.
- TMDb import и перенос кандидата в dataset - разные шаги.
- Финальное сообщение об успешном добавлении печатает UI-слой, а не storage.
- Legacy model лежит в `archive/legacy/model/` и не импортируется активным runtime.
- Public candidate flow требует только `TMDB_TOKEN`; KP API и локальный IMDb dataset не нужны для candidate pool.
