import contextlib
import io
import tempfile
from pathlib import Path

import constant
import format_score
import model
import storage
import valid


def show_check(text: str, result: bool) -> None:
    """Выводит результат проверки в понятном русском формате."""
    print(f"{text}: {result}")


def assert_check(text: str, result: bool) -> None:
    """Печатает результат проверки и останавливает тесты при ошибке."""
    show_check(text, result)
    assert result, text


def make_movie(title="Test Movie", user_score=8.0, raw_score=8.0) -> dict:
    """Создает валидный объект фильма для тестовых сценариев."""
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
        constant.TAGS_VIBE_SECTION: {
            "has_crime": 1,
            "has_psyhology": 1,
            "has_comedy": 0,
            "has_mystic": 0,
            "has_romantic_tension": 1
        }
    }


def setup_temp_project():
    """Переключает проект на временные файлы и возвращает старые пути."""
    temp_dir = tempfile.TemporaryDirectory()
    root = Path(temp_dir.name)

    old_paths = {
        "DATA_DIR": constant.DATA_DIR,
        "FILE_NAME": constant.FILE_NAME,
        "WEIGHTS_JSON": constant.WEIGHTS_JSON,
        "BACKUP_DIR": constant.BACKUP_DIR,
        "DIR_META": constant.DIR_META,
        "META_JSON": constant.META_JSON,
        "TXT_INPUT": constant.TXT_INPUT,
        "CSV_INPUT": constant.CSV_INPUT,
    }

    constant.DATA_DIR = str(root / "data")
    constant.FILE_NAME = str(root / "data" / "dataset.json")
    constant.WEIGHTS_JSON = str(root / "data" / "weights.json")
    constant.BACKUP_DIR = str(root / "backup") + "/"
    constant.DIR_META = str(root / "meta")
    constant.META_JSON = str(root / "meta" / "meta_data.json")
    constant.TXT_INPUT = str(root / "data" / "input.txt")
    constant.CSV_INPUT = str(root / "data" / "input.csv")

    storage.init_dataset()
    storage.init_meta()
    storage.init_weights()
    storage.init_txt()
    storage.init_csv()

    return temp_dir, old_paths


def restore_project_paths(temp_dir, old_paths: dict) -> None:
    """Возвращает реальные пути проекта после тестов."""
    for name, value in old_paths.items():
        setattr(constant, name, value)
    temp_dir.cleanup()


def test_files_created() -> None:
    """Проверяет создание рабочих файлов проекта."""
    print("\n1) Проверяем создание файлов")
    assert_check("Файл dataset.json открывается", Path(constant.FILE_NAME).exists())
    assert_check("Файл meta_data.json открывается", Path(constant.META_JSON).exists())
    assert_check("Файл weights.json открывается", Path(constant.WEIGHTS_JSON).exists())
    assert_check("Файл input.txt открывается", Path(constant.TXT_INPUT).exists())
    assert_check("Файл input.csv открывается", Path(constant.CSV_INPUT).exists())
    assert_check("Dataset изначально пустой", storage.load_dataset() == {})
    assert_check("Meta изначально пустая", storage.load_meta() == {})


def test_add_new_movie() -> None:
    """Проверяет добавление нового фильма в dataset и meta."""
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
    """Проверяет приоритет raw-полей из meta над новым вводом."""
    print("\n3) Проверяем приоритет meta")
    storage.clean_dataset()

    first_movie = make_movie(title="Known Movie", raw_score=9.0)
    assert_check("Первая запись создает meta", storage.add_movie(first_movie))
    storage.clean_dataset()

    second_movie = make_movie(title="Known Movie", raw_score=1.0)
    second_movie[constant.TAGS_VIBE_SECTION]["has_comedy"] = 1

    assert_check("Повторная запись с тем же title добавляется в пустой dataset", storage.add_movie(second_movie))

    saved_movie = storage.load_dataset()["Known Movie"]
    assert_check("Raw kp_score взят из meta, а не из нового ввода", saved_movie["raw_scores"]["kp_score"] == 9.0)
    assert_check("Tag has_comedy взят из нового ввода", saved_movie[constant.TAGS_VIBE_SECTION]["has_comedy"] == 1)


def test_duplicate_rejected() -> None:
    """Проверяет запрет дубля title в dataset."""
    print("\n4) Проверяем запрет дублей")
    storage.clean_dataset()
    movie = make_movie(title="Duplicate Movie")

    assert_check("Первая запись добавляется", storage.add_movie(movie))

    with contextlib.redirect_stdout(io.StringIO()):
        second_result = storage.add_movie(movie)

    assert_check("Повторная запись не добавляется", second_result is False)
    assert_check("В dataset осталась 1 запись", len(storage.load_dataset()) == 1)


def test_feature_formatting() -> None:
    """Проверяет расчет computed-признаков из raw-полей."""
    print("\n5) Проверяем расчет признаков")
    raw_scores = make_movie()["raw_scores"]
    computed = format_score.raw_to_struct(raw_scores, make_movie()["main_info"])

    assert_check("Computed содержит все ожидаемые ключи", set(computed) == set(constant.COMPUTED_SCORES))
    assert_check("kp_score переносится без изменений", computed["kp_score"] == raw_scores["kp_score"])
    assert_check("imdb_score переносится без изменений", computed["imdb_score"] == raw_scores["imdb_score"])
    assert_check("imdb_popularity находится от 0 до 10", 0 <= computed["imdb_popularity"] <= 10)


def test_validation() -> None:
    """Проверяет основные функции валидации."""
    print("\n6) Проверяем валидацию")
    assert_check("Корректный title проходит", valid.is_correct_title("Good Title"))
    assert_check("Пустой title не проходит", valid.is_correct_title("") is False)
    assert_check("Оценка 8.5 проходит", valid.is_correct_score("8.5"))
    assert_check("Оценка 11 не проходит", valid.is_correct_score("11") is False)
    assert_check("Год 2024 проходит", valid.is_correct_year("2024"))
    assert_check("Год 1999 не проходит", valid.is_correct_year("1999") is False)
    assert_check("100 голосов проходит", valid.is_correct_votes("100"))
    assert_check("-1 голосов не проходит", valid.is_correct_votes("-1") is False)


def test_training() -> None:
    """Проверяет запуск обучения модели."""
    print("\n7) Проверяем обучение модели")
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
    new_weights = model.fit_weights(data, constant.DEFAULT_WEIGHTS, passes=1)
    new_error = model.mean_absolute_error(data, new_weights)

    show_check("MAE до обучения", round(start_error, 4))
    show_check("MAE после обучения", round(new_error, 4))
    assert_check("Новые веса содержат все признаки", set(new_weights) == set(constant.FEATURES))
    assert_check("MAE не увеличилась", new_error <= start_error)


def test_txt_import() -> None:
    """Проверяет импорт записи из txt-файла."""
    print("\n8) Проверяем импорт из txt")
    storage.clean_dataset()
    Path(constant.TXT_INPUT).write_text(
        "Txt Movie;8;2024;8;120000;8;1200;1;1;0;0;1\n",
        encoding="utf-8"
    )

    with contextlib.redirect_stdout(io.StringIO()):
        result = storage.input_txt()

    dataset = storage.load_dataset()
    meta = storage.load_meta()

    assert_check("Импорт из txt возвращает True", result)
    assert_check("После импорта из txt в dataset 1 запись", len(dataset) == 1)
    assert_check("Title из txt сохранен", dataset["Txt Movie"]["main_info"]["title"] == "Txt Movie")
    assert_check("Title из txt сохранен в meta", "Txt Movie" in meta)


def test_csv_import() -> None:
    """Проверяет импорт записи из CSV-файла."""
    print("\n9) Проверяем импорт из CSV")
    storage.clean_dataset()
    Path(constant.CSV_INPUT).write_text(
        "title;user_score;year;kp_score;kp_votes;imdb_score;imdb_votes;has_crime;has_psyhology;has_comedy;has_mystic;has_romantic_tension\n"
        "Csv Movie;8;2024;8;120000;8;1200;1;1;0;0;1\n",
        encoding="utf-8-sig"
    )

    with contextlib.redirect_stdout(io.StringIO()):
        result = storage.input_csv()

    dataset = storage.load_dataset()
    meta = storage.load_meta()

    assert_check("Импорт из CSV возвращает True", result)
    assert_check("После импорта из CSV в dataset 1 запись", len(dataset) == 1)
    assert_check("Title из CSV сохранен", dataset["Csv Movie"]["main_info"]["title"] == "Csv Movie")
    assert_check("Title из CSV сохранен в meta", "Csv Movie" in meta)


def run_tests() -> None:
    """Запускает все проверки по шагам."""
    temp_dir, old_paths = setup_temp_project()
    try:
        print("=== Тесты проекта recommended ===")
        test_files_created()
        test_add_new_movie()
        test_meta_overrides_raw_scores()
        test_duplicate_rejected()
        test_feature_formatting()
        test_validation()
        test_training()
        test_txt_import()
        test_csv_import()
        print("\nВсе проверки пройдены: True")
    finally:
        restore_project_paths(temp_dir, old_paths)


if __name__ == "__main__":
    run_tests()
