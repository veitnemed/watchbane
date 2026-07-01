# Refactoring Checklist

Короткий чеклист для завершения структурных правок в `Watchbane`.

## Перед правкой

- Убедиться, что рабочее дерево понятно: `git status --short`.
- Найти текущие импорты и публичные вызовы через `rg`, а не менять файл вслепую.
- Если меняется facade (`dataset.service`, `candidates.service`), сначала определить публичные имена, которые должны сохраниться.

## Во время правки

- UI-слои (`ui/console`, `desktop`) могут печатать, спрашивать ввод и показывать сообщения.
- Нижние слои (`storage`, `dataset`, `candidates`, `apis`, `posters`) должны возвращать данные, result-объекты или исключения, а не управлять пользовательским выводом.
- Compatibility wrappers допустимы временно, но новые сценарии должны идти через service/facade API.
- Read-path не должен писать runtime JSON. Write-path должен быть явно назван и покрыт тестом.
- Не переносить ручные scripts в runtime. Если script стал обычным сценарием приложения, доменную логику вынести в активный слой, а script оставить CLI-оберткой.

## Проверки

Минимум для точечной правки:

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest <затронутые тесты>
```

Перед завершением крупного рефакторинга:

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
```

## Красные флаги

- Публичная service-функция импортирует реализацию с тем же именем и вызывает себя.
- Новый код в `ui/console` напрямую пишет JSON или обходит service layer.
- Новый код в `dataset` или `candidates` вызывает `input()`.
- Новый read-only view меняет `data/candidates/pool.json`, `data/watched/titles.json` или `data/watched/meta.json`.
- Тест проходит только при исключении одного файла.
