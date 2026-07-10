# Логическая архитектура

Физически папки остаются как сейчас. `src/` пока не вводим: это отдельная миграция импортов.

Документ задаёт, как воспринимать проект в голове, документации, VS Code и задачах для Codex.

## Зоны

```text
UI
  app/          запуск и orchestration приложения
  desktop/      PyQt GUI
  ui/           console UI
  web/          read-only web/export views

Domain
  dataset/      watched titles domain
  candidates/   candidate pool и рекомендации
  posters/      poster domain/cache logic

Infra
  apis/         TMDb client (legacy KP/IMDb in archive/legacy/apis/)
  storage/      runtime data read/write (SQLite canonical; JSON import/export via scripts)
  config/       scheme, constants, path aliases
  common/       shared small utilities

Project
  tests/        tests
  docs/         documentation
  scripts/      manual tools/jobs/migrations
  assets/       static assets

Runtime / hidden
  data/
  datasets/
  diagnostics/
  reports/

Legacy / hidden
  archive/
```

## Правила слоёв

### UI

- отвечает за окна, кнопки, ввод пользователя, таблицы, preview, console/web представление;
- может вызывать Domain-сервисы;
- не пишет `data/*.json` напрямую;
- не содержит сетевую логику внешних источников;
- не содержит тяжёлую бизнес-логику рекомендаций.

### Domain

- отвечает за watched dataset, candidate pool, posters;
- содержит бизнес-логику;
- может использовать Infra;
- не импортирует `desktop`, `ui`, `web`;
- не знает про кнопки, виджеты и `QMessageBox`.

### Infra

- отвечает за API, storage, config, common utilities;
- не импортирует UI;
- не зависит от `desktop`;
- `storage` работает с файлами, но UI не должен обходить storage/service path.

### Project

- содержит `tests`, `docs`, `scripts`, `assets`;
- `scripts` должны быть тонкими утилитами;
- бизнес-логику не добавлять в `scripts`, а выносить в Domain/Infra.

## Что не делаем сейчас

- не создаём физические папки `UI/`, `Domain/`, `Infra/`, `Project/`;
- не переносим проект в `src/`;
- не переписываем импорты;
- не меняем `start_app.py` и `start_console.py`.
