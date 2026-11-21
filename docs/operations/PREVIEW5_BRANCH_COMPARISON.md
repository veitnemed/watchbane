# WB-005: Preview 5 → рабочая ветка Watchbane

**Статус: PARTIAL.** Отличия и риски пофиксированы по GitHub; одинаковый GUI smoke на двух точных деревьях не запускался. Публикация Preview 6 не возобновлялась.

- [Preview 5](https://github.com/veitnemed/watchbane/releases/tag/story-search-preview.5): тег разрешается в `4ffcf5b16f5ade4a21f57d4ac094ebf5cfa421ea`. Это ZIP с исходниками, не клиентский EXE; в нём нет каталога, весов модели или пользовательских файлов. [Точная памятка](https://github.com/veitnemed/watchbane/blob/story-search-preview.5/SOURCE_PREVIEW.md).
- [Контрольный HEAD](https://github.com/veitnemed/watchbane/commit/e6391ca24abe71b87262b3ca10989056fc2d4761): `e6391ca24abe71b87262b3ca10989056fc2d4761`. [Точный compare](https://github.com/veitnemed/watchbane/compare/story-search-preview.5...e6391ca24abe71b87262b3ca10989056fc2d4761): Preview 5 также merge base, 63 коммита вперёд, 0 назад, 91 изменённый путь. Это не diff с `main`.
- В двух проверенных локальных зеркалах оригинальные удалённые commit objects отсутствуют. Последний чистый `wb-sprint-1121.8iVSPl/watchbane` на локальном `0ef9d75 / 9f0d50…` предшествует e6391ca. В `wb-master-cycle.Cxw9W5/watchbane` есть локальный эквивалент `0259b74` (дерево `6df1f526fc710b875368a1c9890a7d34dd33e810`), но рабочая копия содержит текущие изменения, и для запуска годится только отдельная проверенная выгрузка commit tree. Старый объект Preview 5 в этих зеркалах не найден; не использовать неподтверждённые одноимённые ZIP или старую грязную копию.

## Функциональная матрица

| Что | Preview 5 | e6391ca и доказательство | Риск / приёмка |
|---|---|---|---|
| P0. Профиль и восстановление | Исходный профиль/SQLite backup; новые проверки конкурентного восстановления отсутствуют. | `storage/sqlite/backup.py`, `ui/console/backup_menu.py`, `tests/test_sqlite_backup_restore.py`: проверяемый временный backup, отказ при активной сессии и перенос без подмены открытой исправной базы. Журнал описывает двухпроцессный Linux тест. | Убедиться, что успешный коммит другого процесса виден после открытия; прерванный backup не публикуется. Чистая Windows и внезапное отключение питания не доказаны. Не запускать старый релиз над мигрированным рабочим профилем. |
| P0. Идентичность и оценки | Уже есть typed identity и некоторые тесты тёзок; не приписывать изобретение идентичности новой ветке. | `storage/sqlite/{action_repository,watched_write,watched_meta}.py`, `candidates/title_state_service.py`: защита метаданных/оценок, устаревшего удаления и конфликтной записи IMDb. `tests/test_stale_saved_{removal_identity,write_conflict}.py`, `tests/test_watched_localized_poster_refresh.py`. | Перепроверить старый импорт, тёзок разных типов, Saved/Hidden/Watched после закрытия приложения и отказ без ложного успеха. Для неподтверждённого старого ключа не делать вывод об одинаковых тайтлах. |
| P1. Каталог | Реальный bounded import из TMDb с ключом и ручной локальный JSONL уже существовали. | `candidates/story_catalog.py`, `storage/sqlite/candidate_pool_repository.py`, `desktop/story/view.py`; `tests/test_story_catalog_additive.py`, `tests/desktop/test_story_catalog_flow.py`: конкурентное аддитивное обновление и обработка неудачи/повтора. | Ошибка источника не равна пустому каталогу. Проверить отказ без потери запроса и независимый профиль при одном разрешённом snapshot. Не обещать готовый каталог или коммерческие права. |
| P1. Установка E5 | Выбор готовой папки или отдельная команда; приложение не скачивает веса. | `candidates/story_model_install.py`, `desktop/story/view.py`, `tests/test_story_model_install.py`, `tests/desktop/test_story_model_install_ui.py`: явное согласие, pinned integrity, повтор, неразрушающий repair, idle и общий timeout. | Проверить отказ/повтор после частичной загрузки и сохранение рабочего режима. Hosted установку/repair и exact smoke не складывать в подтверждение клиентского пакета. |
| P1. Поиск и QProcess | E5 и словарный fallback, evidence из синопсиса. | `candidates/story_search.py`, `tests/test_story_narrative_negation.py`, `tests/test_story_relevance_v2.py`: узкая поддержка сюжетного отрицания, больше диагностики. Документированный QProcess остаётся частным экспериментом. | 5/5 свежих вне темы получили карточки; 0/5 назначенных целей были в малом каталоге. Не выводить порог или рост качества из этой выборки; отдельно измерять покрытие, ranking и abstention. |
| P1. Сборка и smoke | Source Preview, с оговоркой ручного Python/модели. | `.github/workflows/{story-source-package,windows-story-smoke,windows-e5-acceptance}.yml`, `start_app.py`, `tools/smoke_windows_e5_install.ps1`, `docs/architecture/WINDOWS_DISTRIBUTION_AUDIT.md`: исходный пакет отдельно от служебной Windows сборки и notice-аудита. | Два Windows Server smoke-профиля на f51319d зелёные ([run](https://github.com/veitnemed/watchbane/actions/runs/44883478264)); это не прогон e6391ca и не клиентский скачиваемый артефакт. Нужны точный архив, чистая Windows, законный реальный каталог и права на весь пакет. |
| P2. Контроль качества | Предыдущие контракты UI. | Последний e6391ca изменяет документацию и два Qt тестовых файла. [Точный журнал](https://github.com/veitnemed/watchbane/blob/e6391ca24abe71b87262b3ca10989056fc2d4761/docs/DEVELOPMENT_LOG.md) сообщает 2 108 / 20 / 2 на Linux; три старых отказа сняты проверками актуальных контрактов, не изменением UI. | Не сравнивать эти числа с Preview 5 без одинакового окружения и списка node IDs; часть baseline требует Windows PowerShell или дополнительного Plotly. |

## Как закрыть оставшуюся часть без риска для профиля

1. Получить тег Preview 5 и e6391ca только в чистый отдельный sandbox (read-only fetch разрешённым GitHub способом либо чистые архивы с подлинным SHA/manifest). Разрешение тега подтвердить снова; для локальных зеркал сверять дерево, а не сходство локальных commit IDs. Не трогать `watchbane-story` или активный мастер-worktree.
2. Сверить Python/Qt/ORT и ОС; использовать один разрешённый immutable JSONL, одну закреплённую FP32 папку и один запрос с подтверждённым ожидаемым тайтлом. Зафиксировать SHA всех входов. Оба точно проверенных скрипта поддерживают следующие **общие** флаги (без head-only `--verify-cached-install` или нового ремонтного режима):

```sh
# Отдельный раз из корня каждого проверенного снапшота; переменные заранее заданы.
# Используйте новый профиль для каждого запуска, не передавайте реальный DB или ключ.
env -u WATCHBANE_STORY_SEED_CATALOG QT_QPA_PLATFORM=offscreen \
  "$QA_PYTHON" -m tools.qa.smoke_story_desktop \
    --catalog "$APPROVED_CATALOG_JSONL" --model-dir "$PINNED_FP32_DIR" \
    --query "$FIXED_RUSSIAN_QUERY" --expected-title "$EXPECTED_TITLE" \
    --qt-platform offscreen
```

Сохранить exit status и факты «поиск → верный тайтл → сохранение → открытие во втором процессе» отдельно для каждого SHA. Если общий smoke проходит, прогнать отдельно head-only негативные проверки (таймаут после прогресса, отказ при конкурентном restore, устаревшая карточка) и не считать их симметричным A/B. Не посылать тестовый запрос внешнему сервису. При отсутствии разрешённого runtime/corpus указать блокер, а не подменять их фиктивными данными.

## Выполненный парный прогон

Деревья `c62ac5f25b2c70a85ca710b5cb5e9e2adfcf83e3` (Preview 5) и `1b379d2369a4122b84891f55b8da91cd222d70de` ([`7b9bcf1`](https://github.com/veitnemed/watchbane/commit/7b9bcf16ef7309012cbabcf47d22ddec3b4a2e09)) сверены с точными GitHub-коммитами. Между ними 64 новых коммита и 94 изменённых пути, общая база Preview 5. Дополнительное изменение после `e6391ca`: проверка содержимого JSONL вместо одного размера и времени; ошибочный файл не оставляет доступными карточки старой версии.

Прогнаны приведённые выше общие флаги, с отдельными чистыми профилями, на одной Linux Qt среде, закреплённой FP32 и одинаковых 50 разрешённых описаниях. Одинаковый запрос про банкирский тоннель на обоих деревьях дал «Побег из Шоушенка» первым, сохранение и повторное открытие прошли. В обеих фазах обоих прогонов ноль незапланированных сетевых обращений. Это один общий сценарий, не статистика улучшения качества, не установка E5 и не прогон входного ZIP на клиентской Windows. Новые веточные риски проверялись отдельно и перечислены в журнале.
