# Архитектура Watchbane

Версия среза: **Watchbane 0.1.1-alpha.1 — Open Route** / **ReDeck v0.1.0**.  
Канон релиза: [../../VERSION.md](../../VERSION.md).  
Канон продукта: [../contracts/PRODUCT_ROADMAP_CONTRACT.md](../contracts/PRODUCT_ROADMAP_CONTRACT.md).

Watchbane — **local-first** приложение на PyQt6. Desktop UI вызывает use cases; доменные сервисы держат рекомендации и библиотеку; инфраструктура — хранение и внешние API.

```text
desktop/             экраны PyQt6, presenters, workers
app/use_cases/       продуктовые операции для UI
candidates/          пул кандидатов, поиск, onboarding, TMDb
dataset/             коллекция watched и read-модели
posters/             постеры: разрешение, кэш, загрузка
storage/             SQLite runtime и репозитории
apis/                клиенты внешних сервисов
config/, common/     конфигурация и общие утилиты
tools/, diagnostics/ обслуживание и диагностика
```

## Поток кандидатов

`desktop/candidates` вызывает `app/use_cases/candidate_search.py`. Use case координирует `candidates/pool_service.py` и `candidates/search_service.py`; записи идут через узкие use cases (`candidate_actions.py`, `onboarding.py` и т.п.).

`candidates/service.py` — compatibility facade для консоли и старых интеграций. Новый код должен импортировать узкий сервис или `app/use_cases`, а не наращивать facade.

## Направление зависимостей

Модули `desktop/` не должны напрямую импортировать SQLite-репозитории, TMDb builders или API-compatibility. Правило охраняет `tests/architecture/test_ui_import_boundaries.py`.

## Связанные документы

- [LOGICAL_ARCHITECTURE.md](./LOGICAL_ARCHITECTURE.md) — зоны UI / Domain / Infra
- [PROJECT_MAP.md](./PROJECT_MAP.md) — карта модулей
- [ARCHITECTURE_TARGET.md](./ARCHITECTURE_TARGET.md) — целевые правила слоёв
- [CANDIDATE_QUEUE_AND_POSTERS.md](./CANDIDATE_QUEUE_AND_POSTERS.md) — колода и постеры (техсправочник)
