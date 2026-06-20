# Правила добавления и изменения записей dataset

Этот файл фиксирует текущий контракт добавления и изменения записей. Он должен отражать реальное поведение кода, а не желаемую архитектуру "на будущее".

## Главный принцип

Новые записи должны сохраняться через существующий безопасный путь:

```python
storage_movie.add_movie(...)
    -> add_dataset_record(...)
```

Нельзя сохранять dataset напрямую из UI-сценариев.

## Слои ответственности

### UI-слой

Файлы:

- [ui/console/interface_funcs.py](../ui/console/interface_funcs.py)
- [ui/console/request.py](../ui/console/request.py)

Отвечает за:

- выбор сценария;
- показ карточек и предупреждений;
- сбор defaults;
- открытие формы подтверждения;
- ручной ввод `user_score`, `raw_scores`, `tags_vibe`, `genre`;
- печать финального сообщения пользователю.

UI не должен молча добавлять запись в dataset.

### Storage / service-слой

Файлы:

- [dataset/storage_movie.py](../dataset/storage_movie.py)
- [dataset/dataset_records.py](../dataset/dataset_records.py)

Отвечает за:

- валидацию payload;
- проверку дублей;
- нормализацию полей;
- создание/обновление meta;
- пересчёт `computed_scores`;
- сохранение dataset;
- очистку candidate pool после успешного добавления;
- возврат структурированного результата.

Storage возвращает `AddRecordResult`, а не управляет UX целиком.

## Текущий контракт `add_movie()`

```python
add_movie(
    movie: dict,
    *,
    meta_payload=None,
    pool_candidate=None,
    print_message: bool = True,
)
```

### Что делает `add_movie()`

- вызывает `add_dataset_record(...)`;
- прокидывает `meta_payload`;
- прокидывает `pool_candidate`;
- по умолчанию может напечатать `result.message`;
- возвращает `AddRecordResult`.

### Что важно сейчас

- для UI-сценариев, где сообщение уже печатается вручную, нужно вызывать `print_message=False`;
- это убирает двойной вывод `Новая запись добавлена!`.

## Текущий контракт `add_dataset_record()`

```python
add_dataset_record(
    record_payload: dict,
    meta_payload=None,
    source_name: str = "",
    pool_candidate=None,
) -> AddRecordResult
```

### Обязательные данные `record_payload`

- `main_info.title`
- `main_info.user_score`
- `main_info.year`
- `raw_scores`
- `tags_vibe`
- `genre`

### Что проверяет service

- валидность `title`;
- дубль по title без учёта регистра;
- валидность `user_score`;
- валидность `year`;
- валидность `raw_scores`;
- валидность `tags_vibe`;
- валидность `genre`;
- полноту итогового набора признаков.

### Что делает при успехе

1. нормализует `main_info`, `raw_scores`, `tags_vibe`, `genre`;
2. собирает `computed_scores`;
3. сохраняет запись в dataset;
4. при необходимости синхронизирует/создаёт meta;
5. очищает candidate pool:
   - если передан `pool_candidate`, удаляет именно его;
   - иначе делает best-effort cleanup просмотренных кандидатов;
6. возвращает `AddRecordResult(ok=True, ..., reason="saved")`.

## Источники добавления новой записи

### 1. Ручное добавление

Путь:

```text
interface_funcs.request_object()
-> request.request_api_defaults(confirm_genres=True)
-> request.request_all_scores(defaults)
-> storage_movie.add_movie(movie_request, print_message=False)
```

Особенности:

- defaults собираются через SQL/API flow;
- перед сохранением всегда открывается форма;
- итоговое сообщение печатает UI.

### 2. Перенос кандидата из пула

Путь:

```text
interface_funcs.mark_candidate_as_watched()
-> title_resolve.build_candidate_transfer_payload(candidate)
-> request.request_all_scores(defaults)
-> storage_movie.add_movie(
       movie_request,
       meta_payload=meta_payload,
       pool_candidate=candidate,
       print_message=False,
   )
```

Особенности:

- запись не добавляется автоматически без формы;
- после успеха кандидат удаляется из общего пула;
- для incomplete-кандидата UI показывает предупреждение, но не блокирует перенос.

## Как TMDb-кандидат превращается в defaults

Логика живёт в:

- [dataset/title_resolve.py](../dataset/title_resolve.py)

`build_candidate_transfer_payload(candidate)` готовит:

- `defaults` для формы;
- `meta_payload` для сохранения meta.

### Для TMDb-кандидата используются common-поля

- `title`
- `year`
- `kp_score`
- `kp_votes`
- `imdb_score`
- `imdb_votes`
- `genres`
- `description`
- `tmdb_id`
- `imdb_id`
- `kp_id`
- `source`

### Заполнение `raw_scores`

В форму должны попадать:

- `kp_score <- candidate["kp_score"]`
- `kp_votes <- candidate["kp_votes"]`
- `imdb_score <- candidate["imdb_score"]`
- `imdb_votes <- candidate["imdb_votes"]`

Если поля нет, оно должно остаться пустым/`None`, а не превращаться в `0`.

## Жанры

Если у кандидата есть `candidate["genres"]`, они используются как defaults.

Нормализация жанров идёт через текущую проектную логику:

- известные жанры маппятся в существующие `has_*`;
- смешанные русские и английские названия проходят через общую нормализацию;
- пользователь всё равно может подтвердить или поправить жанры в форме.

## Meta при добавлении

`meta_payload` может содержать дополнительные поля поверх `main_info` / `raw_scores`.

Сейчас в meta для TMDb-переноса по возможности передаются:

- `tmdb_id`
- `imdb_id`
- `kp_id`
- `description`
- `source`

`add_dataset_record()` сохраняет эти дополнительные поля как extra meta.

## Duplicate policy

Новая запись отклоняется, если в dataset уже есть title с тем же текстом без учёта регистра.

Результат при дубле:

```python
AddRecordResult(
    ok=False,
    message="Ошибка добавления! Такой объект уже добавлен",
    reason="duplicate_title",
)
```

Это важно для callers и тестов: current contract возвращает объект результата, а не `False`.

## Обновление существующей записи

Для patch существующей записи используется:

```python
update_dataset_record(title, patch_payload, source_name="") -> UpdateRecordResult
```

### Разрешено менять

- `main_info.user_score`
- `main_info.year`
- `raw_scores`
- `tags_vibe`
- `genre`

### Запрещено менять через update

- key записи;
- `main_info.title` как способ переименования.

Переименование должно идти отдельным путём через `rename_movie_title()`.

## Excel-правила

Excel-поток сейчас служит для patch существующих записей, а не для создания новых.

Это значит:

- Excel не должен создавать новые записи;
- Excel не должен удалять записи;
- Excel не должен переименовывать записи;
- если набор title не совпадает с dataset, импорт должен останавливаться;
- `raw_scores` patch должен синхронизироваться в meta через update-service.

## Candidate pool cleanup

Текущее правило:

- успешное добавление через перенос кандидата должно удалить кандидата из общего пула;
- для этого caller передаёт `pool_candidate` в `storage_movie.add_movie()`;
- cleanup выполняется в `add_dataset_record()`, а не вручную отдельным UI-шагом после сохранения.

## Печать сообщений

Текущее разделение ответственности:

- service возвращает `AddRecordResult` / `UpdateRecordResult`;
- UI решает, что печатать пользователю;
- для сценариев с ручной печатью нужно использовать `print_message=False`.

Это сохраняет бизнес-логику без изменения, но убирает двойной success-output.
