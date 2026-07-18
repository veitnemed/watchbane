# Участие в разработке

Спасибо, что заглянули в Watchbane.

Проект — local-first и сознательно разделяет UI, доменную логику и storage.

## Настройка

```powershell
py -m pip install -r requirements.txt
py -m pytest
```

Запуск приложения:

```powershell
py start_app.py
```

Консольный UI:

```powershell
py start_console.py
```

## Правила архитектуры

- UI-код живёт в `desktop/`, `ui/`, `web/`, `app/`.
- Доменная логика — в `dataset/`, `candidates/`, `posters/`.
- Инфра — в `apis/`, `storage/`, `config/`, `common/`.
- UI вызывает сервисы и не пишет напрямую в SQLite, legacy JSON или файлы под `data/`.
- Доменные модули не импортируют `desktop`, `ui` или `web`.
- Скрипты остаются тонкими. Переиспользуемую логику выносить в Domain или Infra.

Читать дальше:

- [LOGICAL_ARCHITECTURE.md](../architecture/LOGICAL_ARCHITECTURE.md)
- [PROJECT_MAP.md](../architecture/PROJECT_MAP.md)
- [add_functions.md](add_functions.md)
- [Корневой AGENTS.md](../../AGENTS.md) — вход для агента (продукт, DoD, фазы)
- [PRODUCT_ROADMAP_CONTRACT.md](../contracts/PRODUCT_ROADMAP_CONTRACT.md) — канон продукта и roadmap
- [AGENTS.md](AGENTS.md) — правила слоёв проекта

## Pull Request'ы

Хорошие PR — небольшие и сфокусированные:

- опишите пользовательское изменение;
- укажите затронутые слои;
- добавьте тесты при смене поведения;
- избегайте постороннего форматирования;
- не коммитьте runtime-данные из `data/`, кэши, отчёты и локальные бэкапы.

## Тесты

Для узких правок запускайте точечные тесты.

Для крупных изменений:

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
```

В unit-тестах не должно требоваться реальных внешних сетевых вызовов.
