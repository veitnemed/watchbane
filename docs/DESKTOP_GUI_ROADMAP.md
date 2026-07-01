# Desktop GUI Roadmap

Roadmap описывает актуальный PyQt desktop для `Watchbane`: watched-база, карточка тайтла, аналитика и поиск кандидатов. Старые desktop-сценарии из `archive/legacy/` не возвращаются в активный GUI.

## Цель

Desktop должен быть рабочим интерфейсом для ежедневного сценария:

1. посмотреть watched-базу;
2. найти тайтл или кандидата;
3. проверить карточку, постер, рейтинги, жанры и описание;
4. добавить/обновить watched-запись через documented services;
5. использовать read-only аналитику для качества базы.

## Правила

- GUI не пишет JSON напрямую.
- Любой write идет через `dataset` или `candidates.service`.
- TMDb/KP/IMDb SQL вызываются через `apis` и сервисы.
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
| Analytics read-only | `desktop/analytics/view.py`, `dataset/score_analytics.py` | done |
| Plotly/fallback charts | `desktop/analytics/charts.py` | done |
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

## Этап 2. Read-only аналитика

Статус: done.

Scope:

- dataset completeness;
- score distribution;
- genre distribution;
- average by year;
- gaps against IMDb/KP;
- suspicious records;
- fallback без WebEngine.

Правило: analytics читает dataset/meta и ничего не сохраняет.

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
- сортировка через `candidates.service.sort_search_candidates`: KP, IMDb, голоса KP, голоса IMDb;
- read-only компактная карточка без actions и без explanations;
- счётчик «уникальных в pool» и скрытые title-дубли в списке;
- async poster preview через `candidate_poster_worker`.

Осталось вне этого этапа:

- actions (add to watched, watchlist, hide) на вкладке кандидатов;
- pool maintenance (retry KP, dedupe, TMDb build/import) — только console (см. Этап 5).

## Этап 5. Candidate pool operations

Статус: console done.

Console (**Поиск сериалов**):

- обновление общего pool (TMDb build), просмотр, runtime search, mark watched;
- stats с `unique_total` и предупреждением о дублях в JSON;
- **Управление pool**: очистка pool, defaults фильтров, import TMDb result, legacy KP-сбор, **очистка дублей**;
- диагностика: suspicious duplicates, poster diagnostics/bulk download.

Desktop:

- mark watched — done (transfer из вкладки Кандидаты);
- retry KP, dedupe, TMDb import/build, poster batch — **не в GUI**, только console.

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
- `Analytics` (watched + pool read-only charts).

Console остаётся рабочим fallback и местом для pool maintenance-сценариев.

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
