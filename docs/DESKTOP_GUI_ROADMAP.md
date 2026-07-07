# Desktop GUI Roadmap

Roadmap описывает актуальный PyQt desktop для `Watchbane`: watched-база, карточка тайтла, аналитика и поиск кандидатов. Старые desktop-сценарии из `archive/legacy/` не возвращаются в активный GUI.

## Цель

Desktop должен быть рабочим интерфейсом для ежедневного сценария:

1. посмотреть watched-базу;
2. найти тайтл или кандидата;
3. проверить карточку, постер, рейтинги, жанры и описание;
4. добавить/обновить watched-запись через documented services;
5. использовать watched/search/settings сценарии без отдельной вкладки `Информация`.

## Правила

- GUI не пишет JSON напрямую.
- Любой write идет через `dataset` или `candidates.service`.
- Внешние и локальные источники вызываются через `apis` и сервисы.
- Generated JSON не добавляется в git.
- Desktop не содержит старых legacy-вкладок.

## Текущее состояние

| Область | Файлы | Статус |
| --- | --- | --- |
| Watched list + detail card | `desktop/watched/` | done |
| Poster display/actions | `desktop/shared/detail/`, `posters/` | done |
| Edit `user_score` | `desktop/watched/dialogs/score_edit.py`, `dataset.dataset_records` | done |
| Delete watched | `desktop/watched/delete.py`, `desktop/watched/dialogs/delete_dialog.py` | done |
| Add watched wizard | `desktop/watched/add_title/`, `dataset.storage_movie` | done |
| Information/analytics tab | removed from active shell | removed |
| Analytics chart helpers | `desktop/analytics/charts.py`, `desktop/analytics/chart_constructor.py` | internal/not a tab |
| Settings tab | `desktop/settings/tab_view.py`, `desktop/settings/app_settings.py` | done |
| Candidate filters tab | `desktop/candidates/filters_view.py`, `candidates.service` | done |
| Candidate list tab | `desktop/candidates/list_view.py`, `candidates.service` | done |
| Candidate pool operations | console via `candidates.service` | done (console) |

## Этап 1. Polish текущей watched-базы

Статус: done.

- watched sidebar: поиск, сортировка, фильтры, thumbnails;
- detail card: poster, title, chips, ratings, overview;
- context actions: открыть локальный постер, удалить watched;
- стабильный layout при resize;
- helper-тесты в `tests/test_desktop.py`.

## Этап 2. Removed Information/analytics tab

Статус: removed from active desktop shell.

Контракт:

- вкладки `Информация` / `Information` в главном окне больше нет;
- shell не регистрирует `AnalyticsView` и не делает watched-entry wiring для analytics tab;
- если задача упоминает `Информация`, `Information`, `Analytics tab` или analytics как вкладку главного окна, нужно сначала уточнить сценарий.

Внутренние analytics/chart helpers могут оставаться в кодовой базе для тестов и возможных будущих сценариев, но они не являются активной вкладкой.

## Этап 3. Watched write-сценарии

Статус: mostly done.

- добавление записи через wizard;
- редактирование `user_score`;
- удаление watched с preview и подтверждением;
- poster-cache side effects только через dataset/delete services.

Осталось:

- ручное редактирование жанров и raw scores в GUI;
- более понятные ошибки API/defaults;
- UX для неполных данных перед сохранением.

## Этап 4. Поиск кандидатов

Статус: done.

Цель: перенести основной поиск из console в desktop без дублирования core-логики.

Реализовано:

- две вкладки **Фильтры** и **Кандидаты** в [`desktop/shell/tabs.py`](../desktop/shell/tabs.py);
- shared state через [`desktop/candidates/session.py`](../desktop/candidates/session.py);
- runtime-фильтры на вкладке **Фильтры** ([`desktop/candidates/filters_view.py`](../desktop/candidates/filters_view.py));
- лёгкий ranked-список на вкладке **Кандидаты** ([`desktop/candidates/list_view.py`](../desktop/candidates/list_view.py));
- сортировка через `candidates.service.sort_search_candidates`: итог, качество, TMDb rating/votes/popularity, год;
- read-only компактная карточка без actions и без explanations;
- счётчик «уникальных в pool» и скрытые title-дубли в списке;
- async poster preview через `candidate_poster_worker`.

Осталось вне этого этапа:

- actions (add to watched, watchlist, hide) на вкладке кандидатов;
- pool maintenance (dedupe, TMDb build/import) — только console (см. Этап 5).

## Этап 5. Candidate pool operations

Статус: console done.

Console (**Поиск сериалов**):

- обновление общего pool (TMDb build), просмотр, runtime search, mark watched;
- stats с `unique_total` и предупреждением о дублях в JSON;
- **Управление pool**: очистка pool, defaults фильтров, import TMDb result, **очистка дублей**;
- диагностика: suspicious duplicates, poster diagnostics/bulk download.

Desktop:

- mark watched — done (transfer из вкладки Кандидаты);
- dedupe, TMDb import/build, poster batch — **не в GUI**, только console.

## Этап 6. Metadata и posters

Статус: planned.

- показать состояние poster-cache: local/missing/remote;
- batch download missing posters;
- refresh TMDb metadata для выбранной записи;
- аккуратные сообщения по сети, SSL и отсутствию токена.

## Этап 7. Финальная структура GUI

После переноса поиска desktop должен иметь понятные зоны:

- `Watched`;
- `Фильтры` (runtime candidate filters);
- `Кандидаты` (sorted list + read-only card);
- `Настройки` (UI scale и интерфейсные preferences).

Console остаётся рабочим fallback и местом для pool maintenance-сценариев.

### Interface language

Статус: ru/en core desktop UI connected.

- `interface_language` меняет только labels/buttons/messages/placeholders/tooltips.
- `data_language` не используется для интерфейсных строк; он меняет отображаемые данные: title, overview, genres, countries и candidate titles, если есть localized data, и имеет fallback на `ru`/legacy fields.
- Перевод применяется после restart: новые views создаются через `desktop.i18n.tr(...)`, динамического retranslate всего окна нет.
- Новые интерфейсные строки добавляются в `desktop/i18n/catalog.py` сразу для `ru` и `en`.
- Для новых вкладок shell использует `DesktopLanguageContext` из `desktop/language_context.py`: tab labels берутся через `language_context.tr(...)`, а не hardcoded strings.

### Data language

Статус: ru/en display data connected.

- Watched read model, candidate presenters, filters genre labels and add-title preview read `AppSettings.data_language`.
- Desktop-initiated TMDb flows use `data_language` locale (`ru-RU` / `en-US`) instead of hardcoded `ru-RU`.
- New read models and presenters must accept explicit `data_language`; do not infer data language from `interface_language`.
- New poster/list/detail flows must prefer localized `poster_url/poster_path` and invalidate local pixmap caches when a poster file is replaced.
- Existing local JSON can be backfilled with TMDb localized strings via `scripts/backfill_watched_localized_from_tmdb.py --target watched-meta|candidate-pool|all --language en`.
- Backfill only adds `localized.<lang>.title/overview`, creates a backup next to the JSON file and does not rename dataset keys or overwrite legacy title/overview fields.

## Этап 8. Final guardrails

Статус: done / enforced by tests.

- Новая вкладка добавляется только как view + `ShellTabSpec` в `desktop/shell/tabs.py`.
- Cross-tab wiring остаётся в shell; feature views не импортируют другие tab views напрямую.
- `desktop/` не импортирует `storage` или `web` напрямую, кроме documented whitelist.
- Hardcoded fixed/min sizes без scaling helpers запрещены, кроме legacy whitelist с TODO.
- Scale anchors `0.75`, `1.0`, `1.50` являются обязательными smoke/control режимами, но не pixel-perfect golden tests.

## Проверки

Для desktop-изменений:

```powershell
py -m compileall desktop dataset candidates apis storage ui tests
py -m pytest tests/test_desktop.py
```

Для структурных изменений:

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
```
