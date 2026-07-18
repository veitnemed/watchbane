# Поддержание порядка в workspace

Проект держит generated data и артефакты visual-check вне git. Репозиторий должен оставаться достаточно маленьким для clone и review без локальных кэшей, дампов БД и разовых скриншотов.

## UI-скриншоты

- Закоммиченные product-скриншоты живут в `docs/assets/screens/`.
- Временные UI smoke-скриншоты живут в `tmp/ui/`.
- Файлы в `tmp/ui/` игнорируются и могут быть удалены или перегенерированы.

При проверке desktop UI-изменений держите скриншоты сгруппированными по задаче в
`tmp/ui/tmp_ui_*`, а не создавайте папки `tmp_ui_*` в корне.

## Отчёты

Сгенерированные отчёты относятся к игнорируемым output-папкам, а не к активному
корню `docs/`. Пути по умолчанию для сырых отчётов описаны в
[REPORT_OUTPUT_POLICY.md](REPORT_OUTPUT_POLICY.md).

Используйте `docs/reports/` только как указатель на архив курируемых исторических
сводков (`internal/archive/docs/reports/`). Не коммитьте сырой generated markdown,
JSON dumps, network logs, visual smoke screenshots, cache snapshots или разовые
audit transcripts.

## Крупные локальные артефакты

Эти пути намеренно игнорируются и не должны коммититься:

- `datasets/` — локальные datasets, включая IMDb sqlite databases.
- `data/cache/` — пересобираемые API/cache data.
- `data/backups/` — локальные backup snapshots.
- `data/exports/` — сгенерированные export archives и outputs candidate-pool.
- `data/watchbane.sqlite3*` — локальные runtime-данные SQLite.
- `data/candidates/*.json*` и `data/watched/*.json*` — legacy import/export или старые локальные данные.
- `reports/` и `data/diagnostics/` — сгенерированная диагностика.
- `logs/` — сгенерированные локальные логи.

Публичные desktop и candidate flows — TMDb-only. Локальная IMDb sqlite
database и артефакты KP API не нужны для обычной работы приложения. Если
внутреннему legacy helper нужен `datasets/dataset_sql_light/imdb_light.sqlite3`,
восстановите его локально; не коммитьте.

## Кандидаты на cleanup

Безопасные цели очистки, когда workspace разрастается:

- старые батчи скриншотов `tmp/ui/tmp_ui_*`;
- сырые сгенерированные отчёты в `reports/`;
- сгенерированные release zip в `data/exports/`;
- старые snapshots `pool.before_*.json` после подтверждения, что активный pool валиден;
- пересобираемые файлы TMDb cache в `data/cache/tmdb/`;
- локальные IMDb sqlite databases в `datasets/`.

Не удаляйте `data/watchbane.sqlite3`, если вы намеренно не сбрасываете локальные
данные или не восстановили backup. Legacy JSON-файлы не являются каноническим
runtime storage после перехода на SQLite.
