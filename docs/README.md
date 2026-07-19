# Документация Watchbane

Активная версия: **Watchbane 0.1.1-alpha.1 — Open Route**, алгоритм **ReDeck v0.1.0**.  
Канон релиза: [../VERSION.md](../VERSION.md).  
Канон продукта: [contracts/PRODUCT_ROADMAP_CONTRACT.md](contracts/PRODUCT_ROADMAP_CONTRACT.md).

Локальное Windows-приложение: **inbox рекомендаций** — конечная колода (фильм/сериал), действия смотрел / сохранить / скрыть; TMDb под капотом. Не «выбор на вечер», не каталог, не стриминг. Канон: **вариант X** в PRODUCT_ROADMAP.

Старая ML-модель и ручные тесты — в `archive/legacy/`, не в runtime.

## Читай сначала

1. [PRODUCT_ROADMAP_CONTRACT.md](contracts/PRODUCT_ROADMAP_CONTRACT.md) — продукт, фаза C, колода до 10, «не делать».
2. [VERSION.md](../VERSION.md) — версия релиза.
3. [AGENTS.md](../AGENTS.md) — правила для агента (Composer).

**Daily path:** вкладка **Рекомендации** → колода → разобрать карточки (смотрел / сохранить / скрыть).  
**Коллекция (Моё)** — результат разбора.  
**Не сейчас:** сценарий «Сегодня» / V0.

## Что умеет проект

- показывать конечную колоду рекомендаций из локального пула;
- хранить watched / saved / hidden, настройки и метаданные постеров в SQLite;
- пополнять пул через TMDb Discover (свой токен);
- фильтровать и ранжировать кандидатов локально;
- вести коллекцию и карточку тайтла в desktop GUI;
- обслуживать пул через консоль (`start_console.py`).

## Запуск

Python 3.13+.

```powershell
py start_console.py
py start_app.py
```

### Сборка Windows (onedir)

```powershell
./tools/build_desktop.ps1
./dist/Watchbane/Watchbane.exe
```

Рядом с `Watchbane.exe` должен оставаться `_internal/`.

Токен TMDb: `TMDB_TOKEN`, `.env.local` или `tmdb.env` — не коммитить и не печатать в лог.

## Основные папки

| Папка | Назначение |
| --- | --- |
| `app/` | сценарии приложения |
| `desktop/` | PyQt GUI |
| `ui/console/` | консоль |
| `dataset/` | watched / meta |
| `candidates/` | пул и рекомендации |
| `posters/` | кэш постеров |
| `storage/` | SQLite |
| `apis/` | внешние API |
| `tests/` | pytest |
| `archive/legacy/` | legacy, не runtime |
| `screens/tmp_ui/` | временные скрины (не коммитить) |
| `internal/archive/docs/` | архив отчётов и старых планов |

## Пул кандидатов

Один пул в SQLite (`data/watchbane.sqlite3`), criteria `"pool"`. Named pools не создаются.

## Документация (активная)

### Архитектура

- [OVERVIEW.md](architecture/OVERVIEW.md) — обзор
- [PROJECT_MAP.md](architecture/PROJECT_MAP.md) — карта модулей
- [LOGICAL_ARCHITECTURE.md](architecture/LOGICAL_ARCHITECTURE.md) — зоны слоёв
- [ARCHITECTURE_TARGET.md](architecture/ARCHITECTURE_TARGET.md) — целевые правила
- [CANDIDATE_QUEUE_AND_POSTERS.md](architecture/CANDIDATE_QUEUE_AND_POSTERS.md) — колода и постеры
- [REFACTORING_CHECKLIST.md](architecture/REFACTORING_CHECKLIST.md) — чеклист рефакторинга

### Контракты

- [PRODUCT_ROADMAP_CONTRACT.md](contracts/PRODUCT_ROADMAP_CONTRACT.md) — **канон продукта**
- [ADD_RECORD_RULES.md](contracts/ADD_RECORD_RULES.md)
- [TMDB_ONLY_CANDIDATE_FLOW.md](contracts/TMDB_ONLY_CANDIDATE_FLOW.md)
- [DESKTOP_STYLE_CONTRACT.md](contracts/DESKTOP_STYLE_CONTRACT.md)
- [UI_SCALE_CONTRACT.md](contracts/UI_SCALE_CONTRACT.md)
- [CHIP_FILTER_WIDGET_CONTRACT.md](contracts/CHIP_FILTER_WIDGET_CONTRACT.md)
- [DETAIL_CARD_HERO_CONTRACT.md](contracts/DETAIL_CARD_HERO_CONTRACT.md)
- [DETAIL_CARD_VISUAL_CONTRACT.md](contracts/DETAIL_CARD_VISUAL_CONTRACT.md)

### Desktop / storage / ops

- [DESKTOP_MODULE_MAP.md](desktop/DESKTOP_MODULE_MAP.md)
- [storage/README.md](storage/README.md) — кратко про SQLite
- [WORKSPACE_HOUSEKEEPING.md](operations/WORKSPACE_HOUSEKEEPING.md)
- [REPORT_OUTPUT_POLICY.md](operations/REPORT_OUTPUT_POLICY.md)
- [onboarding_dev_sandbox.md](operations/onboarding_dev_sandbox.md)
- [TMDB_NETWORK_TROUBLESHOOTING.md](TMDB_NETWORK_TROUBLESHOOTING.md)
- [GITHUB_PUBLICATION_CHECKLIST.md](operations/GITHUB_PUBLICATION_CHECKLIST.md)

### Проект

- [add_functions.md](project/add_functions.md)
- [CONTRIBUTING.md](project/CONTRIBUTING.md)
- [SECURITY.md](project/SECURITY.md)
- [CODE_OF_CONDUCT.md](project/CODE_OF_CONDUCT.md)
- [AGENTS.md](project/AGENTS.md) — только слои (product → корневой AGENTS.md)

### Отчёты

Активный указатель: [reports/README.md](reports/README.md).  
Архив: [`internal/archive/docs/reports/`](../internal/archive/docs/reports/).

## Архив (не читать как direction)

- Планы: [`internal/archive/docs/plans/`](../internal/archive/docs/plans/) — STRUCTURE, POSTER, DESKTOP_GUI_ROADMAP, DATA_STORAGE
- Closed plans / audits / movie-cycle: `internal/archive/docs/closed-plans/`, `audits/`, `codex_movie_cycle/`

## Legacy JSON

SQLite — канон. JSON — только совместимость:

```powershell
py tools/migrations/migrate_json_to_sqlite.py --dry-run
py tools/migrations/migrate_json_to_sqlite.py --apply
```

Сначала восстанавливай backup из `data/backups/`.

## Важно

- Runtime-фильтры поиска не должны менять сохранённый SQLite pool.
- Поиск/ранжирование — по ready/complete кандидатам.
- Public candidate flow: только `TMDB_TOKEN` (без KP/IMDb dataset).
- Агент не берёт product direction из архивных планов и отчётов.
