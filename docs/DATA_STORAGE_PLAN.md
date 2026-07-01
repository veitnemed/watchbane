# Data Storage Plan

Целевая структура локальных данных `Watchbane`.

```text
data/
  watched/
    titles.json
    meta.json
  candidates/
    pool.json
    criteria.json
    watchlist.json
    hidden.json
  cache/
    posters/
    tmdb/
    kp/
  exports/
    candidate_pool/
    edit_dataset.xlsx
  logs/
    api_requests.log
  backups/
```

## Source Of Truth

- `data/watched/titles.json` - пользовательские watched-записи.
- `data/watched/meta.json` - enrichment-данные: external ids, description, poster hints, source/raw metadata.
- `data/candidates/pool.json` - общий candidate pool между запусками.
- `data/candidates/criteria.json` - сохраненные criteria/defaults для pool.

## Runtime Lists

- `data/candidates/watchlist.json` - локальный список “посмотреть позже”.
- `data/candidates/hidden.json` - скрытые кандидаты.

## Cache

- `data/cache/posters/` - poster-cache и локальные изображения.
- `data/cache/tmdb/` - TMDb Discover/Details cache.
- `data/cache/kp/` - KP enrichment cache.

Cache можно удалить без потери watched-базы.

## Generated / Exports

- `data/exports/candidate_pool/` - saved TMDb build JSON/CSV.
- `data/exports/edit_dataset.xlsx` - Excel export/import рабочий файл.
- `data/diagnostics/` - diagnostic reports.
- `data/logs/api_requests.log` - API log.
- `data/backups/` - backups перед изменениями.

Generated файлы не хранятся в git.

## Main Info Country

`main_info.country` хранит страну тайтла в watched-записи.

Правила:

- поле текстовое;
- старые записи без `country` нормализуются как пустая строка;
- add-flow подставляет страну из API/SQL/TMDb/candidate;
- если источник не дал страну, используется страна, выбранная пользователем при поиске;
- `country` не участвует в computed scores.

## Git Policy

В git остаются только справочники проекта:

- `config/tags.json`;
- `config/genre_tags.json`;
- `apis/sql_title_aliases.json`.

Локальные runtime JSON в `data/` игнорируются.
