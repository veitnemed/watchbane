# TMDB-1.3d — partial candidate enrichment audit

Это офлайн-аудит происхождения частичной metadata в candidate pool. Он читает
только явно переданную SQLite-копию в `mode=ro` и не запускает refresh,
replenish, ranking, UI или TMDb-запросы.

```powershell
py tools/research/analyze_tmdb_partial_enrichment.py `
  --database "<copied-watchbane.sqlite3>" `
  --output "evidence/tmdb_matrix_1_3d"
```

До и после чтения сверяются SHA-256, размер, mtime и SQLite `data_version`.
Production runtime отвергается. Evidence не содержит названий, TMDb IDs,
identity keys, onboarding-ответов или request parameters.

## Cohorts and verdict

`full` содержит одновременно `runtime`, `content_rating`, `keywords`; `partial`
не содержит ни одного из них; `mixed` содержит часть; `invalid` имеет
некорректный `payload_json`. Для каждой когорты сохраняются только агрегаты
source/version/bucket/profile, timestamps, `details_enriched`, completeness и
SQL/payload conflicts.

Baseline 2026-07-21: `full=30`, `partial=71`, `mixed=0`. Все 101 записи имеют
один onboarding source/version/bucket/profile и одинаковые timestamps. При этом
29 full-record имеют `details_enriched=false`, а 2 partial-record имеют `true`:
этот marker не является доказательством полноты.

Текущий onboarding Details merge и candidate builder не переносят эти три поля.
Значит, partial cohort совместима с текущим onboarding contract, а full cohort
не могла появиться только через его current merge. Verdict: `E — different
acquisition or historical contract`; уверенность сильная для current code,
ограниченная для точного historical writer. Per-Details request audit и writer
version не сохранены, поэтому отсутствие Details-строки не доказывает, что
Details-вызова не было.

Следующая отдельная product-задача: **Ensure Details enrichment contract for
persisted recommendation candidates**.
