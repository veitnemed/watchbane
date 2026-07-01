# Desktop Module Map

Карта PyQt desktop GUI: куда класть код, как добавлять вкладки и как не ломать границы слоёв.

Связанные документы:

- [DESKTOP_GUI_ROADMAP.md](DESKTOP_GUI_ROADMAP.md) — roadmap функций.
- [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) — визуальный контракт.
- [ARCHITECTURE_TARGET.md](ARCHITECTURE_TARGET.md) — общая архитектура проекта.

## Принцип

Desktop — **тонкий слой сценариев** поверх `dataset`, `candidates.service`, `posters`. UI не пишет JSON напрямую.

```text
start_app.py → desktop.app.main()
                 → shell/main_window.WatchedMoviesWindow
                      → WatchedTabView / Candidate*View / AnalyticsView
                           → presenters + shared widgets
                           → service layer (dataset, candidates)
```

## Структура пакетов

```text
desktop/
  app.py                         # thin entry: re-exports main + WatchedMoviesWindow

  shell/
    bootstrap.py                 # QApplication, WebEngine prep, main()
    main_window.py               # WatchedMoviesWindow: chrome + status bar
    tabs.py                      # build_main_tabs(), MainTabRegistry, AppTabsContext
  watched/
    model/                       # load, filter, sort, format, writes (no Qt widgets)
      load.py
      filters.py
      formatters.py
      score_write.py
    filters_panel.py             # WatchedFiltersPanel (collapsible score/year/genre)
    sidebar.py                   # build_watched_sidebar()
    delete.py                    # delete preview/execute helpers
    tab.py                       # WatchedTabView orchestration
    dialogs/
      score_edit.py              # ScoreEditDialog
      delete_dialog.py           # WatchedDeleteDialog
    add_title/
      dialog.py                  # search/preview flow
      worker.py                  # AddTitleResolveWorker
  candidates/
    session.py                   # shared filter/sort state
    filters_view.py              # вкладка Фильтры
    list_view.py                 # вкладка Кандидаты
    list_delegate.py             # card-style list rows
    presenters.py                # format/map candidate records
    workers/poster_worker.py
  analytics/
    view.py                      # AnalyticsView orchestrator
    constants.py                 # typography, spacing, icons
    sections/
      summary.py                 # KPI, completeness, insights
      charts_host.py             # Plotly host
      fallback_bars.py           # bar fallbacks
      lists.py                   # IMDb delta, gaps, dense scores
    charts.py                    # Plotly HTML builders
  shared/
    detail/
      types.py                   # DetailEntry
      presenters.py              # card-facing formatters (no watched import)
      posters.py                 # poster path / shell helpers
      profiles.py                # layout profiles and constants
      rating_indicator.py        # RatingCircleIndicator
      list_delegate.py           # WatchedListItemDelegate
      card.py                    # WatchedDetailCard only
    widgets/
      range_slider.py
      list_search.py
      collapsible_chip_helpers.py
      genre_chip_selector.py
      country_chip_selector.py
  theme/
    tokens.py                    # COLOR_*, FONT_*, spacing, radius
    styles/
      app.py                     # build_app_style
      dialogs.py                 # score/delete/add-title dialogs
      detail_card.py             # detail card, poster, bar fallbacks
      analytics.py               # build_analytics_style
```

| Модуль | Роль | Слой |
| --- | --- | --- |
| `app.py` | thin entry, re-exports `main` | shell |
| `shell/main_window.py` | главное окно, status bar | shell |
| `shell/tabs.py` | `build_main_tabs()`, tab registry, cross-tab wiring | shell |
| `watched/tab.py` | orchestration: detail card, dialogs, CRUD | feature view |
| `watched/sidebar.py` | list widget, search, sort, add-title button | feature view |
| `watched/filters_panel.py` | collapsible score/year/genre filters | feature view |
| `watched/model/` | load/filter/format, poster paths, score save | model |
| `shared/detail/` | card, delegate, presenters (no `watched/` import) | shared |
| `watched/dialogs/score_edit.py` | диалог редактирования user_score | dialog |
| `watched/add_title/` | wizard добавления / transfer из pool | dialog + worker |
| `candidates/session.py` | shared state Фильтры ↔ Кандидаты | session |
| `candidates/filters_view.py` | вкладка Фильтры | feature view |
| `candidates/list_view.py` | вкладка Кандидаты | feature view |
| `candidates/list_delegate.py` | card-style list row delegate | shared UI |
| `candidates/presenters.py` | format/map для UI | presenter |
| `analytics/view.py` | read-only вкладка Analytics (orchestrator) | feature view |
| `analytics/sections/*` | KPI, charts, lists section mixins | feature view |
| `analytics/charts.py` | Plotly chart builders | charts |
| `shared/widgets/` | range_slider, list_search, chip selectors | shared |
| `theme/tokens.py` | colors, fonts, spacing | theme |
| `theme/styles/*` | QSS builders per screen | theme |

## Контракт feature view

Каждая вкладка — класс с единым интерфейсом (как `CandidateListView`, `WatchedTabView`, `AnalyticsView`):

```python
class SomeTabView:
    @property
    def widget(self) -> QWidget: ...   # корневой виджет для QTabWidget

    def on_tab_activated(self) -> None: ...  # опционально: lazy refresh
```

Правила:

- view **не импортирует** другие feature views напрямую;
- cross-tab события идут через shell (`WatchedMoviesWindow`) или shared session (`CandidateSearchSession`);
- status bar — callback `on_status_message(msg, timeout_ms)` из shell;
- изменение watched-базы — callback `on_entries_changed(entries)` для analytics и др.

## Куда класть новый код

| Задача | Куда |
| --- | --- |
| Новая вкладка | `desktop/<feature>/` + регистрация в `shell/tabs.py` (`build_main_tabs`) |
| Фильтр/сортировка watched (логика) | `watched/model/filters.py` |
| Layout watched sidebar | `watched/sidebar.py` |
| Watched filter panel UI | `watched/filters_panel.py` |
| Detail card formatters | `shared/detail/presenters.py` |
| Detail card / list delegate | `shared/detail/card.py`, `list_delegate.py` |
| Форматирование candidate list | `candidates/presenters.py` |
| Candidate list row paint | `candidates/list_delegate.py` |
| Write-сценарий (save/delete) | `watched/delete.py` / `dataset` + dialog |
| Переиспользуемый виджет без domain | `shared/widgets/` |
| Новый цвет/spacing | `theme/tokens.py` |
| QSS нового экрана | `theme/styles/<screen>.py` |

## Запрещённые зависимости

```text
❌ desktop → storage (напрямую save/load JSON)
❌ feature view → feature view (Watched → Candidate)
❌ shared/detail → watched/ (presenters live in shared)
❌ watched/model/ → PyQt6
❌ candidates/* → watched/tab.py
✅ candidate views → shared/detail (card reused across watched, candidates, add-title)
✅ watched/model → shared/detail/presenters (re-export for backward compat)
✅ все views → dataset / candidates.service
```

## Добавление вкладки (чеклист)

1. Создать view в `desktop/<feature>/` с `.widget`.
2. Бизнес-логику — в `dataset` / `candidates` / model без Qt.
3. QSS — через `desktop.theme` (`tokens.py` + `styles/`).
4. Зарегистрировать в `shell/tabs.py` через `build_main_tabs()` / `MainTabRegistry`.
5. Cross-tab callbacks — в `build_main_tabs()` (не в feature views).
6. Тесты в `tests/test_desktop.py`.

## Порядок миграции

1. ~~`watched/model.py` + `detail_card.py`~~ done
2. ~~`watched/tab.py`~~ done
3. ~~`candidates/` — session, filters_view, list_view, presenters, workers~~ done
4. ~~`analytics/` — view, charts~~ done
5. ~~`shared/widgets/`~~ done
6. ~~`theme/` — tokens + styles~~ done
7. ~~Удалить shims~~ done
8. ~~Перенести flat-файлы (`app.py` → `shell/`, dialogs в feature-пакеты)~~ done
9. ~~`shell/tabs.py`, `shared/detail/`, `on_tab_activated`~~ done
10. ~~`shared/detail/{types,presenters,posters}.py` — убрать `watched/` из card~~ done
11. ~~Разбить монолиты: `shared/detail/*`, `watched/{sidebar,filters_panel,model/}`, `candidates/list_delegate.py`~~ done
12. ~~`analytics/sections/*`, `build_main_tabs()` в shell, docs~~ done

## Проверки

```powershell
py -m compileall desktop dataset candidates storage ui tests
py -m pytest tests/test_desktop.py
```
