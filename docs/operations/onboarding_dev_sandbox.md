# Onboarding Dev Sandbox

Дата: 2026-07-08

## Цель

Безопасно повторять first-run onboarding при разработке, не удаляя молча реальные пользовательские данные.

## Явные флаги

- `WATCHBANE_DEV_EMPTY_PROFILE=1`
- `WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START=1`

Оба флага по умолчанию выключены.

## Поведение при старте

`desktop.shell.bootstrap.main()` вызывает `storage.runtime.apply_dev_startup_reset_from_env()` до инициализации runtime.

Если включён любой из флагов:

1. Активный data root копируется в backup под `data/.../backups/dev_startup/`.
2. `WATCHBANE_DEV_EMPTY_PROFILE=1` удаляет активные файлы SQLite DB и legacy runtime JSON.
3. `WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START=1` очищает candidate/onboarding SQLite tables, не очищая watched records.
4. Инициализация runtime заново создаёт SQLite schema и нужные directories.

## Локальный launcher

Для изолированных проверок пересборки pool без затрагивания активного профиля:

```powershell
py scripts\reports\run_onboarding_pool_rebuild.py --mock --all --output reports\onboarding\pool_mock_report.md
py scripts\reports\run_onboarding_pool_rebuild.py --live --all --require-live --output reports\onboarding\pool_live_report.md
```

Scenario runner пишет каждый сценарий во временную SQLite database и не печатает TMDb credentials.

## Режим Console GUI

Для повторных first-run проверок без очистки watched records:

```powershell
py start_console.py
# choose: 7 >> Dev GUI: empty candidate pool on startup
```

Это копирует активный data root в `tmp/dev_gui/empty_candidate_pool/`, запускает `start_app.py` с `WATCHBANE_DATA_DIR`, указывающим на этот изолированный runtime root, и включает `WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START=1`. GUI bootstrap делает backup скопированного data root, очищает там candidate/onboarding tables, затем открывает onboarding flow с нулевым candidate pool, не трогая активный профиль.

## Политика токена

TMDb credentials ищутся в:

- `TMDB_ACCESS_TOKEN`
- `TMDB_TOKEN`
- `TMDB_API_KEY`

Токены никогда не печатаются. `TMDB_API_KEY` отправляется как query `api_key`; access tokens — как Bearer auth.

## Release Note

Dev-флаги только для разработки. Старый helper prompt-pack `.codex-onboarding-fullscreen` удалён; для локальных проверок используйте команды выше. Эти флаги нельзя включать в пользовательских startup-окружениях.
