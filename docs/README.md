# Документация Watchbane

Активная версия: **Watchbane 0.1.1-alpha.1 — Open Route**, алгоритм **ReDeck v0.1.0**.  
Канон релиза: [../VERSION.md](../VERSION.md).

Локальное Windows-приложение: **inbox рекомендаций** — конечная колода до **10** карточек (фильм/сериал) с постерами; действия **смотрел / сохранить / скрыть**. Данные local-first; TMDb под капотом. Не каталог, не стриминг, не сценарий «выбор на вечер» (V0 в parking).

## Читай сначала

1. [PRODUCT_ROADMAP_CONTRACT.md](contracts/PRODUCT_ROADMAP_CONTRACT.md) — **канон продукта**, фаза C, колода до 10, «не делать».
2. [HAPPY_PATH_INBOX.md](contracts/HAPPY_PATH_INBOX.md) — daily path из 6 шагов.
3. [../VERSION.md](../VERSION.md) — версия релиза.
4. [../AGENTS.md](../AGENTS.md) — правила для агента (Composer). Тонкий pointer: [../main_agents.md](../main_agents.md).

**Daily path:** вкладка **Рекомендации** → колода с постерами (или одно «готовим колоду») → разобрать карточки (смотрел / сохранить / скрыть) → при необходимости «Ещё варианты».  
**Коллекция (Моё)** — результат разбора (watched / saved / hidden), не замена колоды.  
**Не сейчас:** V0 «Сегодня», богатые фильтры (A), NL (B), web.

## Что умеет продукт сейчас (Phase C)

- показывать **конечную** колоду рекомендаций с постерами (до 10);
- принимать решения **смотрел / сохранить / скрыть**;
- хранить списки и настройки локально (SQLite);
- учитывать прошлые решения при следующих колодах;
- работать как desktop GUI на Windows (PyQt).

Внутренний запас кандидатов, Discover и пополнение — **под капотом**, не пользовательские сущности продукта. Консоль обслуживания и расширенные настройки поиска — не daily path и не позиционируются как основной продукт.

## Запуск

Python 3.13+ (Windows).

```powershell
py -m pip install -r requirements.txt
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
| `candidates/` | движок рекомендаций и локальное хранилище кандидатов (реализация, не UX «пул») |
| `dataset/` | watched / meta |
| `posters/` | кэш постеров |
| `storage/` | SQLite |
| `apis/` | внешние API (TMDb) |
| `tests/` | pytest |
| `ui/console/` | консоль обслуживания (не основной продукт) |
| `archive/legacy/` | legacy, не runtime |
| `screens/tmp_ui/` | временные скрины агента (не коммитить без просьбы) |
| `internal/archive/docs/` | архив отчётов и старых планов (**не** product direction) |

## Документация (активная)

### Контракты

- [PRODUCT_ROADMAP_CONTRACT.md](contracts/PRODUCT_ROADMAP_CONTRACT.md) — **канон продукта и roadmap**
- [HAPPY_PATH_INBOX.md](contracts/HAPPY_PATH_INBOX.md) — happy path inbox
- [UI_SCALE_CONTRACT.md](contracts/UI_SCALE_CONTRACT.md) — QA scales фазы C: **1.0 / 1.25**
- [DESKTOP_STYLE_CONTRACT.md](contracts/DESKTOP_STYLE_CONTRACT.md)
- [DETAIL_CARD_HERO_CONTRACT.md](contracts/DETAIL_CARD_HERO_CONTRACT.md)
- [DETAIL_CARD_VISUAL_CONTRACT.md](contracts/DETAIL_CARD_VISUAL_CONTRACT.md)
- [CHIP_FILTER_WIDGET_CONTRACT.md](contracts/CHIP_FILTER_WIDGET_CONTRACT.md)
- [TMDB_ONLY_CANDIDATE_FLOW.md](contracts/TMDB_ONLY_CANDIDATE_FLOW.md) — технический flow кандидатов
- [ADD_RECORD_RULES.md](contracts/ADD_RECORD_RULES.md)

### Архитектура

- [OVERVIEW.md](architecture/OVERVIEW.md)
- [PROJECT_MAP.md](architecture/PROJECT_MAP.md)
- [LOGICAL_ARCHITECTURE.md](architecture/LOGICAL_ARCHITECTURE.md)
- [ARCHITECTURE_TARGET.md](architecture/ARCHITECTURE_TARGET.md)
- [CANDIDATE_QUEUE_AND_POSTERS.md](architecture/CANDIDATE_QUEUE_AND_POSTERS.md)
- [REFACTORING_CHECKLIST.md](architecture/REFACTORING_CHECKLIST.md)

### Desktop / storage / сеть

- [DESKTOP_MODULE_MAP.md](desktop/DESKTOP_MODULE_MAP.md)
- [storage/README.md](storage/README.md)
- [TMDB_NETWORK_TROUBLESHOOTING.md](TMDB_NETWORK_TROUBLESHOOTING.md)

### Проект

- [CONTRIBUTING.md](project/CONTRIBUTING.md)
- [SECURITY.md](project/SECURITY.md)
- [CODE_OF_CONDUCT.md](project/CODE_OF_CONDUCT.md)
- [AGENTS.md](project/AGENTS.md) — слои архитектуры (product direction → корневой `AGENTS.md`)
- [add_functions.md](project/add_functions.md)

### Отчёты

Указатель: [reports/README.md](reports/README.md).  
Архив отчётов: [`internal/archive/docs/reports/`](../internal/archive/docs/reports/).

## Архив (не читать как product direction)

- Планы: [`internal/archive/docs/plans/`](../internal/archive/docs/plans/) — в т.ч. `DESKTOP_GUI_ROADMAP.md` (**SUPERSEDED**)
- Closed plans / audits / movie-cycle: `internal/archive/docs/closed-plans/`, `audits/`, `codex_movie_cycle/`

## Legacy JSON

SQLite — канон хранения. JSON — только совместимость/миграции:

```powershell
py tools/migrations/migrate_json_to_sqlite.py --dry-run
py tools/migrations/migrate_json_to_sqlite.py --apply
```

Сначала восстанавливай backup из `data/backups/`.

## Важно

- Daily path Phase C **не** требует «Настройки поиска» и детальных фильтров.
- Агент не берёт product direction из архивных планов и отчётов.
- Public candidate flow: только `TMDB_TOKEN` (без KP/IMDb dataset как обязательного источника).
- Векторы A (богатые фильтры), B (NL), V0 («Сегодня») — **parking**, не текущий фокус.
