# Сюжетный поиск: локальный вертикальный срез

Решение владельца 2026-11-19; исходный main `a8ceca2ed13b243112c3a5b2e66ca6548f0b0f7e`.
Это новый основной сценарий, не завершение старой Phase C. История и acceptance Phase C сохранены.
Никакого обучения весов на этом наборе, внешнего inference или платных API.

## Путь пользователя

Главная вкладка «Поиск сюжета» доступна до токена, выбора вкусов и настройки пула.
Первый набор — 30 оригинальных вымышленных историй; это демонстрация механики, не каталог.
Режим «Мои локальные описания» читает имеющийся candidate pool. Для широкого поиска
понадобятся разрешённые описания и отдельный индекс; готового широкого каталога в поставке нет.
E5 подключается кнопкой выбора локальной папки или `WATCHBANE_STORY_MODEL_DIR`.
Без неё явно показывается ограниченный словарный fallback. Ошибка модели не превращается
молча в успешный семантический поиск. Подключение модели — осознанный шаг, не требование токена.

Старые вкладки и title-add поиск сохранены. Новый local adapter использует существующие
identity/filter/safety функции; hidden/watched исключаются до поиска. Сохранение, скрытие
и watched идут через прежние title-state transitions; изменение SQLite schema не требуется.
Демо нельзя сохранить в настоящую библиотеку: скрытие примера живёт только в сессии.
При скрытии удаляется конкретная карточка без refill. Новый явный поиск пересчитывает выдачу.

Карточки используют PlainText, перенос текста, общие scale helpers, источник и дословный
фрагмент текущего описания. Генерации сюжетов или LLM-объяснений нет. Числа similarity не
представляются вероятностью, рейтингом фильма или уверенностью. Выдача называется возможными
совпадениями: порог достоверного отсутствия совпадения на малом наборе не калибровался.

## Архитектура и измеряемые ступени

- `candidates/story_search.py`: DTO, ограничения, чистый offline словарный fallback.
- `candidates/story_lexical.py`: символьный TF-IDF (3–5 символов), без семантического словаря.
- `candidates/story_semantic.py`: E5 tokenizer → attention-mask mean pooling → L2 normalization;
  query/passages используют разные обязательные префиксы. ONNX CPU, 2 intra-op threads.
- Retrieval: top-40 E5 ∪ top-40 текста. Отсутствие слова/понятия не исключает semantic candidate.
- Предварительный default: weighted reciprocal rank fusion `1/(60+r_dense) + .35/(60+r_text)`.
  Это фиксированная эвристика, не обученные веса и не вероятность. Sentence rerank выключен.
  После визуально подтверждённой подмены героя добавлена отдельно измеренная поправка ×1.1/×.9:
  только явное имя роли в запросе и единственная nominative роль в первом предложении.
  Темы «ограбление»/«расследование» не считаются запросом роли. Оба retrieval-сигнала сохраняются.
  Для чистого fusion передать `role_adjustment=False`; в benchmark это отдельная строка.
  Последняя поправка роли прошла local tests; повторный независимый acceptance нужен отдельно.
- Экспериментальный `rerank=True`: .65 full-plot cosine + .25 lead + .10 best sentence;
  мягкая поправка ±.02 для распознанной роли героя. Это не синтаксический парсер и не cross-encoder.
  Он проверяется отдельно и не навязывается: независимая проверка обнаружила деградацию Top-1.
- Выбор подтверждающей фразы работает независимо от порядка. В default он не меняет rank.
- `candidates/story_service.py`: facade adapter для локальных данных и выбора backend.
- `desktop/story/view.py`: QThread read/search, управление состояниями и старые сервисные действия.

Явное «фильм»/«сериал» ограничивает media_type. Если названы оба — ограничения по типу нет.
Год фильтруется только в форме «фильм 2014», «год выпуска 2014», «вышел в 2014» и подобных
поддержанных формах; дата внутри событий сюжета не трактуется автоматически как год выпуска.
Исключения (`без`, `кроме`, `не про`, `исключая` и пр.) отклоняются с сообщением.
Сюжетное «не может вспомнить» допускается. Это ограниченная грамматика, не полноценная логика отрицаний.

Опечатки: text TF-IDF и мягкая коррекция по словарю корпуса; `пристурник` проверен.
Нормализация не является семантическим фильтром. Общие персонажи/темы и перестановки ролей
остаются трудными; контрастные тесты не доказывают полноценное понимание всех ролей.

Encoder cache держит до 4096 passage vectors в RAM. Запросы не кэшируются и не логируются.
Ни embeddings, ни библиотека не отправляются наружу. Модель один раз верифицируется SHA256
при открытии; записи и индекс в этой версии не персистятся. Отдельного сетевого поиска нет.
Длинные тексты обрезаются tokenizer на 512 tokens; chunked retrieval и ANN пока отсутствуют.

## Официальные источники и переносимость

Выбрана именно [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small),
MIT, 384 dimensions. Префиксы, pooling и предел 512 tokens следуют model card.
Артефакты закреплены на `614241f622f53c4eeff9890bdc4f31cfecc418b3`:

| Артефакт | Размер | SHA256 |
| --- | ---: | --- |
| `onnx/model.onnx` FP32 | 470268510 | `ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665` |
| `onnx/model_qint8_avx512_vnni.onnx` dev INT8 | 118346824 | `dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88` |
| `onnx/tokenizer.json` | 17082730 | `0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39` |

Ссылки файлов — в [official ONNX tree](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3/onnx).
FastEmbed рассмотрен: его [документация](https://github.com/qdrant/fastembed) описывает custom E5-small
и автоматически скачивающий constructor. Для прозрачного local-only поведения выбран прямой
ONNX Runtime + tokenizers, без Hub loader/remote code/pickle. Зависимости — `requirements-story.txt`.

Для будущей Windows-сборки выбран обычный FP32 ONNX; VNNI-артефакт остаётся dev-опцией
и отклоняется loader на Windows. Оба артефакта проверены и запущены на Linux CPU.
Это **не** проверка Windows EXE, ноутбука без AVX512 или упаковки optional dependencies.
Веса не входят в git, патч или приложение. Installer исполняется только явно пользователем.

## Данные и воспроизводимость

Синтетические тексты в `story_demo.py` оригинальные, без реальных TMDb ID; относятся к коду
проекта под MIT. Реальные синопсисы не включены в исходники/патч. Для dev smoke обычными GET
прочитаны публичные страницы 12 тайтлов × RU/EN; токен отсутствовал, TMDb API не вызывался.
Каждая запись локального snapshot содержит URL, язык, HTTP status и checksum. Нет обхода 403,
retry через прокси или личной базы. Fetch utility предназначен только для малого explicit smoke.

[TMDb FAQ](https://developer.themoviedb.org/docs/faq) требует attribution для API и разделяет
некоммерческое/коммерческое использование. Этот smoke не даёт разрешения переиздавать
данные; для широкого индекса нужен отдельный проверенный источник/договор. Сырые страницы,
синопсисы, модели и пользовательские данные не публикуются.

Команды (Linux, из checkout; используйте собственные временные каталоги):

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt -r requirements-story.txt
.venv/bin/python -m tools.qa.download_story_model --destination ../watchbane-models/multilingual-e5-small-portable --variant fp32 --accept-download
.venv/bin/python -m tools.qa.fetch_story_tmdb_smoke --output-dir ../watchbane-tmdb-smoke --allow-public-pages
.venv/bin/python -m tools.reports.benchmark_story_models --corpus ../watchbane-tmdb-smoke/corpus.json --model-dir ../watchbane-models/multilingual-e5-small-portable --output screens/tmp_ui/story-search/tmdb-fp32-role-smoke.json
.venv/bin/python -m tools.reports.benchmark_story_search --output screens/tmp_ui/story-search/fallback-benchmark.json
mkdir -p tmp/pytest
QT_QPA_PLATFORM=offscreen PYTEST_QT_API=pyqt6 WATCHBANE_DATA_DIR="$PWD/tmp/qa-profile" WATCHBANE_TEST_MODEL_DIR="$PWD/../watchbane-models/multilingual-e5-small-portable" .venv/bin/python -m pytest tests/test_story_search.py tests/test_story_semantic.py tests/desktop/test_story_flow.py -q
WATCHBANE_DATA_DIR="$PWD/tmp/manual-profile" WATCHBANE_STORY_MODEL_DIR="$PWD/../watchbane-models/multilingual-e5-small-portable" .venv/bin/python start_app.py
```

Без optional зависимостей/весов основной desktop стартует с fallback. Проверки real E5
пропускаются, если не указан `WATCHBANE_TEST_MODEL_DIR`; приложение ничего не скачивает.
Для скрина заменить scale/output на `1.25`/`after_125.png`:

```bash
WATCHBANE_STORY_MODEL_DIR="$PWD/../watchbane-models/multilingual-e5-small-portable" .venv/bin/python -m tools.screenshots.capture_story_search --scale 1 --runtime-root screens/tmp_ui/story-search/runtime100 --output screens/tmp_ui/story-search/after_100.png
```

## Как читать результаты

Сравнение включает text TF-IDF, прежний dictionary fallback, raw E5 без предметных ограничений,
E5 с явными ограничениями, hybrid и экспериментальный plot-rerank на одном корпусе.
Описания RU и EN проверяются отдельно при русских запросах; тип/год одинаковы в сравнимых
ограниченных методах. Queries/labels записаны до E5 прогона TMDb, но автор тот же разработчик:
это **smoke**, не независимая широкая оценка, не обучающий/тестовый split.

Top-1/3, P@5, Recall@5, nDCG@5 и top-10 recall перечислены по группам. P@5 делится на 5
даже если релевантен один тайтл. Метрики бинарные; неполная разметка не считается ground truth
для другого корпуса. `retrieval_recall_at_10` в JSON означает recall первых 10 данного метода;
для rerank это уже reranked top-10, не recall объединённого candidate pool.
Если цель не попала в retrieval top-K при наличии фактов — проверять coverage/representation;
дообучение возможно только на отдельной разметке. Если попала — сначала исследовать fusion/rerank.

CPU latency измеряет поиск без Qt/storage; query embeddings вычисляются на каждом вызове,
passage vectors кэшируются. Индексация и загрузка модели вынесены отдельно. Summary latency —
среднее per-query median/p95, не общий percentile всех запросов. При маленьком числе repeats
p95 не является надёжной tail-оценкой. Масштабирование на большой каталог не доказано.

Независимый ревьюер (сообщение руководителя): на 9 известных сюжетах / 20 настоящих TMDb
описаниях exact lexical Top-3 6/9, Top-1 4/9; E5 9/9 и 7/9; weighted hybrid 9/9 и 9/9;
sentence rerank 9/9 и 7/9. Это внешний результат, не подмена нашего собственного прогона.
В нашем 12-title RU smoke FP32 raw E5 Top-1 14/18, hybrid 12/18, но hybrid Top-3 18/18
против 17/18 у E5. Значит у hybrid есть **регрессия Top-1** на другом малом наборе;
default предварительный, пользу для широкого каталога не объявляем. Веса по этим результатам
не подгонялись. Окончательный выбор default требует расширенного независимого acceptance.

## Оставшиеся риски

- Короткий или бедный synopsis не содержит требуемого факта; embeddings этого не исправят.
- Нет надёжного порога отказа, готового широкого индекса, логического negative filtering.
- Близкие тропы и роли (участник преступления / следователь) могут смешиваться.
- Простой TF-IDF/RRF может ухудшить первый результат, sentence-rerank также регрессирует.
- UI в новом сценарии ориентирован на русский; старые интерфейсные языки не переписаны.
- Cold start FP32, память, 512-token truncation, многотысячные корпуса и shutdown во время
  большой индексации требуют дополнительных проверок; модельные batch не прерываются мгновенно.
- Windows EXE, CPU ноутбука, реальный TMDb API и пользовательские данные не проверялись.


## Следующий измеримый этап: подтверждение условий сюжета

Независимый следующий smoke руководителя: 9 коротких запросов, заранее зафиксированных до
поиска; 39 новых русских описаний из top-rated movie / popular TV, без дублей старого набора.
Сообщены полезные ответы («врач в больнице» → «Доктор Хаус»), но и ложные соответствия:
«ограбление банка» → спасение заложника, «семейная тайна» → ситком без тайны в описании,
тюрьма без побега высоко по запросу побега. Сырые результаты не копировались в репозиторий.
Это подтверждает ограничение similarity. Отдельно размечать для независимых query-document
пар: (1) поддержан герой, (2) поддержано действие, (3) поддержан конфликт, (4) отсутствуют
данные / есть противоречие. Измерять event-supported Precision@5 и failure types, сохраняя
retrieval Recall@K. Не обучать/калибровать на этих же проверочных примерах и не создавать
правила под тайтлы. Текущая UI-цитата называется «Из описания», а не доказательством совпадения.
До этого этапа нельзя объявлять сюжетный acceptance закрытым или выпускать готовый каталог.

## Source preview amendment, 2026-11-19

После независимой проверки владелец одобрил пробную сборку без ожидания идеального rerank. Default теперь чистый RRF (role_adjustment=False): короткие тематические запросы не требуют доказательства центральной роли. Предыдущие измерения role/sentence вариантов выше остаются историей, не результатами нового default. Выдержки извлекаются только для финальных карточек; это не entailment и не confidence.

Созданы `preview.py`, `Start-Preview.cmd`, `requirements-preview.txt`, `SOURCE_PREVIEW.md`. По умолчанию отдельный профиль, автоматический выбор существующего локального каталога. Один сессионный индекс переиспользуется по неизменному набору документов и пути модели; явное обновление/смена документов инвалидирует его. Ввод во время поиска открыт, последний следующий запрос ставится в очередь. Отмена между ONNX batch; дискового cache нет. Отдельный долг — `STORY_SEARCH_DEBT.md`.

V1 сохранён внешней неизменной копией `watchbane-story-v1-verified.patch`, SHA256 `11075c824f899cb0f6fe8eeb47ce65956d30a2a3e08d840d92f0782d11613bd8`. Preview передаётся отдельным патчем и исходным zip, без весов и корпусов. История старой Phase C не удалена.

## Increment after source preview: profile vector cache

A subsequent owner-authorized increment adds reusable passage vectors within the active profile, preserving ranking. Earlier statements about no on-disk cache describe the immutable original preview. Identity, format, atomic updates, privacy/retention, measured fresh-process timings and unexecuted Windows checklist: [STORY_VECTOR_CACHE](STORY_VECTOR_CACHE.md). Original ZIP and patch are unchanged; this is a separate patch.
