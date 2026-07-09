# Инструкции для агента в корне проекта

Объясняй простым языком и по делу.

Перед изменениями оцени слой проекта. Физически папки не переносим, `src/` пока не вводим.

## Логические зоны

- UI: `app/`, `desktop/`, `ui/`, `web/`.
- Domain: `dataset/`, `candidates/`, `posters/`.
- Infra: `apis/`, `storage/`, `config/`, `common/`.
- Project: `tests/`, `docs/`, `scripts/`, `assets/`.

`data/`, `datasets/`, `diagnostics/`, `reports/`, `archive/`, `.pytest-tmp/`, `.browser_profiles/`, `_safety_audit/`, `__pycache__/` не являются архитектурными зонами.

## Правила слоёв

- UI отвечает за окна, кнопки, ввод, таблицы, preview, console/web представление.
- UI может вызывать Domain-сервисы, но не пишет `data/*.json` напрямую.
- UI не содержит сетевую логику KP/TMDb и тяжёлую бизнес-логику рекомендаций.
- Domain содержит бизнес-логику watched dataset, candidate pool и posters.
- Domain может использовать Infra, но не импортирует `desktop`, `ui`, `web`.
- Infra отвечает за API, storage, config и маленькие shared utilities.
- Infra не импортирует UI и не зависит от `desktop`.
- `scripts/` — тонкие ручные entrypoints. Бизнес-логику выносить в Domain/Infra.

Подробная карта: `LOGICAL_ARCHITECTURE.md`.
