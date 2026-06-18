"""Проверяет основные сценарии работы проекта на временных данных."""

import contextlib
import io
import tempfile
from pathlib import Path
import sys
from unittest.mock import patch
from urllib.error import HTTPError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import constant
from common import format_score
from model import model
from model import linear_regression_train
from data_work import storage
from data_work import excel_work
from data_work import candidate_pool
from data_work import sql_search
from data_work import title_resolve
from ui import request as request_ui
from apis import api
from common import valid


def show_check(text: str, result: bool) -> None:
    """Печатает результат проверки."""
    print(f"{text}: {result}")


def assert_check(text: str, result: bool) -> None:
    """Проверяет условие и останавливает тест при ошибке."""
    show_check(text, result)
    assert result, text


def make_movie(title="Test Movie", user_score=8.0, raw_score=8.0) -> dict:
    """Создает тестовый объект фильма."""
    tags_vibe = {feature: 0 for feature in constant.TAGS_VIBE}
    genre_tags = {feature: 0 for feature in constant.GENRE}
    for feature in ["has_crime", "has_psychology", "has_romantic_pursuit"]:
        if feature in tags_vibe:
            tags_vibe[feature] = 1
    for feature in ["has_drama", "has_crime"]:
        if feature in genre_tags:
            genre_tags[feature] = 1

    return {
        "main_info": {
            "title": title,
            "user_score": user_score,
            "year": 2024
        },
        "raw_scores": {
            "kp_score": raw_score,
            "kp_votes": 120000,
            "imdb_score": raw_score,
            "imdb_votes": 1200
        },
        constant.TAGS_VIBE_SECTION: tags_vibe,
        constant.GENRE_SECTION: genre_tags
    }


def setup_temp_project():
    """Готовит временный проект для тестов."""
    temp_dir = tempfile.TemporaryDirectory()
    root = Path(temp_dir.name)

    old_paths = {
        "DATA_DIR": constant.DATA_DIR,
        "FILE_NAME": constant.FILE_NAME,
        "WEIGHTS_JSON": constant.WEIGHTS_JSON,
        "CRITERIA_POOL_JSON": constant.CRITERIA_POOL_JSON,
        "CANDIDATE_POOL_JSON": constant.CANDIDATE_POOL_JSON,
        "BACKUP_DIR": constant.BACKUP_DIR,
        "DIR_META": constant.DIR_META,
        "META_JSON": constant.META_JSON,
    }

    constant.DATA_DIR = str(root / "data")
    constant.FILE_NAME = str(root / "data" / "dataset.json")
    constant.WEIGHTS_JSON = str(root / "data" / "weights.json")
    constant.CRITERIA_POOL_JSON = str(root / "data" / "candidate_criteria.json")
    constant.CANDIDATE_POOL_JSON = str(root / "data" / "candidate_pool.json")
    constant.BACKUP_DIR = str(root / "backup") + "/"
    constant.DIR_META = str(root / "meta")
    constant.META_JSON = str(root / "meta" / "meta_data.json")

    storage.init_dataset()
    storage.init_meta()
    storage.init_weights()

    return temp_dir, old_paths


def restore_project_paths(temp_dir, old_paths: dict) -> None:
    """Возвращает реальные пути после тестов."""
    for name, value in old_paths.items():
        setattr(constant, name, value)
    temp_dir.cleanup()


def test_files_created() -> None:
    """Проверяет создание рабочих файлов."""
    print("\n1) Проверяем создание файлов")
    assert_check("Файл dataset.json открывается", Path(constant.FILE_NAME).exists())
    assert_check("Файл meta_data.json открывается", Path(constant.META_JSON).exists())
    assert_check("Файл weights.json открывается", Path(constant.WEIGHTS_JSON).exists())
    assert_check("Dataset изначально пустой", storage.load_dataset() == {})
    assert_check("Meta изначально пустая", storage.load_meta() == {})


def test_add_new_movie() -> None:
    """Проверяет добавление фильма."""
    print("\n2) Проверяем добавление новой записи")
    movie = make_movie()

    assert_check("Запись добавляется", storage.add_movie(movie))

    dataset = storage.load_dataset()
    meta = storage.load_meta()

    assert_check("В dataset появилась 1 запись", len(dataset) == 1)
    assert_check("Title сохранен в dataset", dataset["Test Movie"]["main_info"]["title"] == "Test Movie")
    assert_check("Title сохранен в meta", "Test Movie" in meta)
    assert_check("В dataset нет постоянного поля features", "features" not in dataset["Test Movie"])
    assert_check("Features собраны полностью", set(model.get_features(dataset["Test Movie"])) == set(constant.FEATURES))
    assert_check("Raw-поля в dataset совпадают с meta", dataset["Test Movie"]["raw_scores"] == meta["Test Movie"]["raw_scores"])


def test_meta_overrides_raw_scores() -> None:
    """Проверяет приоритет raw-данных из meta."""
    print("\n3) Проверяем приоритет meta")
    storage.clean_dataset()

    first_movie = make_movie(title="Known Movie", raw_score=9.0)
    assert_check("Первая запись создает meta", storage.add_movie(first_movie))
    storage.clean_dataset()

    second_movie = make_movie(title="Known Movie", raw_score=1.0)
    changed_tag = constant.TAGS_VIBE[0] if constant.TAGS_VIBE else None
    if changed_tag is not None:
        second_movie[constant.TAGS_VIBE_SECTION][changed_tag] = 1

    assert_check("Повторная запись с тем же title добавляется в пустой dataset", storage.add_movie(second_movie))

    saved_movie = storage.load_dataset()["Known Movie"]
    assert_check("Raw kp_score взят из meta, а не из нового ввода", saved_movie["raw_scores"]["kp_score"] == 9.0)
    if changed_tag is not None:
        assert_check("Tag взят из нового ввода", saved_movie[constant.TAGS_VIBE_SECTION][changed_tag] == 1)


def test_duplicate_rejected() -> None:
    """Проверяет запрет дублей."""
    print("\n4) Проверяем запрет дублей")
    storage.clean_dataset()
    movie = make_movie(title="Duplicate Movie")

    assert_check("Первая запись добавляется", storage.add_movie(movie))

    with contextlib.redirect_stdout(io.StringIO()):
        second_result = storage.add_movie(movie)

    assert_check("Повторная запись не добавляется", second_result.ok is False)
    assert_check("Причина отказа - дубль title", second_result.reason == "duplicate_title")
    assert_check("В dataset осталась 1 запись", len(storage.load_dataset()) == 1)


def test_feature_formatting() -> None:
    """Проверяет расчет признаков."""
    print("\n5) Проверяем расчет признаков")
    raw_scores = make_movie()["raw_scores"]
    movie = make_movie()
    computed = format_score.raw_to_struct(raw_scores, movie["main_info"])
    movie["computed_scores"] = computed

    assert_check("Computed содержит все ожидаемые ключи", set(computed) == set(constant.COMPUTED_SCORES))
    movie_features = model.get_features(movie)
    assert_check("Bias входит в признаки модели", movie_features[constant.BIAS_FEATURE] == 1.0)
    assert_check("kp_score переносится без изменений", computed["kp_score"] == raw_scores["kp_score"])
    assert_check("imdb_score переносится без изменений", computed["imdb_score"] == raw_scores["imdb_score"])
    assert_check("imdb_popularity находится от 0 до 10", 0 <= computed["imdb_popularity"] <= 10)
    assert_check("CSV-схема содержит genre-поля", all(feature in constant.CSV_FIELDS for feature in constant.GENRE))


def test_excel_row_supports_genre() -> None:
    """Проверяет, что Excel-строка включает genre-поля."""
    print("\n5.1) Проверяем Excel-схему с жанрами")
    movie = make_movie()
    row = excel_work.build_row(movie)

    assert_check("Число значений в строке совпадает с CSV-схемой", len(row) == len(constant.CSV_FIELDS))
    if len(constant.GENRE) > 0:
        genre_feature = constant.GENRE[0]
        genre_index = constant.CSV_FIELDS.index(genre_feature)
        assert_check("Genre-поле попадает в Excel-строку", row[genre_index] == movie[constant.GENRE_SECTION][genre_feature])


def test_excel_title_guard() -> None:
    """Проверяет, что Excel не может добавлять, удалять или переименовывать записи."""
    print("\n5.2) Проверяем защиту title при Excel-импорте")
    dataset = {
        "Excel A": make_movie("Excel A"),
        "Excel B": make_movie("Excel B"),
    }
    same_titles = [make_movie("Excel A"), make_movie("Excel B")]
    renamed_title = [make_movie("Excel A renamed"), make_movie("Excel B")]
    missing_title = [make_movie("Excel A")]

    assert_check("Excel с тем же набором title проходит", excel_work.validate_excel_titles(same_titles, dataset))
    assert_check(
        "Excel с переименованной записью останавливается",
        excel_work.validate_excel_titles(renamed_title, dataset) is False,
    )
    assert_check(
        "Excel с удалённой строкой останавливается",
        excel_work.validate_excel_titles(missing_title, dataset) is False,
    )


def test_validation() -> None:
    """Проверяет валидаторы."""
    print("\n6) Проверяем валидацию")
    assert_check("Корректный title проходит", valid.is_correct_title("Good Title"))
    assert_check("Пустой title не проходит", valid.is_correct_title("") is False)
    assert_check("Оценка 8.5 проходит", valid.is_correct_score("8.5"))
    assert_check("Оценка 11 не проходит", valid.is_correct_score("11") is False)
    assert_check("Год 2024 проходит", valid.is_correct_year("2024"))
    assert_check("Год 1999 не проходит", valid.is_correct_year("1999") is False)
    assert_check("100 голосов проходит", valid.is_correct_votes("100"))
    assert_check("-1 голосов не проходит", valid.is_correct_votes("-1") is False)


def test_tag_compatibility() -> None:
    """Проверяет совместимость тегов."""
    expected_tags = constant.TAGS_VIBE
    old_tags = {
        "has_crime": 1,
        "has_psyhology": 1,
        "has_comedy": 0,
        "has_mystic": 1,
        "has_romantic_tension": 1,
    }
    normalized = storage.normalize_tags_vibe(old_tags)

    assert_check("Tag order matches the new scheme", constant.TAGS_VIBE == expected_tags)
    assert_check("Legacy tags are removed after migration", list(normalized) == expected_tags)
    assert_check("Missing active tags default to zero", all(feature in normalized for feature in constant.TAGS_VIBE))
    if constant.TAGS_VIBE:
        changed_tag = constant.TAGS_VIBE[0]
        assert_check("Invalid binary tag is rejected", storage.is_valid_tags_vibe({**normalized, changed_tag: 2}) is False)


def test_training() -> None:
    """Проверяет обучение модели."""
    print("\n7) Проверяем обучение модели")
    if linear_regression_train.is_method_available("mae_scipy") is False:
        print("SKIP: scipy minimize (MAE) недоступен в текущем окружении.")
        return
    storage.clean_dataset()

    movies = [
        make_movie("A", user_score=8.0, raw_score=8.0),
        make_movie("B", user_score=5.0, raw_score=5.0),
        make_movie("C", user_score=9.0, raw_score=9.0),
    ]
    for movie in movies:
        assert_check(f"Запись {movie['main_info']['title']} добавляется", storage.add_movie(movie))

    data = storage.load_dataset()
    start_error = model.mean_absolute_error(data, constant.DEFAULT_WEIGHTS)
    new_weights = linear_regression_train.fit_linear_weights(
        data=data,
        method="mae_scipy",
        start_weights=constant.DEFAULT_WEIGHTS,
        alpha=0.1,
        l1_ratio=0.5,
        max_iter=500,
    )
    new_error = model.mean_absolute_error(data, new_weights)

    show_check("MAE до обучения", round(start_error, 4))
    show_check("MAE после обучения", round(new_error, 4))
    assert_check("Новые веса содержат все признаки", set(new_weights) == set(constant.FEATURES))
    assert_check("MAE не увеличилась", new_error <= start_error)


def test_backup_restore() -> None:
    """Проверяет восстановление датасета из backup."""
    print("\n9) Проверяем восстановление backup")
    storage.clean_dataset()

    first_movie = make_movie("Backup A", user_score=7.0, raw_score=7.0)
    second_movie = make_movie("Backup B", user_score=9.0, raw_score=9.0)

    assert_check("Первая запись добавляется", storage.add_movie(first_movie))
    storage.create_backup()
    backup_path = storage.get_latest_backups(1)[0]

    assert_check("Вторая запись добавляется", storage.add_movie(second_movie))
    assert_check("В датасете временно 2 записи", len(storage.load_dataset()) == 2)

    records_count = storage.restore_backup(backup_path)
    data = storage.load_dataset()

    assert_check("Backup восстановил 1 запись", records_count == 1)
    assert_check("Первая запись осталась", "Backup A" in data)
    assert_check("Вторая запись исчезла после восстановления", "Backup B" not in data)


def test_api_fallback_to_secondary_token() -> None:
    """Проверяет переход на резервный API-ключ после HTTP 403."""
    print("\n10) Проверяем fallback на второй API-ключ")

    old_secondary = api.SECONDARY_TOKEN
    api.SECONDARY_TOKEN = "secondary-token"

    class FakeResponse:
        def __init__(self, payload: str):
            self.payload = payload.encode("utf-8")
            self.status = 200

        def read(self):
            return self.payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    calls = []

    def fake_opener(request, timeout=20):
        calls.append(request.headers.get("X-api-key"))
        if len(calls) == 1:
            raise HTTPError(request.full_url, 403, "Forbidden", hdrs=None, fp=None)
        return FakeResponse('{"docs": [{"id": 1}]}')

    try:
        result = api.fetch_json(
            "https://example.test/api",
            token="primary-token",
            opener=fake_opener,
            retries=0,
        )
    finally:
        api.SECONDARY_TOKEN = old_secondary

    assert_check("Первый запрос ушёл с основным ключом", calls[0] == "primary-token")
    assert_check("Второй запрос ушёл с резервным ключом", calls[1] == "secondary-token")
    assert_check("Ответ успешно получен через резервный ключ", result["ok"] is True)


def test_sql_title_search() -> None:
    """Проверяет поиск тайтла в локальной SQLite-базе."""
    print("\n11) Проверяем поиск тайтла в SQL")

    result = sql_search.search_title_in_sql("Триггер", "Россия")

    assert_check("SQL-поиск возвращает ok", result["ok"] is True)
    assert_check("Вернулся словарь с данными", isinstance(result["data"], dict))
    assert_check("Есть название", bool(result["data"].get("title")))
    assert_check("Есть год", result["data"].get("year") is not None)
    assert_check("Есть жанры", isinstance(result["data"].get("genres"), list))
    assert_check("Есть рейтинг", result["data"].get("imdb_rating") is not None)
    assert_check("Есть голоса", result["data"].get("imdb_votes") is not None)
    assert_check("Есть режиссеры или актеры", bool(result["data"].get("credits", {}).get("directors") or result["data"].get("credits", {}).get("actors")))


def test_sql_title_search_aliases() -> None:
    """Проверяет сложные и опечатанные названия для SQL-поиска."""
    print("\n11.1) Проверяем алиасы и опечатки SQL-поиска")

    checks = [
        ("Чернобыль зона отчуждения", "Chernobyl: Zone of Exclusion"),
        ("Haappy End", "Happy End"),
        ("Индентификация", "Identification"),
        ("Фишшер", "Fisher"),
        ("Я знаю кто тебя убил", "YA znayu, kto tebya ubil"),
    ]

    for query, expected_title in checks:
        result = sql_search.search_title_in_sql(query, "Россия")
        assert_check(f"SQL-поиск находит {query}", result["ok"] is True)
        assert_check(
            f"SQL-поиск приводит {query} к ожидаемому тайтлу",
            result["data"].get("title") == expected_title
        )

    alias_result = sql_search.search_title_in_sql("Haappy End", "Россия")
    assert_check(
        "В match сохраняется информация о ручном alias",
        bool(alias_result["data"].get("match", {}).get("alias_applied"))
    )


def test_build_api_defaults_from_raw_movie() -> None:
    """Проверяет сбор defaults из сырого ответа API."""
    print("\n11.2) Проверяем build_api_defaults на сыром API-объекте")

    movie = {
        "name": "Тестовый сериал",
        "alternativeName": "Test Series",
        "year": 2025,
        "rating": {"kp": 7.4, "imdb": 6.9},
        "votes": {"kp": 12345, "imdb": 678},
        "genres": [{"name": "драма"}, {"name": "триллер"}],
    }

    defaults = title_resolve.build_api_defaults(movie)

    assert_check("Название берётся из raw API name", defaults["main_info"]["title"] == "Тестовый сериал")
    assert_check("Год берётся из raw API", defaults["main_info"]["year"] == 2025)
    assert_check("KP рейтинг извлекается из rating.kp", defaults["raw_scores"]["kp_score"] == 7.4)
    assert_check("IMDb рейтинг извлекается из rating.imdb", defaults["raw_scores"]["imdb_score"] == 6.9)
    assert_check("Жанры размечаются в defaults", sum(defaults["genre"].values()) >= 2)


def test_merge_defaults_prefers_api_and_keeps_sql() -> None:
    """Проверяет объединение SQL и API defaults."""
    print("\n11.3) Проверяем merge_defaults для SQL + API")

    sql_defaults = {
        "main_info": {"title": "Trigger", "user_score": None, "year": 2018},
        "raw_scores": {"kp_score": None, "kp_votes": None, "imdb_score": 7.7, "imdb_votes": 4321},
        "tags_vibe": {},
        "genre": {"has_drama": 1, "has_thriller": 1},
    }
    api_defaults = {
        "main_info": {"title": "Триггер", "user_score": None, "year": 2018},
        "raw_scores": {"kp_score": 8.0, "kp_votes": 55555, "imdb_score": 7.6, "imdb_votes": 4000},
        "tags_vibe": {},
        "genre": {"has_drama": 1, "has_detective": 1},
    }

    merged = title_resolve.merge_defaults(sql_defaults, api_defaults)

    assert_check("Название берётся из API как более пользовательское", merged["main_info"]["title"] == "Триггер")
    assert_check("KP приходит из API", merged["raw_scores"]["kp_score"] == 8.0)
    assert_check("IMDb остаётся заполненным", merged["raw_scores"]["imdb_score"] == 7.6)
    assert_check("Жанр из SQL сохраняется", merged["genre"]["has_thriller"] == 1)
    assert_check("Жанр из API добавляется", merged["genre"]["has_detective"] == 1)


def test_build_genre_defaults_ignores_unknown() -> None:
    """Проверяет, что неизвестные жанры не создают новые feature в обычном потоке."""
    print("\n11.4) Проверяем, что новые жанры не автодобавляются в модель")

    defaults = title_resolve.build_genre_defaults(["комедия", "future-micro-genre-x", "драма"])

    assert_check("Известный жанр комедия размечается", defaults.get("has_comedy") == 1)
    assert_check("Известный жанр драма размечается", defaults.get("has_drama") == 1)
    assert_check("Неизвестный жанр не включается в defaults", "has_future_micro_genre_x" not in defaults)


def test_manual_add_defaults_when_lookup_fails() -> None:
    """Проверяет ручной fallback, если SQL/API ничего не нашли."""
    print("\n11.5) Проверяем ручной fallback добавления")
    resolved = {
        "title": "Manual Missing Title",
        "country": "Россия",
        "sql_result": {"ok": False, "details": "not_found"},
        "sql_data": None,
        "api_data": None,
        "api_error": {"ok": False, "error": "network_error", "details": "timeout"},
        "defaults": None,
        "found": False,
    }

    output = io.StringIO()
    with patch("ui.request.title_resolve.resolve_title_data_for_add", return_value=resolved):
        with patch("builtins.input", return_value="y"):
            with contextlib.redirect_stdout(output):
                defaults = request_ui.resolve_title_for_training("Manual Missing Title", confirm_genres=True)

    assert_check("Fallback возвращает defaults", defaults is not None)
    assert_check("Title берётся из ручного ввода", defaults["main_info"]["title"] == "Manual Missing Title")
    assert_check("KP score остаётся пустым", defaults["raw_scores"]["kp_score"] is None)
    assert_check("Vibe defaults заполнены по схеме", set(defaults["tags_vibe"]) == set(constant.TAGS_VIBE))
    assert_check("Genre defaults заполнены по схеме", set(defaults["genre"]) == set(constant.GENRE))
    assert_check("Печатается режим ручной разметки", "Режим: ручная разметка" in output.getvalue())


def test_add_resolver_prioritizes_sql_and_kp() -> None:
    """Проверяет приоритет SQL для IMDb и KP API для KP/жанров/описания."""
    print("\n11.6) Проверяем приоритеты источников SQL + KP API")
    sql_data = {
        "title": "SQL Title",
        "original_title": "SQL Original",
        "year": 2022,
        "genres": ["триллер"],
        "imdb_rating": 7.7,
        "imdb_votes": 12345,
    }
    kp_data = {
        "name": "KP Title",
        "year": 2024,
        "rating": {"kp": 8.1, "imdb": 6.1},
        "votes": {"kp": 5000, "imdb": 100},
        "genres": [{"name": "драма"}],
        "description": "KP description",
    }

    with patch("data_work.title_resolve.sql_search.search_title_in_sql", return_value={"ok": True, "data": sql_data}):
        with patch("data_work.title_resolve.api.find_series_raw", return_value={"ok": True, "data": kp_data}):
            resolved = title_resolve.resolve_title_data_for_add("Input Title")

    defaults = resolved["defaults"]
    assert_check("Title берётся из KP API", defaults["main_info"]["title"] == "KP Title")
    assert_check("Год берётся из KP API", defaults["main_info"]["year"] == 2024)
    assert_check("IMDb rating берётся из SQL", defaults["raw_scores"]["imdb_score"] == 7.7)
    assert_check("KP rating берётся из KP API", defaults["raw_scores"]["kp_score"] == 8.1)
    assert_check("Источник IMDb зафиксирован как SQL", resolved["sources"]["imdb_score"] == "imdb_sql")
    assert_check("Источник жанров зафиксирован как KP API", resolved["sources"]["genres"] == "kp_api")
    assert_check("TMDb не вызывается при успешном KP", resolved["statuses"]["tmdb_api"] == "не найдено")


def test_add_resolver_uses_tmdb_when_kp_fails() -> None:
    """Проверяет fallback на TMDb для жанров/описания, без подстановки KP/IMDb оценок."""
    print("\n11.7) Проверяем fallback на TMDb при падении KP API")
    sql_data = {
        "title": "SQL Title",
        "original_title": "SQL Original",
        "year": 2021,
        "genres": ["триллер"],
        "imdb_rating": 7.5,
        "imdb_votes": 2222,
    }
    tmdb_details = {
        "id": 10,
        "name": "TMDb Title",
        "original_name": "TMDb Original",
        "first_air_date": "2023-01-01",
        "genres": [{"name": "драма"}],
        "overview": "TMDb overview",
        "external_ids": {},
        "credits": {},
    }

    with patch("data_work.title_resolve.sql_search.search_title_in_sql", return_value={"ok": True, "data": sql_data}):
        with patch("data_work.title_resolve.api.find_series_raw", return_value={"ok": False, "error": "network_error", "details": "timeout"}):
            with patch("data_work.title_resolve.api_tmdb.search_tv_by_name", return_value=[{"id": 10, "name": "TMDb Title", "vote_count": 10}]):
                with patch("data_work.title_resolve.api_tmdb.get_tv_details", return_value=tmdb_details):
                    resolved = title_resolve.resolve_title_data_for_add("Input Title")

    defaults = resolved["defaults"]
    assert_check("KP API отмечен как ошибка", resolved["statuses"]["kp_api"] == "ошибка")
    assert_check("TMDb найден", resolved["statuses"]["tmdb_api"] == "найдено")
    assert_check("IMDb остаётся из SQL", defaults["raw_scores"]["imdb_score"] == 7.5)
    assert_check("KP score не берётся из TMDb", defaults["raw_scores"]["kp_score"] is None)
    assert_check("Жанры берутся из TMDb, если KP не сработал", resolved["sources"]["genres"] == "tmdb_api")
    assert_check("Описание берётся из TMDb", resolved["sources"]["description"] == "tmdb_api")


def test_add_resolver_offline_without_sql_is_manual() -> None:
    """Проверяет, что полный offline/no-match сценарий остаётся ручным."""
    print("\n11.8) Проверяем полный offline/manual сценарий resolver-а")

    with patch("data_work.title_resolve.sql_search.search_title_in_sql", return_value={"ok": False, "details": "not_found"}):
        with patch("data_work.title_resolve.api.find_series_raw", return_value={"ok": False, "error": "network_error", "details": "timeout"}):
            with patch("data_work.title_resolve.api_tmdb.search_tv_by_name", side_effect=RuntimeError("offline")):
                resolved = title_resolve.resolve_title_data_for_add("Manual Only")

    assert_check("Ничего не найдено", resolved["found"] is False)
    assert_check("Defaults не создаются до согласия пользователя", resolved["defaults"] is None)
    assert_check("SQL не найден", resolved["statuses"]["sql"] == "не найдено")
    assert_check("KP API ошибка", resolved["statuses"]["kp_api"] == "ошибка")
    assert_check("TMDb API ошибка", resolved["statuses"]["tmdb_api"] == "ошибка")


def test_remove_candidate_from_pool() -> None:
    """Проверяет удаление просмотренного кандидата из общего пула по совпадающему названию и году."""
    print("\n12) Проверяем удаление просмотренного кандидата из пула")

    candidate_pool.save_candidate_pool({
        "one": {
            "title": "Ева, рожай!",
            "alternative_title": "",
            "year": 2022,
            "criteria_name": "A",
            "kp_score": 7.0,
            "kp_votes": 1000,
            "imdb_score": 0,
            "imdb_votes": 0,
            "genres": ["комедия"],
        },
        "two": {
            "title": "Ева рожай",
            "alternative_title": "",
            "year": 2022,
            "criteria_name": "B",
            "kp_score": 8.0,
            "kp_votes": 2000,
            "imdb_score": 0,
            "imdb_votes": 0,
            "genres": ["комедия"],
        },
        "three": {
            "title": "Другой сериал",
            "alternative_title": "",
            "year": 2022,
            "criteria_name": "A",
            "kp_score": 8.0,
            "kp_votes": 500,
            "imdb_score": 0,
            "imdb_votes": 0,
            "genres": ["драма"],
        },
    })

    removed = candidate_pool.remove_candidate_from_pool({
        "title": "Ева рожай",
        "alternative_title": "",
        "year": 2022,
        "criteria_name": "X",
    })
    pool = candidate_pool.load_candidate_pool()

    assert_check("Удалён совпавший кандидат из единого общего пула", removed == 1)
    assert_check("В пуле остался только другой сериал", len(pool) == 1)


def test_candidate_pool_genre_filters() -> None:
    """Проверяет фильтрацию кандидатов по жанрам и жанрам-исключениям."""
    print("\n13) Проверяем фильтрацию пула кандидатов по жанрам")

    movie = {
        "genres": [
            {"name": "драма"},
            {"name": "триллер"},
        ]
    }

    assert_check(
        "Кандидат проходит по обязательному жанру",
        candidate_pool.movie_matches_genres(movie, ["драма"], [])
    )
    assert_check(
        "Кандидат отсекается по исключенному жанру",
        candidate_pool.movie_matches_genres(movie, ["драма"], ["триллер"]) is False
    )
    assert_check(
        "При пустом обязательном списке жанров кандидат проходит",
        candidate_pool.movie_matches_genres(movie, [], []) is True
    )


def run_tests() -> None:
    """Запускает все тесты проекта."""
    temp_dir, old_paths = setup_temp_project()
    try:
        print("=== Тесты проекта recommended ===")
        test_files_created()
        test_add_new_movie()
        test_meta_overrides_raw_scores()
        test_duplicate_rejected()
        test_feature_formatting()
        test_excel_row_supports_genre()
        test_excel_title_guard()
        test_validation()
        test_tag_compatibility()
        test_training()
        test_backup_restore()
        test_api_fallback_to_secondary_token()
        test_sql_title_search()
        test_sql_title_search_aliases()
        test_build_api_defaults_from_raw_movie()
        test_merge_defaults_prefers_api_and_keeps_sql()
        test_build_genre_defaults_ignores_unknown()
        test_manual_add_defaults_when_lookup_fails()
        test_add_resolver_prioritizes_sql_and_kp()
        test_add_resolver_uses_tmdb_when_kp_fails()
        test_add_resolver_offline_without_sql_is_manual()
        test_remove_candidate_from_pool()
        test_candidate_pool_genre_filters()
        print("\nВсе проверки пройдены: True")
    finally:
        restore_project_paths(temp_dir, old_paths)


if __name__ == "__main__":
    run_tests()
