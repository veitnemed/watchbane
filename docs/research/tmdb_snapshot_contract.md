# TMDb tracing snapshot 1.2

Это диагностический контракт для воспроизводимого аудита пути TMDb-данных. Он
не меняет runtime-модель, ranking, UI, SQLite-схему или TMDb-запросы.

## Состав

- [JSON Schema](../../research/tmdb/schema.json) — Draft 2020-12;
- [описание схемы](../../research/tmdb/schema.md);
- [manifest schema](../../research/tmdb/sample_manifest.schema.json);
- [sample manifest](../../research/tmdb/sample_manifest.json) и три
  детерминированных fixture в `research/tmdb/fixtures/`.

Один snapshot включает metadata/reproducibility: schema version, snapshot и
record ID, TMDb ID, тип медиа, sample group, commit/version приложения, время
и параметры запроса (`endpoint`, язык, регион, append). Все fixtures —
искусственные: они не содержат сетевых ответов или пользовательских данных.

## Четыре слоя

1. `raw_api` — значение и форма TMDb-ответа после указанного запроса.
2. `normalized` — результат существующих extractors/normalizer.
3. `stored` — отдельно `sql_columns`, `payload_fields`, `meta_fields`.
4. `ui_projection` — значение, которое доступно потребителю detail/UI.

`field_traces` описывает каждый traced field во всех слоях. Статус намеренно
отличает отсутствующий запрос, null/пустое значение и техническую потерю между
слоями. Это позволяет фиксировать наблюдение без подмены его исправлением.

## Обязательная provenance

Для `title`, `overview`, `poster`, `certification`, `providers` snapshot
указывает selected value, поле-источник, язык, регион, fallback level и причину
выбора. Специальные typed diagnostics отдельно сохраняют:

- raw/normalized/stored `adult` и loss flags;
- всю доступную certification и выбранную страну;
- `origin_country`, `production_country` и нормализованные страны;
- raw/selected TV runtime и стратегию выбора;
- регион, тип и имена providers, время проверки;
- raw type credits и стратегию извлечения.

## Fixtures

- `movie_watched_refresh_losses.json` документирует текущие потери movie
  certification и credits при watched refresh. `adult` после TMDB-1.1a проходит
  до storage без loss.
- `tv_content_ratings_aggregate_credits.json` покрывает TV content ratings,
  aggregate credits и несколько `episode_run_time`.
- `localization_en_fallback.json` покрывает пустые RU title/overview и
  реализованный английский fallback.

Проверка выполняется офлайн: `py -m pytest tests/test_tmdb_snapshot_schema.py -q`.
## Local pool export

TMDB-1.3 добавляет `not_available_in_local_snapshot`: raw TMDb response не был
сохранён и поэтому не может быть честно восстановлен из normalized или stored
данных. Exporter сохраняет такой marker отдельно в `raw_api`.

Запуск только на копии или isolated runtime:

```powershell
py tools/research/export_tmdb_pool_snapshot.py `
  --database "screens/tmp_ui/TMDB-1.3/watchbane-copy.db" `
  --output "evidence/tmdb_matrix_1_3"
```

## TMDB-1.3b: fresh adult trace

`tools/research/trace_tmdb_adult_propagation.py` создаёт новый изолированный
runtime, затем проверяет `raw Details → normalized candidate → payload_json →
deck eligibility`. В evidence не попадают title, TMDb ID, raw ответ или token:
только `present`/`null`/`lost`, совпадение значений и решение safety gate.

Детерминированные сценарии `adult=true`, `false`, `null` проверяют оба
контура: полный Details normalizer и Discover → Details merge replenish. Один
явно заданный `--movie-id` дополнительно запрашивается у TMDb только при
ручном запуске; pytest его не вызывает. Потеря поля фиксируется в
`failures.json`; слой потери различается как
`normalization_or_detail_merge` либо `storage_normalization_or_persistence`.
Этот audit не исправляет product pipeline.

```powershell
py tools/research/trace_tmdb_adult_propagation.py `
  --runtime-root "tmp/tmdb-1.3b-runtime" `
  --movie-id 550 `
  --output "evidence/tmdb_matrix_1_3b"
```

## TMDB-1.3c: saved-deck safety anomaly

`tools/research/inspect_tmdb_saved_deck_safety.py` читает только явную SQLite
копию и описывает blocked candidate, уже сохранённый в active/reserve. Отчёт
содержит reason code, состояния `adult`/certification/keywords/overview,
текущее deck state и результат rebuild через текущий safety gate. Названия,
TMDb IDs, тексты и identity keys в evidence не записываются. Время попадания
в историческую колоду и версию historical safety gate фиксируются как
`not_reconstructible_from_stored_data`, если их нет в SQLite state.
