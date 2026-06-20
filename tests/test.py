"""Проверяет основные сценарии работы проекта на временных данных."""

import contextlib
import io
import json
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
from model import noise_experiment
from storage import data as storage_data
from storage import files as storage_files
from storage import normalize as storage_normalize
from dataset import storage_movie
from dataset import excel_work
from candidates import candidate_pool
from candidates import schema as candidate_schema
from candidates import tmdb_candidate_pool
from apis import imdb_sql as sql_search
from dataset import title_resolve
from ui.console import interface_funcs
from ui.console import request as request_ui
from apis import kp_api as api
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
        "computed_scores": format_score.raw_to_struct(
            {
                "kp_score": raw_score,
                "kp_votes": 120000,
                "imdb_score": raw_score,
                "imdb_votes": 1200,
            },
            {
                "title": title,
                "user_score": user_score,
                "year": 2024,
            },
        ),
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
        "RATING_ORDER_DRAFTS_DIR": constant.RATING_ORDER_DRAFTS_DIR,
        "MODEL_METRICS_JSON": constant.MODEL_METRICS_JSON,
        "BACKUP_DIR": constant.BACKUP_DIR,
        "DIR_META": constant.DIR_META,
        "META_JSON": constant.META_JSON,
        "DIR_TXT": constant.DIR_TXT,
        "EDIT_EXCEL": constant.EDIT_EXCEL,
    }

    constant.DATA_DIR = str(root / "data")
    constant.FILE_NAME = str(root / "data" / "dataset.json")
    constant.WEIGHTS_JSON = str(root / "data" / "weights.json")
    constant.CRITERIA_POOL_JSON = str(root / "data" / "candidate_criteria.json")
    constant.CANDIDATE_POOL_JSON = str(root / "data" / "candidate_pool.json")
    constant.RATING_ORDER_DRAFTS_DIR = str(root / "data" / "rating_order_drafts")
    constant.MODEL_METRICS_JSON = str(root / "config" / "model_metrics.json")
    constant.BACKUP_DIR = str(root / "backup") + "/"
    constant.DIR_META = str(root / "meta")
    constant.META_JSON = str(root / "meta" / "meta_data.json")
    constant.DIR_TXT = str(root / "txt")
    constant.EDIT_EXCEL = str(root / "txt" / "edit_dataset.xlsx")

    storage_data.init_dataset()
    storage_data.init_meta()
    storage_data.init_weights()
    storage_data.init_model_metrics()

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
    assert_check("Dataset изначально пустой", storage_data.load_dataset() == {})
    assert_check("Meta изначально пустая", storage_data.load_meta() == {})


def test_add_new_movie() -> None:
    """Проверяет добавление фильма."""
    print("\n2) Проверяем добавление новой записи")
    movie = make_movie()

    assert_check("Запись добавляется", storage_movie.add_movie(movie))

    dataset = storage_data.load_dataset()
    meta = storage_data.load_meta()

    assert_check("В dataset появилась 1 запись", len(dataset) == 1)
    assert_check("Title сохранен в dataset", dataset["Test Movie"]["main_info"]["title"] == "Test Movie")
    assert_check("Title сохранен в meta", "Test Movie" in meta)
    assert_check("В dataset нет постоянного поля features", "features" not in dataset["Test Movie"])
    assert_check("Features собраны полностью", set(model.get_features(dataset["Test Movie"])) == set(constant.FEATURES))
    assert_check("Raw-поля в dataset совпадают с meta", dataset["Test Movie"]["raw_scores"] == meta["Test Movie"]["raw_scores"])


def test_meta_overrides_raw_scores() -> None:
    """Проверяет приоритет raw-данных из meta."""
    print("\n3) Проверяем приоритет meta")
    storage_data.clean_dataset()

    first_movie = make_movie(title="Known Movie", raw_score=9.0)
    assert_check("Первая запись создает meta", storage_movie.add_movie(first_movie))
    storage_data.clean_dataset()

    second_movie = make_movie(title="Known Movie", raw_score=1.0)
    changed_tag = constant.TAGS_VIBE[0] if constant.TAGS_VIBE else None
    if changed_tag is not None:
        second_movie[constant.TAGS_VIBE_SECTION][changed_tag] = 1

    assert_check("Повторная запись с тем же title добавляется в пустой dataset", storage_movie.add_movie(second_movie))

    saved_movie = storage_data.load_dataset()["Known Movie"]
    assert_check("Raw kp_score взят из meta, а не из нового ввода", saved_movie["raw_scores"]["kp_score"] == 9.0)
    if changed_tag is not None:
        assert_check("Tag взят из нового ввода", saved_movie[constant.TAGS_VIBE_SECTION][changed_tag] == 1)


def test_duplicate_rejected() -> None:
    """Проверяет запрет дублей."""
    print("\n4) Проверяем запрет дублей")
    storage_data.clean_dataset()
    movie = make_movie(title="Duplicate Movie")

    assert_check("Первая запись добавляется", storage_movie.add_movie(movie))

    with contextlib.redirect_stdout(io.StringIO()):
        second_result = storage_movie.add_movie(movie)

    assert_check("Повторная запись не добавляется", second_result.ok is False)
    assert_check("Причина отказа - дубль title", second_result.reason == "duplicate_title")
    assert_check("В dataset осталась 1 запись", len(storage_data.load_dataset()) == 1)


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


def test_excel_export_overwrite_refreshes_dataset() -> None:
    """Проверяет, что повторный export пересоздаёт Excel по актуальному dataset."""
    print("\n5.3) Проверяем пересоздание Excel по актуальному dataset")
    from openpyxl import load_workbook

    storage_data.save_dataset({
        "Old Title": make_movie("Old Title"),
    })
    assert_check("Первый export Excel успешен", excel_work.export_dataset_to_excel(overwrite=True))

    storage_data.save_dataset({
        "Old Title": make_movie("Old Title"),
        "Кухня": make_movie("Кухня"),
    })
    assert_check("Повторный export Excel успешен", excel_work.export_dataset_to_excel(overwrite=True))

    workbook = load_workbook(constant.EDIT_EXCEL, data_only=True, read_only=True)
    try:
        worksheet = workbook.active
        titles = [
            str(row[0]).strip()
            for row in worksheet.iter_rows(min_row=2, max_col=1, values_only=True)
            if row[0] is not None
        ]
    finally:
        workbook.close()

    assert_check("Новая запись появляется в Excel после переэкспорта", "Кухня" in titles)
    assert_check("Excel содержит актуальный набор title", set(titles) == {"Old Title", "Кухня"})


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


def test_title_punctuation_validation() -> None:
    """Проверяет, что названия с обычной пунктуацией проходят validator."""
    print("\n6.1) Проверяем title validator с пунктуацией")
    assert_check("Ева, рожай! проходит", valid.is_correct_title("Ева, рожай!"))
    assert_check("Слово пацана. Кровь на асфальте проходит", valid.is_correct_title("Слово пацана. Кровь на асфальте"))
    assert_check("Что? Где? Когда? проходит", valid.is_correct_title("Что? Где? Когда?"))
    assert_check("Метод-2 проходит", valid.is_correct_title("Метод-2"))
    assert_check("Пищеблок: Экстра проходит", valid.is_correct_title("Пищеблок: Экстра"))
    assert_check("Строка из пробелов не проходит", valid.is_correct_title("   ") is False)
    assert_check("Управляющий символ не проходит", valid.is_correct_title("Bad\nTitle") is False)


def test_scores_menu_structure_and_safe_update() -> None:
    """Проверяет UX меню оценок и безопасное обновление user_score."""
    print("\n6.2) Проверяем меню оценок dataset")
    from ui.console import ui as ui_module

    storage_data.save_dataset({
        "High": make_movie("High", user_score=9.0, raw_score=9.0),
        "Low": make_movie("Low", user_score=4.0, raw_score=4.0),
        "Middle": make_movie("Middle", user_score=6.5, raw_score=6.5),
    })

    data_menu_output = io.StringIO()
    with contextlib.redirect_stdout(data_menu_output):
        ui_module.show_data_menu(3, 0)
    train_menu_output = io.StringIO()
    with contextlib.redirect_stdout(train_menu_output):
        ui_module.show_train_menu(3, 0)

    assert_check("Пункт уточнения порядка находится в данных", "Уточнить порядок оценок" in data_menu_output.getvalue())
    assert_check("Попарное сравнение убрано из обучения", "Попарное сравнение оценок" not in train_menu_output.getvalue())

    before_linear = storage_data.load_dataset()
    scores_output = io.StringIO()
    with patch("builtins.input", side_effect=["8"]):
        with contextlib.redirect_stdout(scores_output):
            interface_funcs.show_all_movies()
    output_text = scores_output.getvalue()

    assert_check("Просмотр отсортирован по user_score снизу вверх", output_text.index("Low") < output_text.index("Middle") < output_text.index("High"))
    assert_check("После просмотра есть пункт линейного распределения", "Линейное распределение оценок" in output_text)
    assert_check("После просмотра есть пункт изменения user_score", "Изменить оценку user_score" in output_text)
    assert_check("После просмотра есть пункт изменения названия", "Изменить название" in output_text)
    assert_check("Выход из подменю не меняет dataset", storage_data.load_dataset() == before_linear)

    with patch("builtins.input", side_effect=["6", "1", "5.5"]):
        with contextlib.redirect_stdout(io.StringIO()):
            interface_funcs.show_all_movies()
    updated = storage_data.load_dataset()
    assert_check("Изменение user_score проходит через update-service", updated["Low"]["main_info"]["user_score"] == 5.5)


def test_linear_distribution_draft() -> None:
    """Проверяет draft линейного распределения оценок без применения к dataset."""
    print("\n6.3) Проверяем draft линейного распределения оценок")

    rows = [
        {"title": "A", "score": 5.0},
        {"title": "B", "score": 7.0},
        {"title": "C", "score": 10.0},
    ]
    proposed = interface_funcs.build_linear_distribution_items(rows)
    assert_check("3 оценки распределяются линейно", [item["proposed_score"] for item in proposed] == [5.0, 7.5, 10.0])
    assert_check("Delta считается от old_score", [item["delta"] for item in proposed] == [0.0, 0.5, 0.0])

    single = interface_funcs.build_linear_distribution_items([{"title": "Only", "score": 8.0}])
    assert_check("Одна запись не падает", len(single) == 1)
    assert_check("Одна запись сохраняет old_score", single[0]["proposed_score"] == 8.0)

    storage_data.save_dataset({
        "A": make_movie("A", user_score=5.0, raw_score=5.0),
        "B": make_movie("B", user_score=7.0, raw_score=7.0),
        "C": make_movie("C", user_score=10.0, raw_score=10.0),
    })
    before_dataset = storage_data.load_dataset()
    draft_output = io.StringIO()
    with patch("builtins.input", side_effect=["5"]):
        with contextlib.redirect_stdout(draft_output):
            interface_funcs.show_all_movies()

    draft_files = sorted(Path(constant.RATING_ORDER_DRAFTS_DIR).glob("rating_order_draft_*.json"))
    assert_check("Draft JSON создан во временной папке", len(draft_files) == 1)
    draft = json.loads(draft_files[0].read_text(encoding="utf-8"))
    assert_check("Draft содержит метод linear_distribution", draft["method"] == "linear_distribution")
    assert_check("Draft содержит proposed_score", draft["items"][1]["proposed_score"] == 7.5)
    assert_check("Dataset не меняется при создании draft", storage_data.load_dataset() == before_dataset)
    assert_check("Preview показывает top изменений", "Top-10 изменений по модулю delta" in draft_output.getvalue())


def write_rating_order_draft(name: str, items: list[dict]) -> Path:
    """Создаёт draft распределения оценок для тестов."""
    draft_dir = Path(constant.RATING_ORDER_DRAFTS_DIR)
    draft_dir.mkdir(parents=True, exist_ok=True)
    draft_path = draft_dir / name
    draft = {
        "created_at": "2026-06-19T12:00:00",
        "method": "linear_distribution",
        "min_score": min(item["old_score"] for item in items),
        "max_score": max(item["old_score"] for item in items),
        "count": len(items),
        "items": items,
    }
    draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=4), encoding="utf-8")
    return draft_path


def clear_rating_order_drafts() -> None:
    """Очищает временные draft-файлы тестового проекта."""
    draft_dir = Path(constant.RATING_ORDER_DRAFTS_DIR)
    if draft_dir.exists() is False:
        return
    for draft_file in draft_dir.glob("rating_order_draft_*.json"):
        draft_file.unlink()


def test_apply_rating_order_draft() -> None:
    """Проверяет безопасное применение draft распределения оценок."""
    print("\n6.4) Проверяем применение draft распределения оценок")

    storage_data.save_dataset({
        "A": make_movie("A", user_score=5.0, raw_score=5.0),
        "B": make_movie("B", user_score=7.0, raw_score=7.0),
        "C": make_movie("C", user_score=10.0, raw_score=10.0),
    })
    clear_rating_order_drafts()
    storage_data.save_model_metrics({"loo_mae": 0.4321})
    before_weights = storage_data.load_weights()
    before_metrics = storage_data.load_model_metrics()
    write_rating_order_draft(
        "rating_order_draft_2026-06-19_12-00-00.json",
        [
            {"position": 1, "title": "A", "old_score": 5.0, "proposed_score": 5.0, "delta": 0.0},
            {"position": 2, "title": "B", "old_score": 7.0, "proposed_score": 7.5, "delta": 0.5},
            {"position": 3, "title": "C", "old_score": 10.0, "proposed_score": 10.0, "delta": 0.0},
        ],
    )

    with patch("builtins.input", side_effect=["1"]):
        with patch("ui.console.interface_funcs.calculate_rating_order_loo_mae", side_effect=[1.0, 0.9]) as loo_mock:
            with patch("ui.console.interface_funcs.update_dataset_record", wraps=interface_funcs.update_dataset_record) as update_mock:
                with contextlib.redirect_stdout(io.StringIO()):
                    applied = interface_funcs.apply_rating_order_draft_flow(input_func=lambda _text: "y")

    updated = storage_data.load_dataset()
    assert_check("Draft с совпадающим old_score применяется", applied is True)
    assert_check("update_dataset_record вызван для изменённой оценки", update_mock.call_count == 1)
    assert_check("LOO comparison вызывается для текущего и draft dataset", loo_mock.call_count == 2)
    assert_check("user_score обновлён после применения", updated["B"]["main_info"]["user_score"] == 7.5)
    assert_check("Веса не меняются при применении draft", storage_data.load_weights() == before_weights)
    assert_check("model_metrics не меняется при применении draft", storage_data.load_model_metrics() == before_metrics)


def test_apply_rating_order_draft_stops_on_stale_or_missing_data() -> None:
    """Проверяет остановку применения draft при рассинхроне с dataset."""
    print("\n6.5) Проверяем защиту применения draft")

    storage_data.save_dataset({
        "A": make_movie("A", user_score=5.0, raw_score=5.0),
        "B": make_movie("B", user_score=7.0, raw_score=7.0),
    })
    clear_rating_order_drafts()
    stale = {
        "method": "linear_distribution",
        "items": [
            {"title": "A", "old_score": 4.0, "proposed_score": 5.0},
        ],
    }
    missing = {
        "method": "linear_distribution",
        "items": [
            {"title": "Missing", "old_score": 7.0, "proposed_score": 8.0},
        ],
    }
    ok_stale, message_stale, _ = interface_funcs.validate_rating_order_draft(stale, storage_data.load_dataset())
    ok_missing, message_missing, _ = interface_funcs.validate_rating_order_draft(missing, storage_data.load_dataset())

    assert_check("Draft с несовпадающим old_score останавливается", ok_stale is False)
    assert_check("Stale draft сообщает о смене dataset", message_stale == "Dataset изменился после создания draft. Создайте новый draft.")
    assert_check("Draft с отсутствующим title останавливается", ok_missing is False)
    assert_check("Missing title сообщает об отсутствующей записи", "отсутствует запись" in message_missing)


def test_apply_rating_order_draft_cancel_keeps_dataset() -> None:
    """Проверяет, что отмена подтверждения не меняет dataset."""
    print("\n6.6) Проверяем отмену применения draft")

    storage_data.save_dataset({
        "A": make_movie("A", user_score=5.0, raw_score=5.0),
        "B": make_movie("B", user_score=7.0, raw_score=7.0),
    })
    clear_rating_order_drafts()
    before_dataset = storage_data.load_dataset()
    write_rating_order_draft(
        "rating_order_draft_2026-06-19_13-00-00.json",
        [
            {"position": 1, "title": "A", "old_score": 5.0, "proposed_score": 5.0, "delta": 0.0},
            {"position": 2, "title": "B", "old_score": 7.0, "proposed_score": 8.0, "delta": 1.0},
        ],
    )

    with patch("builtins.input", side_effect=["1"]):
        with patch("ui.console.interface_funcs.calculate_rating_order_loo_mae", side_effect=[1.0, 1.1]):
            with contextlib.redirect_stdout(io.StringIO()):
                applied = interface_funcs.apply_rating_order_draft_flow(input_func=lambda _text: "")

    assert_check("При отмене draft не применяется", applied is False)
    assert_check("Dataset не меняется при отмене", storage_data.load_dataset() == before_dataset)


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
    normalized = storage_normalize.normalize_tags_vibe(old_tags)

    assert_check("Tag order matches the new scheme", constant.TAGS_VIBE == expected_tags)
    assert_check("Legacy tags are removed after migration", list(normalized) == expected_tags)
    assert_check("Missing active tags default to zero", all(feature in normalized for feature in constant.TAGS_VIBE))
    if constant.TAGS_VIBE:
        changed_tag = constant.TAGS_VIBE[0]
        assert_check("Invalid binary tag is rejected", storage_normalize.is_valid_tags_vibe({**normalized, changed_tag: 2}) is False)


def test_training() -> None:
    """Проверяет обучение модели."""
    print("\n7) Проверяем обучение модели")
    if linear_regression_train.is_method_available("mae_scipy") is False:
        print("SKIP: scipy minimize (MAE) недоступен в текущем окружении.")
        return
    storage_data.clean_dataset()

    movies = [
        make_movie("A", user_score=8.0, raw_score=8.0),
        make_movie("B", user_score=5.0, raw_score=5.0),
        make_movie("C", user_score=9.0, raw_score=9.0),
    ]
    for movie in movies:
        assert_check(f"Запись {movie['main_info']['title']} добавляется", storage_movie.add_movie(movie))

    data = storage_data.load_dataset()
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


def test_noise_experiment_uses_loo_metrics() -> None:
    """Проверяет, что noise benchmark использует LOO-метрики и не вызывает обычный MAE."""
    print("\n8) Проверяем noise benchmark на LOO MAE")
    if linear_regression_train.is_method_available(linear_regression_train.BENCHMARK_METHOD) is False:
        print("SKIP: Ridge benchmark недоступен в текущем окружении.")
        return

    data = {
        "A": make_movie("A", user_score=8.0, raw_score=8.0),
        "B": make_movie("B", user_score=6.0, raw_score=6.2),
        "C": make_movie("C", user_score=9.0, raw_score=8.7),
    }

    with patch("model.noise_experiment.model.mean_absolute_error", side_effect=AssertionError("MAE не должен вызываться")):
        result = noise_experiment.run_noise_experiment(
            data=data,
            weights=constant.DEFAULT_WEIGHTS.copy(),
            delta=0.5,
            runs=3,
            seed=123,
        )

    assert_check("Benchmark возвращает LOO baseline", "original_loo_mae_before" in result)
    assert_check("Benchmark возвращает средний LOO на шуме", "avg_noisy_loo_mae" in result)
    assert_check("Benchmark возвращает LOO на исходных данных после шума", "avg_original_loo_mae_after_noise_training" in result)
    assert_check("Вернулось 3 прогона benchmark", len(result["trials"]) == 3)


def test_backup_restore() -> None:
    """Проверяет восстановление датасета из backup."""
    print("\n9) Проверяем восстановление backup")
    storage_data.clean_dataset()

    first_movie = make_movie("Backup A", user_score=7.0, raw_score=7.0)
    second_movie = make_movie("Backup B", user_score=9.0, raw_score=9.0)

    assert_check("Первая запись добавляется", storage_movie.add_movie(first_movie))
    storage_files.create_backup()
    backup_path = storage_files.get_latest_backups(1)[0]

    assert_check("Вторая запись добавляется", storage_movie.add_movie(second_movie))
    assert_check("В датасете временно 2 записи", len(storage_data.load_dataset()) == 2)

    records_count = storage_files.restore_backup(backup_path)
    data = storage_data.load_dataset()

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
    with patch("ui.console.request.title_resolve.resolve_title_data_for_add", return_value=resolved):
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

    with patch("dataset.title_resolve.sql_search.search_title_in_sql", return_value={"ok": True, "data": sql_data}):
        with patch("dataset.title_resolve.api.find_series_raw", return_value={"ok": True, "data": kp_data}):
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

    with patch("dataset.title_resolve.sql_search.search_title_in_sql", return_value={"ok": True, "data": sql_data}):
        with patch("dataset.title_resolve.api.find_series_raw", return_value={"ok": False, "error": "network_error", "details": "timeout"}):
            with patch("dataset.title_resolve.api_tmdb.search_tv_by_name", return_value=[{"id": 10, "name": "TMDb Title", "vote_count": 10}]):
                with patch("dataset.title_resolve.api_tmdb.get_tv_details", return_value=tmdb_details):
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

    with patch("dataset.title_resolve.sql_search.search_title_in_sql", return_value={"ok": False, "details": "not_found"}):
        with patch("dataset.title_resolve.api.find_series_raw", return_value={"ok": False, "error": "network_error", "details": "timeout"}):
            with patch("dataset.title_resolve.api_tmdb.search_tv_by_name", side_effect=RuntimeError("offline")):
                resolved = title_resolve.resolve_title_data_for_add("Manual Only")

    assert_check("Ничего не найдено", resolved["found"] is False)
    assert_check("Defaults не создаются до согласия пользователя", resolved["defaults"] is None)
    assert_check("SQL не найден", resolved["statuses"]["sql"] == "не найдено")
    assert_check("KP API ошибка", resolved["statuses"]["kp_api"] == "ошибка")
    assert_check("TMDb API ошибка", resolved["statuses"]["tmdb_api"] == "ошибка")


def test_candidate_pool_cross_criteria_keys_survive_save_load() -> None:
    """Проверяет, что одинаковый title/year в разных criteria_name не схлопывается."""
    print("\n12) Проверяем cross-criteria ключи candidate_pool")

    candidate_pool.save_candidate_pool({
        "legacy-one": {
            "title": "Метод",
            "alternative_title": "",
            "year": 2015,
            "criteria_name": "tmdb_RU_quality",
            "kp_score": 7.3,
            "kp_votes": 1000,
            "imdb_score": 7.4,
            "imdb_votes": 5000,
            "genres": ["драма"],
        },
        "legacy-two": {
            "title": "Метод",
            "alternative_title": "",
            "year": 2015,
            "criteria_name": "tmdb_RU_hidden",
            "kp_score": 7.8,
            "kp_votes": 1500,
            "imdb_score": 7.5,
            "imdb_votes": 4500,
            "genres": ["драма"],
        },
    })

    pool = candidate_pool.load_candidate_pool()
    criteria_names = {candidate.get("criteria_name") for candidate in pool.values()}

    assert_check("В пуле остаются обе criteria-версии", len(pool) == 2)
    assert_check("Сохраняются оба criteria_name", criteria_names == {"tmdb_RU_quality", "tmdb_RU_hidden"})
    assert_check(
        "Ключи пула становятся criteria-aware",
        set(pool.keys()) == {"tmdb_ru_quality|метод|2015", "tmdb_ru_hidden|метод|2015"}
    )


def test_candidate_pool_same_criteria_duplicates_keep_best() -> None:
    """Проверяет дедуп внутри одного criteria-aware ключа."""
    print("\n13) Проверяем дедуп внутри одного pool_entry_key")

    candidate_pool.save_candidate_pool({
        "first": {
            "title": "Метод",
            "alternative_title": "",
            "year": 2015,
            "criteria_name": "tmdb_RU_quality",
            "kp_score": 7.1,
            "kp_votes": 800,
            "imdb_score": 7.0,
            "imdb_votes": 2500,
            "genres": ["драма"],
        },
        "second": {
            "title": "Метод",
            "alternative_title": "",
            "year": 2015,
            "criteria_name": "tmdb_RU_quality",
            "kp_score": 8.4,
            "kp_votes": 2200,
            "imdb_score": 8.0,
            "imdb_votes": 9000,
            "genres": ["драма"],
        },
    })

    pool = candidate_pool.load_candidate_pool()
    saved_candidate = next(iter(pool.values()))

    assert_check("Дубликаты в одном criteria-aware ключе схлопываются", len(pool) == 1)
    assert_check("Остаётся лучший кандидат по текущему score-правилу", saved_candidate["kp_score"] == 8.4)


def test_load_candidate_pool_is_read_only() -> None:
    """Проверяет, что load_candidate_pool больше не пишет файл на чтении."""
    print("\n14) Проверяем read-only поведение load_candidate_pool")

    candidate_pool.save_candidate_pool({
        "one": {
            "title": "Метод",
            "alternative_title": "",
            "year": 2015,
            "criteria_name": "tmdb_RU_quality",
            "kp_score": 7.5,
            "kp_votes": 1000,
            "imdb_score": 7.3,
            "imdb_votes": 3000,
            "genres": ["драма"],
        },
    })
    before_mtime = Path(constant.CANDIDATE_POOL_JSON).stat().st_mtime_ns

    with patch("candidates.candidate_pool.save_candidate_pool", side_effect=RuntimeError("load must not save")):
        pool = candidate_pool.load_candidate_pool()

    after_mtime = Path(constant.CANDIDATE_POOL_JSON).stat().st_mtime_ns

    assert_check("load_candidate_pool возвращает данные", len(pool) == 1)
    assert_check("load_candidate_pool не меняет mtime файла", before_mtime == after_mtime)

def test_candidate_schema_normalizes_legacy_complete_record() -> None:
    """Проверяет legacy backfill для complete-кандидата без is_complete/kp_status."""
    print("\n15) Проверяем schema backfill для complete legacy candidate")

    normalized = candidate_schema.normalize_candidate_record({
        "title": "Legacy Complete",
        "year": 2020,
        "kp_score": 7.2,
        "kp_votes": 1500,
        "imdb_score": 7.4,
        "imdb_votes": 7000,
        "extra_field": "keep_me",
    })

    assert_check("Legacy candidate получает criteria_name=legacy", normalized["criteria_name"] == "legacy")
    assert_check("Legacy candidate получает source=legacy", normalized["source"] == "legacy")
    assert_check("Legacy candidate становится complete", normalized["is_complete"] is True)
    assert_check("Legacy candidate получает kp_status=done", normalized["kp_status"] == "done")
    assert_check("Unknown fields сохраняются", normalized["extra_field"] == "keep_me")


def test_candidate_schema_marks_missing_kp() -> None:
    """Проверяет incomplete-кандидата без KP score/votes."""
    print("\n16) Проверяем schema completeness без KP")

    candidate = candidate_schema.normalize_candidate_record({
        "title": "No KP Yet",
        "year": 2021,
        "imdb_score": 7.1,
        "imdb_votes": 5000,
        "kp_score": None,
        "kp_votes": None,
    })
    completeness = candidate_schema.compute_completeness(candidate)

    assert_check("Candidate без KP не complete", candidate["is_complete"] is False)
    assert_check("missing_fields содержит kp_score", "kp_score" in completeness["missing_fields"])
    assert_check("missing_fields содержит kp_votes", "kp_votes" in completeness["missing_fields"])
    assert_check("kp_status не done без KP данных", completeness["kp_status"] != "done")


def test_candidate_schema_preserves_specific_kp_status() -> None:
    """Проверяет сохранение конкретного KP-статуса при отсутствии KP данных."""
    print("\n17) Проверяем сохранение конкретного kp_status")

    candidate = candidate_schema.normalize_candidate_record({
        "title": "KP Not Found",
        "year": 2021,
        "kp_status": "not_found",
        "kp_score": None,
        "kp_votes": None,
        "imdb_score": 7.0,
        "imdb_votes": 3000,
    })

    assert_check("kp_status=not_found сохраняется", candidate["kp_status"] == "not_found")
    assert_check("Candidate со статусом not_found остаётся incomplete", candidate["is_complete"] is False)


def test_candidate_schema_ready_for_predict_requires_kp_and_imdb() -> None:
    """Проверяет readiness gate по единой schema-функции."""
    print("\n18) Проверяем readiness gate schema")

    ready_candidate = {
        "title": "Ready",
        "year": 2020,
        "kp_score": 7.5,
        "kp_votes": 1000,
        "imdb_score": 7.4,
        "imdb_votes": 5000,
    }
    incomplete_candidate = {
        "title": "Incomplete",
        "year": 2020,
        "kp_score": 7.5,
        "kp_votes": 1000,
        "imdb_score": 7.4,
        "imdb_votes": None,
    }

    assert_check("is_ready_for_predict=True только при полном KP+IMDb", candidate_schema.is_ready_for_predict(ready_candidate) is True)
    assert_check("is_ready_for_predict=False если не хватает поля", candidate_schema.is_ready_for_predict(incomplete_candidate) is False)


def test_retry_kp_enrichment_makes_candidate_complete() -> None:
    """Проверяет, что retry KP переводит кандидата в complete после успешного fill."""
    print("\n19) Проверяем retry KP -> complete")

    candidate_pool.save_candidate_pool({
        "one": {
            "title": "Retry Candidate",
            "alternative_title": "",
            "year": 2020,
            "criteria_name": "legacy",
            "kp_score": None,
            "kp_votes": None,
            "imdb_score": 7.3,
            "imdb_votes": 4200,
            "kp_status": "missing",
        },
    })

    kp_movie = {
        "id": 555,
        "name": "Retry Candidate",
        "year": 2020,
        "rating": {"kp": 8.1},
        "votes": {"kp": 12000},
        "description": "Filled from KP",
    }

    with patch("candidates.tmdb_candidate_pool.kp_match_is_safe", return_value=(True, None)):
        with patch("candidates.candidate_pool.api.find_series_raw", return_value={"ok": True, "data": kp_movie}):
            stats = candidate_pool.retry_kp_enrichment_for_pool(limit=1)

    pool = candidate_pool.load_candidate_pool()
    candidate = next(
        item for item in pool.values()
        if item.get("title") == "Retry Candidate"
    )

    assert_check("Retry действительно нашёл KP", stats["kp_found"] == 1)
    assert_check("После retry кандидат complete", candidate["is_complete"] is True)
    assert_check("После retry kp_status=done", candidate["kp_status"] == "done")


def test_candidate_schema_keeps_unknown_fields() -> None:
    """Проверяет, что schema-нормализация не удаляет неизвестные поля."""
    print("\n20) Проверяем сохранение unknown fields")

    normalized = candidate_schema.normalize_candidate_record({
        "title": "Unknown Fields",
        "year": 2022,
        "custom_blob": {"hello": "world"},
        "signals": ["keep"],
    })

    assert_check("Unknown dict field сохраняется", normalized["custom_blob"] == {"hello": "world"})
    assert_check("Signals сохраняются", normalized["signals"] == ["keep"])


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

    assert_check("Удалён совпавший кандидат из единого общего пула", removed == 2)
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


def test_tmdb_candidate_pool_criteria_name() -> None:
    """Проверяет ручной/auto criteria_name и совместимость импорта старых result."""
    print("\n14) Проверяем criteria_name для TMDb candidate_pool")

    def fake_details(_tmdb_id, **_kwargs):
        return {
            "id": 101,
            "name": "TMDb Candidate",
            "original_name": "TMDb Candidate",
            "first_air_date": "2021-01-01",
            "origin_country": ["RU"],
            "production_countries": [{"iso_3166_1": "RU", "name": "Russia"}],
            "genres": [{"name": "Drama"}],
            "vote_average": 8.0,
            "vote_count": 100,
            "popularity": 10,
            "external_ids": {},
            "credits": {},
        }

    with patch("candidates.tmdb_candidate_pool.api_tmdb.load_tmdb_token", return_value="token"):
        with patch("candidates.tmdb_candidate_pool.api_tmdb.discover_tv_candidates", return_value=[{"id": 101, "vote_count": 100, "popularity": 10}]):
            with patch("candidates.tmdb_candidate_pool.api_tmdb.get_tv_details", side_effect=fake_details):
                with patch("candidates.tmdb_candidate_pool.connect_imdb", return_value=None):
                    with patch("candidates.tmdb_candidate_pool.enrich_from_kp_api_if_needed", side_effect=lambda candidate, _country, _stats: candidate):
                        manual_result = tmdb_candidate_pool.build_candidate_pool(
                            country="RU",
                            pages=1,
                            details_limit=1,
                            mode="quality",
                            criteria_name="Русские драмы 2020+",
                        )
                        auto_result = tmdb_candidate_pool.build_candidate_pool(
                            country="RU",
                            pages=1,
                            details_limit=1,
                            mode="quality",
                            year_min=2020,
                            min_tmdb_score=7.0,
                        )

    assert_check("Ручное criteria_name сохраняется в result", manual_result["criteria_name"] == "Русские драмы 2020+")
    assert_check("Ручное criteria_name сохраняется в candidate", manual_result["candidates"][0]["criteria_name"] == "Русские драмы 2020+")
    assert_check("Auto criteria_name создаётся по параметрам", auto_result["criteria_name"] == "tmdb_RU_quality_2020plus_min7")
    assert_check("Auto criteria_name сохраняется в settings", auto_result["settings"]["criteria_name"] == "tmdb_RU_quality_2020plus_min7")

    old_result_path = Path(constant.DATA_DIR) / "old_tmdb_result.json"
    old_result = {
        "country": "RU",
        "mode": "quality",
        "candidates": [
            {
                "title": "Old TMDb Candidate",
                "year": 2022,
                "tmdb_id": 200,
                "genres_tmdb": ["Drama"],
                "tmdb_rating": 7.5,
                "tmdb_votes": 50,
            }
        ],
    }
    old_result_path.write_text(json.dumps(old_result, ensure_ascii=False), encoding="utf-8")
    stats = tmdb_candidate_pool.import_tmdb_result_to_common_pool(old_result_path)
    pool = candidate_pool.load_candidate_pool()

    assert_check("Старый result без criteria_name импортируется", stats["ok"] is True)
    assert_check("Для старого result используется fallback criteria_name", stats["criteria_name"] == "tmdb_RU_quality")
    assert_check(
        "Common candidate получает fallback criteria_name",
        any(candidate.get("criteria_name") == "tmdb_RU_quality" for candidate in pool.values())
    )


def test_tmdb_import_keeps_cross_criteria_entries() -> None:
    """Проверяет, что TMDb import не теряет одинаковый title/year из разных criteria."""
    print("\n16) Проверяем cross-criteria TMDb import")

    first_result_path = Path(constant.DATA_DIR) / "tmdb_result_quality.json"
    second_result_path = Path(constant.DATA_DIR) / "tmdb_result_hidden.json"

    first_result = {
        "criteria_name": "tmdb_RU_quality",
        "country": "RU",
        "mode": "quality",
        "candidates": [
            {
                "title": "Метод",
                "year": 2015,
                "tmdb_id": 301,
                "genres_tmdb": ["Drama"],
                "tmdb_rating": 7.5,
                "tmdb_votes": 50,
            }
        ],
    }
    second_result = {
        "criteria_name": "tmdb_RU_hidden",
        "country": "RU",
        "mode": "hidden",
        "candidates": [
            {
                "title": "Метод",
                "year": 2015,
                "tmdb_id": 302,
                "genres_tmdb": ["Drama"],
                "tmdb_rating": 7.7,
                "tmdb_votes": 40,
            }
        ],
    }

    first_result_path.write_text(json.dumps(first_result, ensure_ascii=False), encoding="utf-8")
    second_result_path.write_text(json.dumps(second_result, ensure_ascii=False), encoding="utf-8")

    first_stats = tmdb_candidate_pool.import_tmdb_result_to_common_pool(first_result_path)
    second_stats = tmdb_candidate_pool.import_tmdb_result_to_common_pool(second_result_path)
    pool = candidate_pool.load_candidate_pool()
    method_candidates = [
        candidate
        for candidate in pool.values()
        if candidate.get("title") == "Метод" and candidate.get("year") == 2015
    ]
    criteria_names = {candidate.get("criteria_name") for candidate in method_candidates}

    assert_check("Первый TMDb import успешен", first_stats["ok"] is True)
    assert_check("Второй TMDb import успешен", second_stats["ok"] is True)
    assert_check("После двух import остаются обе criteria-версии", criteria_names == {"tmdb_RU_quality", "tmdb_RU_hidden"})
    assert_check("TMDb import не схлопывает одинаковый title/year из разных criteria", len(method_candidates) == 2)

def test_tmdb_genre_diagnostics_and_helpers() -> None:
    """Проверяет TMDb genre diagnostics и чистые genre helpers без изменения dataset."""
    print("\n15) Проверяем TMDb genre diagnostics")

    dataset = {
        "A": make_movie("A", user_score=8.0),
        "B": make_movie("B", user_score=7.0),
    }
    meta = {
        "A": {"tmdb_id": 1},
    }
    before_dataset = json.loads(json.dumps(dataset, ensure_ascii=False))

    def fake_details(tmdb_id):
        if tmdb_id == 1:
            return {
                "id": 1,
                "name": "A",
                "first_air_date": "2020-01-01",
                "genres": [{"name": "Drama"}, {"name": "Crime"}],
                "external_ids": {},
                "credits": {},
            }
        raise RuntimeError("unexpected tmdb_id")

    progress_events = []
    report = tmdb_candidate_pool.build_tmdb_genre_distribution_report(
        dataset,
        meta,
        details_fetcher=fake_details,
        search_func=lambda _title: [],
        progress_callback=progress_events.append,
    )
    report_path = tmdb_candidate_pool.save_tmdb_genre_distribution_report(
        report,
        output_dir=Path(constant.DATA_DIR) / "diagnostics",
    )
    genres = tmdb_candidate_pool.collect_candidate_genres({
        "genres": [{"name": "Драма"}, "драма"],
        "imdb_genres": [" Crime "],
        "genres_tmdb": ["Mystery"],
        "genre_ids": [80],
    })

    assert_check("Diagnostics считает Drama", report["genre_counts"]["Drama"] == 1)
    assert_check("Diagnostics считает Crime", report["genre_counts"]["Crime"] == 1)
    assert_check("Unmatched попадает в unmatched_items", report["unmatched_items"] == [{"title": "B", "year": 2024}])
    assert_check("Diagnostics JSON создаётся", report_path.exists())
    assert_check("Dataset не меняется при diagnostics", dataset == before_dataset)
    assert_check("Diagnostics progress вызывается по каждой записи", len(progress_events) == 4)
    assert_check("collect_candidate_genres нормализует и убирает дубли", genres == {"драма", "crime", "mystery"})

    error_dataset = {
        "A": make_movie("A", user_score=8.0),
        "B": make_movie("B", user_score=7.0),
        "C": make_movie("C", user_score=6.0),
    }
    error_events = []
    stopped_report = tmdb_candidate_pool.build_tmdb_genre_distribution_report(
        error_dataset,
        {},
        search_func=lambda _title: (_ for _ in ()).throw(RuntimeError("offline")),
        progress_callback=error_events.append,
        max_consecutive_errors=2,
    )
    assert_check("Diagnostics останавливается после серии ошибок", stopped_report["stopped_early"] is True)
    assert_check("Diagnostics не обходит весь dataset при сетевых ошибках", stopped_report["processed"] == 2)
    assert_check("Diagnostics сообщает stop progress event", error_events[-1]["status"] == "stopped")


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
        test_excel_export_overwrite_refreshes_dataset()
        test_validation()
        test_title_punctuation_validation()
        test_scores_menu_structure_and_safe_update()
        test_linear_distribution_draft()
        test_apply_rating_order_draft()
        test_apply_rating_order_draft_stops_on_stale_or_missing_data()
        test_apply_rating_order_draft_cancel_keeps_dataset()
        test_tag_compatibility()
        test_training()
        test_noise_experiment_uses_loo_metrics()
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
        test_candidate_pool_cross_criteria_keys_survive_save_load()
        test_candidate_pool_same_criteria_duplicates_keep_best()
        test_load_candidate_pool_is_read_only()
        test_candidate_schema_normalizes_legacy_complete_record()
        test_candidate_schema_marks_missing_kp()
        test_candidate_schema_preserves_specific_kp_status()
        test_candidate_schema_ready_for_predict_requires_kp_and_imdb()
        test_retry_kp_enrichment_makes_candidate_complete()
        test_candidate_schema_keeps_unknown_fields()
        test_remove_candidate_from_pool()
        test_candidate_pool_genre_filters()
        test_tmdb_candidate_pool_criteria_name()
        test_tmdb_import_keeps_cross_criteria_entries()
        test_tmdb_genre_diagnostics_and_helpers()
        print("\nВсе проверки пройдены: True")
    finally:
        restore_project_paths(temp_dir, old_paths)


if __name__ == "__main__":
    run_tests()
