# Add Record Rules

Документ фиксирует контракт добавления, обновления и удаления watched-записей в `Watchbane`.

## Главный путь сохранения

Новая watched-запись сохраняется только через service path:

```text
dataset.storage_movie.add_movie(...)
-> dataset.dataset_records.add_dataset_record(...)
```

UI не пишет dataset/meta напрямую. Service path сохраняет через storage compatibility wrappers, которые по умолчанию используют SQLite backend.

## UI-Слой

UI отвечает за:

- ввод пользователя;
- preview перед сохранением;
- подтверждения;
- вывод результата;
- передачу defaults в форму;
- обработку отмены.

UI не отвечает за:

- запись dataset/meta;
- cleanup candidate pool;
- poster-cache side effects;
- прямые API-запросы;
- формат JSON/SQLite.

Relevant files:

- `ui/console/interface_funcs.py`;
- `ui/console/request.py`;
- `desktop/app.py`;
- `desktop/watched/model.py`, `desktop/shared/detail/card.py`.

## Service-Слой

Service отвечает за:

- валидацию payload;
- нормализацию `main_info`, `raw_scores`, `tags_vibe`, `genre`;
- сохранение dataset через SQLite-backed storage;
- сохранение/обновление meta через SQLite-backed storage;
- backup перед опасными операциями;
- best-effort poster-cache sync;
- cleanup candidate pool после переноса кандидата.

Relevant files:

- `dataset/storage_movie.py`;
- `dataset/dataset_records.py`;
- `dataset/delete_record.py`;
- `dataset/title_resolve.py`.

## `add_movie()`

```python
add_movie(
    movie: dict,
    *,
    meta_payload=None,
    pool_candidate=None,
    poster_hints=None,
    print_message: bool = True,
)
```

Правила:

- вызывает `add_dataset_record(...)`;
- принимает optional `meta_payload`;
- принимает optional `pool_candidate`;
- возвращает `AddRecordResult`;
- для UI-сценариев используется `print_message=False`, чтобы финальное сообщение печатал UI.

## `add_dataset_record()`

```python
add_dataset_record(
    record_payload: dict,
    meta_payload=None,
    source_name: str = "",
    pool_candidate=None,
    poster_hints=None,
) -> AddRecordResult
```

Минимальный payload:

- `main_info.title`;
- `main_info.user_score`;
- `main_info.year`;
- `main_info.media_type` (`tv` или `movie`; legacy/empty нормализуется в `tv`);
- `raw_scores`;
- `tags_vibe`;
- `genre`.

После сохранения service:

1. валидирует title/year/user_score;
2. нормализует поля;
3. считает computed fields;
4. сохраняет dataset;
5. сохраняет/обновляет meta;
6. синхронизирует poster-cache best-effort;
7. если передан `pool_candidate`, удаляет watched-кандидата из pool через service cleanup.

## Defaults Для Формы

Defaults собираются через `dataset.title_resolve`.

Источники:

- TMDb TV/Movie;
- candidate pool record.

UI показывает defaults пользователю, но перед сохранением пользователь может изменить **только** `main_info.user_score`.

Название, год, страна, `media_type`, `raw_scores`, жанры и `tags_vibe` берутся из resolve/candidate bundle без override.

Для правки остальных полей уже существующей записи используй `update_dataset_record()`.

## Перенос Candidate -> Watched

Путь:

```text
ui.console.interface_funcs.mark_candidate_as_watched()
-> dataset.title_resolve.build_candidate_transfer_payload(candidate)
-> ui.console.request.request_user_score(defaults)
-> dataset.storage_movie.add_movie(..., pool_candidate=candidate, print_message=False)
```

Правила:

- incomplete-кандидат можно сохранить только после явного UI-warning;
- жанры показываются как preview перед формой;
- cleanup pool выполняет service, не UI.

## Genres

Dataset хранит жанры как `has_*` поля из `config/genre_tags.json`.

Кандидаты могут приходить с:

- `genre_keys`;
- TMDb genres;
- raw labels.

Маппинг выполняется через candidates/dataset helpers, а не вручную в UI.

Новые `has_*` нельзя добавлять по ходу пользовательского сценария. Расширение жанрового каталога - отдельная структурная задача.

## Meta

`meta_payload` может содержать дополнительные поля помимо `main_info` и `raw_scores`.

Типичные поля:

- `tmdb_id`;
- `imdb_id`;
- `kp_id`;
- `description`;
- `source`;
- poster hints.

Service сохраняет дополнительные поля в meta, если они не конфликтуют с базовой структурой.

## Duplicate Policy

Запись не добавляется, если в dataset уже есть объект с тем же нормализованным `title`, `year` и `media_type`.

Legacy-поиск без `year/media_type` сохраняет прежнее title-only поведение для старых API. Если одно название легально существует у разных типов/лет, service создаёт безопасный dataset key с суффиксом, не перезаписывая существующую запись.

Типовой результат:

```python
AddRecordResult(
    ok=False,
    reason="duplicate_title",
)
```

UI печатает человекочитаемое сообщение из result.

## Update Record

Изменение watched-записи выполняется через:

```python
update_dataset_record(title, patch_payload, source_name="") -> UpdateRecordResult
```

Разрешенные patch-поля:

- `main_info.user_score`;
- `main_info.year`;
- `raw_scores`;
- `tags_vibe`;
- `genre`.

Запрещено через patch:

- менять key записи;
- менять `main_info.title`.

Переименование выполняется отдельным путем через `storage.data.rename_movie_title()`, который при SQLite backend обновляет dataset и meta в одной transaction.

## Delete Watched

Удаление выполняется через:

```text
dataset.delete_record.delete_watched_record(dataset_key)
```

Service:

- создает SQLite backup (`*.sqlite3`);
- удаляет запись из dataset;
- удаляет meta;
- чистит poster-cache;
- удаляет локальный poster file best-effort.

Console и desktop используют один service path.

## Generated JSON Policy

В git не добавляются generated preview/snapshot JSON, SQLite DB, WAL/SHM и runtime backups.

Игнорируются:

- `config/rating_comparison_last_snapshot.json`;
- старые legacy metrics/snapshots;
- `data/exports/candidate_pool/`;
- `data/diagnostics/`;
- `data/cache/`.

Активные JSON-справочники в репозитории:

- `config/tags.json`;
- `config/genre_tags.json`;
- `apis/sql_title_aliases.json`.

## Проверки

Для правок add/update/delete:

```powershell
py -m compileall dataset ui desktop storage candidates tests
py -m pytest tests/test_add_title_service.py tests/test_delete_watched_record.py tests/test_smoke.py
```

Для структурных шагов:

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
```
