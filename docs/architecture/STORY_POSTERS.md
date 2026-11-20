# Постеры двухраздельной оболочки — source preview

Scope: только визуальные постеры в Поиске/Коллекции; алгоритм поиска, состояния тайтлов, схема SQLite не меняются. Предыдущий cartoon ZIP/patch сохранены.

## Решение

`desktop/shared/story_posters.py` переиспользует `CandidatePosterPrefetchController` (очередь, дедупликация, cooldown), `preview_poster_path_for_url` (существующий профильный кэш), локальный resolver и `extract_existing_poster_info` через presenter. Старый сетевой путь поддерживает произвольные URL и wsrv proxy; новая оболочка его НЕ вызывает. Старые реализации оставлены.

В новом контроллере только `https://image.tmdb.org/t/p/{size}/{filename}`: size нормализуется в w342, filename — ограниченные ASCII JPEG/PNG/WebP. Query, fragment, credentials, port, traversal, сторонний host и redirect отвергаются. Нет API-запросов, токена, поискового текста, отправки библиотеки или cookie. У CDN при обычном GET видны IP и имя запрошенного изображения. Никаких proxy-fallback со стороны приложения.

Карточка появляется с placeholder сразу. Следующий Qt tick ставит видимые карточки в очередь; прокрутка проверяется каждые 200 мс. Максимум два активных запроса и 40 ожидающих, дедупликация URL. Невидимые элементы не инициируют загрузку. Timeout 8 с, тело максимум 5 МиБ, raster максимум 4096 по каждой стороне и 8 млн пикселей; формат и декодирование проверяются до записи. Qt image decode выполняется на GUI thread с этими ограничениями (не обещаем нулевой CPU overhead).

Запись кэша через уникальный temp, fsync и replace. Кэш общий с прежними preview; новая запись использует канонический w342 URL. Существующий кэш исходного URL переиспользуется локальным resolver. Повреждённый производный файл можно перезапросить; пользовательские записи не редактируются. Кэш не имеет квоты/GC. Права процесса и профиль определяют доступ, шифрования нет.

На смене запроса/перерисовке очищаются ожидания, generation защищает от устаревших ответов. На скрытии/закрытии запросы abort, при возвращении отменённые могут возобновиться. Ошибки сети оставляют placeholder; повтор не чаще следующей активации после cooldown. Weakref и sip.isdeleted защищают удалённые Qt-карточки. Коллекция пока создаёт все карточки, но сеть ленивая.

## Путь метаданных

TMDb details уже предоставляет poster_path/poster_url (`apis/tmdb/client.py`). Pool record сохраняет их. Watchlist/hidden хранят snapshot candidate через существующий title_state_service/action_repository; watched использует существующий transfer payload в movie record. Никакой миграции не нужно. Граничный Qt-тест проверяет извлечение URL из реально сохранённых watchlist и watched записей.

## Проверка и повторение

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/desktop/test_story_posters.py tests/desktop/test_story_quiet_ui.py tests/desktop/test_cartoon_collection.py tests/desktop/test_candidate_poster_prefetch.py -q
.venv/bin/python -m tools.screenshots.capture_story_posters --runtime-root /tmp/watchbane-poster-NEW --output-dir screens/tmp_ui/story-posters/NEW --model-dir ../watchbane-models/multilingual-e5-small-portable --scale 1.25 --live-cdn
```

Каждый capture требует новый временный профиль. `--live-cdn` — явный сетевой smoke одного постера «Интерстеллара» с прямого официального CDN, не тест TMDb API и не оценка каталога. Краткий сюжет написан для smoke самостоятельно. PNG содержит реальный постер, хранится только вне исходного архива. Без флага — авторское демо без постеров. Reopen выполняется с запрещённым network get и проверяет локальный кэш. Model отдельно; скачать её этот скрипт не пытается.

Mock-тесты отдельно проверяют host/redirect/credentials/query, лимиты и abort, битый файл/изображение, размер raster, cache reuse, stale identity, прокрутку и hide, metadata roundtrip. Это не утверждение поведения при всех реальных сетевых отказах.

Linux/PyQt6 проверен. Windows не запускался: вручную распаковать ZIP, выполнить SOURCE_PREVIEW.md, открыть локальный каталог с poster_path, дождаться постера, сохранить, закрыть, отключить сеть, открыть коллекцию; постер должен остаться. Проверить scrolling, 100/125%, закрытие во время скачивания. При недоступном CDN — placeholder, без обхода блокировок.
