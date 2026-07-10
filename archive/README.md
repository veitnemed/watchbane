# Archive

Здесь лежат неактивные части старой версии проекта. **Новый код сюда не добавлять.**

## Содержимое

- `legacy/model/` — старая ML-модель, обучение, LOO-отчёты и диагностика. Активный runtime больше не импортирует этот код.
- `legacy/apis/` — архивные KP API и IMDb SQL helpers (перенесены из `apis/` после TMDb-only migration).
- `legacy/tests/` — старый монолитный набор (`test.py` ~6000 строк). **Не запускается** в активном pytest (`testpaths = tests`).

Активный pytest-набор: [`tests/`](../tests/).

## Запуск

`archive/legacy/tests/` не собирается `pytest` по умолчанию. Скрипты вроде `apply_genre_tags_from_api.py` и `test_sql_search_all.py` ссылаются на удалённые runtime API и считаются историческими.

Архив нужен как страховка при чистке структуры, не как источник импортов для `app/`, `dataset/`, `desktop/`, `ui/`.
