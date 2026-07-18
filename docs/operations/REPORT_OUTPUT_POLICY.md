# Политика вывода отчётов

Сгенерированные отчёты нельзя писать в активный корень docs. Держите `docs/`
для курируемой долговечной документации и коротких сводок, полезных при обычной
разработке.

## Пути вывода по умолчанию

Используйте эти игнорируемые расположения для сырых/сгенерированных outputs:

| Тип отчёта | Путь вывода |
| --- | --- |
| Onboarding rebuilds и quality runs | `reports/onboarding/` |
| TMDb diagnostics и probes | `reports/tmdb/` |
| UI visual notes, которые не являются скриншотами | `reports/ui/` |
| Storage и SQLite diagnostics | `reports/storage/` или `data/diagnostics/` |
| Network logs и probes | `reports/network/` |
| Общие quality audits | `reports/quality/` |

Скриншоты и visual smoke images кладутся в:

```text
tmp/ui/<task-name>/
```

Сгенерированные export data кладутся в:

```text
data/exports/
```

## Что можно коммитить

Курируемые исторические сводки больше не живут в активном `docs/reports/<topic>/`.
Они перенесены в архив:

```text
internal/archive/docs/reports/
```

Каталог `docs/reports/` содержит только README со ссылкой на этот архив.

Новые курируемые сводки, если их нужно сохранить в репозитории, добавляйте в
`internal/archive/docs/reports/<topic>/` (или обновляйте README в `docs/reports/`,
если меняется указатель). Сводка должна быть короткой и включать:

- дату;
- команду или сценарий;
- ключевой итог;
- известные ограничения;
- ссылку или путь к перегенерируемому сырому output, если это уместно.

Не коммитьте полные сырые dumps, большие JSON payloads, локальные скриншоты,
cache snapshots, логи или разовые audit transcripts.

## Defaults скриптов

Новые report-скрипты должны по умолчанию писать в игнорируемые пути под
`reports/`, `data/diagnostics/`, `data/exports/` или `tmp/ui/`.

Если скрипт поддерживает `--output`, примеры в docs должны использовать
игнорируемые пути. Явно курируемые отчёты не должны целиться в активный
`docs/reports/` как в хранилище содержимого — только в архив или игнорируемые
output-пути.
