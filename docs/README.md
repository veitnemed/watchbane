# Series List

Локальный Python-проект для ведения личного списка просмотренных фильмов и сериалов, поиска новых тайтлов, работы с candidate pool и desktop-интерфейсом.

Старая ML-модель и старые ручные тесты сохранены в `archive/legacy/`, но больше не являются активной частью runtime.

## Что умеет проект

- хранить watched/dataset и meta-данные в JSON;
- добавлять записи через безопасный путь `dataset.storage_movie.add_movie() -> dataset.dataset_records.add_dataset_record()`;
- подтягивать defaults из IMDb SQL / KP / TMDb перед сохранением записи;
- поддерживать жанры, vibe-теги, оценки и постеры;
- открывать desktop PyQt GUI для watched-базы;
- показывать read-only карточку тайтла, постер, метаданные, оценки и аналитику;
- собирать TMDb candidate pool v1;
- импортировать TMDb result в общий candidate pool;
- строить top prediction из общего пула по runtime-фильтрам;
- добирать KP для incomplete-кандидатов;
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
- `storage/` - низкоуровневое хранение, backup, файлы, нормализация.
- `apis/` - внешние источники: KP, TMDb, IMDb SQL.
- `common/` - чистые утилиты.
- `config/` - константы, схемы, каталоги тегов/жанров.
- `scripts/` - ручные diagnostic/build utilities.
- `assets/desktop/` - desktop assets.
- `tests/` - активный pytest-набор.
- `archive/legacy/` - старые ML/model и прежние ручные тесты.

## Candidate Pool

Общий пул хранится в `C:/DATA/movies-learn/candidate_pool.json`.

TMDb candidate pool v1:

1. TMDb Discover.
2. TMDb Details.
3. IMDb SQL enrichment.
4. KP enrichment.
5. Сохранение отдельного JSON/CSV результата.
6. При необходимости импорт в общий candidate pool.

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
| Dataset | `C:/DATA/movies-learn/dataset.json` |
| Criteria | `C:/DATA/movies-learn/candidate_criteria.json` |
| Общий candidate pool | `C:/DATA/movies-learn/candidate_pool.json` |
| Rating comparison snapshot | `config/rating_comparison_last_snapshot.json` |
| Rating order drafts | `data/rating_order_drafts/rating_order_draft_*.json` |
| API log | `C:/DATA/movies-learn/api_requests.log` |
| Meta | `C:/META/meta-movies-learn/meta_data.json` |
| Backup | `C:/BACKUP/movies-learn/BACKUP/` |
| Excel | `C:/TXT_FILES/movies-learn/edit_dataset.xlsx` |

## Документация

- [PROJECT_MAP.md](PROJECT_MAP.md) - карта активных модулей.
- [STRUCTURE_PLAN.md](STRUCTURE_PLAN.md) - план структурной чистки.
- [ARCHITECTURE_TARGET.md](ARCHITECTURE_TARGET.md) - целевая архитектура и правила зависимостей.
- [add_functions.md](add_functions.md) - правила добавления нового функционала.
- [ADD_RECORD_RULES.md](ADD_RECORD_RULES.md) - контракт добавления/изменения записей.
- [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) - визуальный контракт desktop GUI.
- [DESKTOP_GUI_ROADMAP.md](DESKTOP_GUI_ROADMAP.md) - roadmap desktop GUI.
- `docs/reports/` - исторические отчёты по сессиям.

## Важно

- `candidate_pool.json` не должен меняться от runtime-фильтра перед top prediction.
- Обычный top prediction работает только по ready/complete-кандидатам.
- TMDb import и перенос кандидата в dataset - разные шаги.
- Финальное сообщение об успешном добавлении печатает UI-слой, а не storage.
- Legacy model лежит в `archive/legacy/model/` и не импортируется активным runtime.
