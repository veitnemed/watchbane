# Desktop Module Map

Карта PyQt desktop GUI: куда класть код, как добавлять вкладки и как не ломать границы слоёв.

Связанные документы:

- [DESKTOP_GUI_ROADMAP.md](DESKTOP_GUI_ROADMAP.md) — roadmap функций.
- [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) — визуальный контракт.
- [ARCHITECTURE_TARGET.md](ARCHITECTURE_TARGET.md) — общая архитектура проекта.

## Принцип

Desktop — **тонкий слой сценариев** поверх `dataset`, `candidates.service`, `posters`. UI не пишет JSON напрямую.

Вкладка `Информация` удалена из активного shell. Если новая задача упоминает `Информация`, `Information`, `Analytics tab` или analytics как вкладку главного окна, сначала нужно уточнить требуемый сценарий и не восстанавливать вкладку автоматически.

```text
start_app.py → desktop.app.main()
                 → shell/main_window.WatchedMoviesWindow
                      → WatchedTabView / Candidate*View / SettingsTabView
                           → presenters + shared widgets
                           → service layer (dataset, candidates)
```

`desktop/watched/model/load.py` — compatibility wrapper. Фактическая загрузка watched read model живет в `dataset/read_models/watched.py`.

## Структура пакетов

```text
dataset/
  language.py                    # data_language helpers, localized fallbacks, TMDb locale mapping
  migrations/
    tmdb_localized.py            # safe TMDb localized backfill for old watched/candidate data
  read_models/
    watched.py                   # watched desktop/export read facade (dataset_key, movie, display card)

desktop/
  app.py                         # thin entry: re-exports main + WatchedMoviesWindow

  shell/
    bootstrap.py                 # QApplication, WebEngine prep, main()
    main_window.py               # WatchedMoviesWindow: chrome + status bar
    tab_contract.py              # TabView protocol + optional activation helper
    tabs.py                      # build_main_tabs(), MainTabRegistry, AppTabsContext
  i18n/
    catalog.py                   # ru/en interface strings
    translator.py                # tr(key) with ru/key fallback
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
    tab_actions.py               # CRUD, context menu, add-title actions
    dialogs/
      score_edit.py              # ScoreEditDialog
      delete_dialog.py           # WatchedDeleteDialog
    add_title/
      constants.py               # dialog sizes and QSS token
      search_dialog.py           # AddTitleSearchDialog
      preview_dialog.py          # AddTitlePreviewDialog
      flow.py                    # run_add_title_flow, transfer flow
      dialog.py                  # backward-compatible re-exports
      worker.py                  # AddTitleResolveWorker
  candidates/
    session.py                   # shared filter/sort state
    filters_view.py              # вкладка Фильтры (orchestrator)
    filters_intro.py             # intro copy and pool stats text
    filters_form.py              # scrollable filter form widgets
    list_view.py                 # вкладка Кандидаты
    list_delegate.py             # card-style list rows
    filters_controls.py          # threshold slider helpers
    presenters.py                # format/map candidate records
    workers/poster_worker.py
  analytics/                     # internal report/chart helpers, not an active shell tab
    view.py                      # legacy/non-registered AnalyticsView
    chart_constructor.py         # pure chart-constructor aggregation
    constants.py                 # typography, spacing, icons
    sections/
      summary.py                 # legacy/internal helpers
      charts_host.py             # Plotly host
      fallback_bars.py           # bar fallbacks
      lists.py                   # legacy/internal list helpers
    charts.py                    # Plotly HTML builders, generic constructor charts
  shared/
    detail/
      types.py                   # DetailEntry
      presenters.py              # card-facing formatters (no watched import)
      posters.py                 # poster path / shell helpers (shared lookup)
      profiles.py                # layout profiles and constants
      rating_indicator.py        # RatingCircleIndicator
      list_delegate.py           # WatchedListItemDelegate
      card.py                    # WatchedDetailCard orchestrator
      card_pills.py              # pill row helpers
      card_poster.py             # poster sync and context menu mixin
    widgets/
      range_slider.py
      list_search.py
      collapsible_chip_helpers.py
      genre_chip_selector.py
      country_chip_selector.py
  theme/
    tokens.py                    # COLOR_*, FONT_*, radius, semantic names
    layout.py                    # spacing, margins, min/max sizes, scaled layout constants
    shell_layout.py              # compatibility re-exports for shell layout constants
    styles/
      app.py                     # build_app_style (composer)
      shell.py                   # tabs, scrollbars, status bar
      form_controls.py           # inputs, combos, range sliders
      lists.py                   # QListWidget base
      watched_shell.py           # watched sidebar/filters
      candidates_shell.py        # candidate filters/list
      chips.py                   # genre/country chip selectors
      dialogs.py                 # score/delete/add-title dialogs
      detail_card.py             # detail card, poster, bar fallbacks
      analytics.py               # build_analytics_style
```

| Модуль | Роль | Слой |
| --- | --- | --- |
| `app.py` | thin entry, re-exports `main` | shell |
| `shell/main_window.py` | главное окно, status bar | shell |
| `shell/tab_contract.py` | `TabView` protocol and optional activation helper | shell |
| `shell/tabs.py` | `build_main_tabs()`, tab registry, cross-tab wiring | shell |
| `i18n/catalog.py` | ru/en catalog for interface labels/buttons/messages/placeholders | UI i18n |
| `i18n/translator.py` | `tr(key)` and persisted interface language lookup | UI i18n |
| `dataset/language.py` | `data_language` normalization, localized value selection, genre labels, TMDb locale mapping | domain localization |
| `dataset/migrations/tmdb_localized.py` | backfill old JSON records with `localized.<lang>.title/overview` from TMDb locale responses | domain migration |
| `watched/tab.py` | layout, list state, selection | feature view |
| `watched/tab_actions.py` | delete/score/add-title write actions | feature view |
| `watched/sidebar.py` | list widget, search, sort, add-title button | feature view |
| `watched/filters_panel.py` | collapsible score/year/genre filters | feature view |
| `watched/model/load.py` | compatibility wrapper over `dataset/read_models/watched.py` | model, no Qt |
| `watched/model/` | watched load, filters, watched-specific formatters, score save; no Qt and no `shared/detail` presenter re-export | model |
| `dataset/read_models/watched.py` | watched read facade: load dataset, lookup/poster cache, display card | domain read model |
| `shared/detail/` | card, delegate, presenters (no `watched/` import) | shared |
| `watched/dialogs/score_edit.py` | диалог редактирования user_score | dialog |
| `watched/add_title/` | wizard добавления / transfer из pool | dialog + worker |
| `candidates/session.py` | shared state Фильтры ↔ Кандидаты | session |
| `candidates/filters_view.py` | вкладка Фильтры (orchestrator) | feature view |
| `candidates/filters_form.py` | filter form widget builders | feature view |
| `candidates/filters_intro.py` | intro/stats copy | presenter |
| `candidates/list_view.py` | вкладка Кандидаты | feature view |
| `candidates/list_delegate.py` | card-style list row delegate | shared UI |
| `candidates/presenters.py` | format/map для UI | presenter |
| `analytics/view.py` | legacy/non-registered analytics view; not an active desktop tab | internal UI |
| `analytics/chart_constructor.py` | pure aggregation for custom charts | model |
| `analytics/sections/*` | Plotly host, fallback bars and legacy/internal section helpers | feature view |
| `analytics/charts.py` | Plotly chart builders, including generic constructor charts | charts |
| `settings/tab_view.py` | active settings tab for UI scale/preferences | feature view |
| `shared/widgets/` | range_slider, list_search, chip selectors | shared |
| `theme/tokens.py` | colors, fonts, radii, semantic visual names | theme |
| `theme/layout.py` | spacing, margins, min/max sizes, scaled layout constants | theme |
| `theme/shell_layout.py` | compatibility facade over `theme/layout.py` | theme |
| `theme/styles/*` | QSS builders per screen | theme |

## Контракт TabView

Каждая активная вкладка регистрируется через `ShellTabSpec` в `desktop/shell/tabs.py`.
Контракт описан в `desktop/shell/tab_contract.py`.

Минимальный интерфейс view-класса (как `CandidateListView`, `WatchedTabView`, `SettingsTabView`):

```python
class TabView(Protocol):
    @property
    def widget(self) -> QWidget: ...   # корневой виджет для QTabWidget
```

`on_tab_activated()` не является обязательным методом view. `MainTabRegistry` вызывает `activate_tab_view(view)`, который безопасно делает `getattr(view, "on_tab_activated", None)` и запускает hook только если он callable.

## Контракт языка интерфейса

- `interface_language` переводит только desktop UI strings: labels, buttons, messages, placeholders, tooltips.
- `data_language` не должен использоваться для интерфейсных подписей; он управляет отображаемыми данными и desktop-initiated metadata/TMDb запросами.
- Перевод интерфейса применяется после restart: view создаётся с текущим persisted `interface_language`, без динамического retranslate всего окна.
- Новые пользовательские строки добавляются в `desktop/i18n/catalog.py` для `ru` и `en`; каталоги должны иметь одинаковый набор ключей.
- Data strings не переводятся через interface i18n: title, overview, genres, countries, candidate titles и значения metadata остаются данными.
- Data localization живет в `dataset/language.py`; desktop read models и presenters принимают `data_language` и должны иметь safe fallback на `ru`/legacy fields.
- Desktop TMDb flows получают locale через app setting `data_language` (`ru -> ru-RU`, `en -> en-US`) и сохраняют фактический locale в `source_query.language`.
- Настройки языков доступны в `Настройки -> Интерфейс -> Язык`; для первого стабильного варианта смена применяется после restart или перезагрузки экранов.
- Старые локальные JSON без `localized.en` обновляются через `scripts/backfill_watched_localized_from_tmdb.py`; backfill добавляет только localized layer, делает backup рядом с JSON и не переименовывает dataset keys.

Шаблон добавления вкладки:

```python
feature_view = SomeFeatureView(...)
registry.register(ShellTabSpec("feature_id", tr("tabs.feature"), feature_view))
```

Правила:

- view **не импортирует** другие feature views напрямую;
- cross-tab wiring живет только в shell (`desktop/shell/tabs.py`) или shared session (`CandidateSearchSession`);
- status bar — callback `on_status_message(msg, timeout_ms)` из shell;
- изменение watched-базы не должно напрямую регистрировать removed `Информация`/analytics tab callbacks.

## Куда класть новый код

| Задача | Куда |
| --- | --- |
| Новая вкладка | `desktop/<feature>/` + регистрация в `shell/tabs.py` (`build_main_tabs`) |
| Фильтр/сортировка watched (логика) | `watched/model/filters.py` |
| Layout watched sidebar | `watched/sidebar.py` |
| Watched filter panel UI | `watched/filters_panel.py` |
| Detail card layout / show_entry | `shared/detail/card.py` |
| Detail card pills | `shared/detail/card_pills.py` |
| Detail card poster area | `shared/detail/card_poster.py` |
| Detail card formatters | `shared/detail/presenters.py` |
| List delegate | `shared/detail/list_delegate.py` |
| Candidate filter form layout | `candidates/filters_form.py` |
| Candidate filter intro copy | `candidates/filters_intro.py` |
| Форматирование candidate list | `candidates/presenters.py` |
| Candidate list row paint | `candidates/list_delegate.py` |
| Write-сценарий (save/delete) | `watched/delete.py` / `dataset` + dialog |
| Переиспользуемый виджет без domain | `shared/widgets/` |
| UI label/button/message/placeholder | `i18n/catalog.py` + `tr("feature.key")` |
| Отображаемые localized data/title/overview/genre/country | `dataset/language.py` + read model/presenter `data_language` parameter |
| Backfill localized data для старого watched/candidate JSON | `dataset/migrations/tmdb_localized.py` + `scripts/backfill_watched_localized_from_tmdb.py` |
| Desktop TMDb request language | `desktop/settings/app_settings.language_to_tmdb_locale()` at desktop boundary, pass locale into `dataset`/`candidates` service |
| Новый цвет/радиус/семантический font token | `theme/tokens.py` |
| Новый размер, margin, spacing, min/max width/height | `theme/layout.py` + scaling helpers |
| QSS нового экрана | `theme/styles/<screen>.py` |

## Запрещённые зависимости

```text
❌ desktop → storage (напрямую save/load JSON)
❌ desktop → web.export (для watched display cards)
❌ feature view → feature view (Watched → Candidate)
❌ shared/detail → watched/ (presenters live in shared)
❌ watched/model/ → PyQt6
❌ watched/model/__init__.py → shared/detail presenter re-export
❌ candidates/* → watched/tab.py
✅ desktop → dataset read facade (`dataset/read_models/watched.py` / `dataset.service`)
✅ candidate views → shared/detail (card reused across watched, candidates, add-title)
✅ все views → dataset / candidates.service
```

Временный whitelist для существующих desktop → storage импортов:

- `desktop/shell/bootstrap.py` → `storage.runtime.ensure_runtime_data_layout`: startup runtime data layout, не feature load/save.
- `desktop/shared/detail/posters.py` → `storage.files.open_file`: shell-open adapter для локального пути. TODO: вынести в отдельный platform/files facade при следующей чистке storage boundary.

## Добавление вкладки (чеклист)

1. Создать view в `desktop/<feature>/` с `.widget`.
2. Бизнес-логику — в `dataset` / `candidates` / model без Qt.
3. QSS — через `desktop.theme` (`tokens.py` для цветов/font/radius, `layout.py` для размеров, `styles/` для QSS).
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
13. ~~Cleanup: split `filters_view`, `watched/tab` + `add_title`, `shared/detail/card`; keep `desktop/settings/` as an active feature package~~ done

## Проверки

```powershell
py -m compileall desktop dataset candidates storage ui tests
py -m pytest tests/test_desktop.py
```

## Language Extension Guardrail

Use `desktop/language_context.py` for new tabs and feature-level UI objects.

- Shell creates a `DesktopLanguageContext` once in `desktop/shell/tabs.py`.
- Tab labels use `language_context.tr("tabs.<id>")`, not hardcoded strings.
- UI labels/buttons/messages/placeholders go through `desktop/i18n/catalog.py` and `tr(...)`/`language_context.tr(...)`.
- Data display uses explicit `data_language` arguments in read models and presenters.
- TMDb requests started by desktop use `DesktopLanguageContext.tmdb_locale` or `language_to_tmdb_locale(data_language)`.
- Do not use `interface_language` to choose title/overview/poster data.
- Do not use `data_language` for UI copy.
- If a new feature has list/detail posters, route poster selection through localized `poster_url/poster_path` and clear local pixmap caches when a file is replaced.

## New Code Routing Guardrail

Use this routing for new desktop code:

- New tab: `desktop/<feature>/view.py` plus `ShellTabSpec` registration in `desktop/shell/tabs.py`.
- Actions/write orchestration: `desktop/<feature>/actions.py` or a focused `desktop/<feature>/<scenario>_actions.py`.
- State without Qt: `desktop/<feature>/state.py`.
- Shared widget: `desktop/shared/widgets/`.
- Detail card formatting: `desktop/shared/detail/`.
- QSS: `desktop/theme/styles/`.
- Domain read/write: `dataset/` or `candidates.service`.
- Sizes, margins and spacing: `desktop/theme/layout.py` plus scaling helpers.

Guardrail tests:

- `tests/test_desktop.py` checks tab registration, optional activation, tab ids, cross-tab wiring boundaries and desktop import boundaries.
- `tests/test_ui_scale_settings.py` checks scale anchors and hardcoded fixed-size whitelist.
