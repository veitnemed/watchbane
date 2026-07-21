# Схема tracing snapshot TMDb

`schema.json` — Draft 2020-12 контракт для статического диагностического
снимка. Он не является runtime-моделью Watchbane и не записывается в SQLite.

Каждый snapshot содержит идентификатор, версию приложения/коммита, параметры
исходного запроса и четыре независимых слоя: `raw_api`, `normalized`, `stored`
и `ui_projection`. `stored` всегда разделяет индексированные SQL-колонки,
поля `payload_json` и `meta_json`.

`field_traces` обязателен для каждого зафиксированного поля. В нём для каждого
из четырёх слоёв указывается `state`, `value` и при наличии `source_field`.
Допустимые состояния: `present`, `null`, `empty`, `not_requested`,
`not_applicable`, `request_failed`, `lost_in_normalization`,
`lost_in_storage`, `not_exposed_to_ui`.

Блок `provenance` фиксирует итоговый выбор title, overview, poster,
certification и providers: источник, язык, регион, уровень fallback и причину
выбора. `diagnostics` хранит отдельные typed-наблюдения для adult,
сертификации, происхождения стран, TV runtime, providers и credits.

Схема допускает дополнительные поля ради эволюции исследования, но обязательные
четыре слоя и специальные диагностические блоки остаются стабильным контрактом.
## TMDB-1.3 local export

`not_available_in_local_snapshot` означает, что локальная candidate database
не хранит исходный TMDb response. В таком случае `raw_api` — отдельный marker
availability, а не реконструированный payload. `tmdb_id` допускает `null` для
явно помеченных legacy identities.
