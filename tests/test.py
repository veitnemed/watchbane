"""Проверяет основные сценарии работы проекта на временных данных."""

import contextlib
import io
import json
import tempfile
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import constant
from core import format_score
from model_work import model
from data_work import storage
from data_work import tst_scores
from core import valid


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
    for feature in ["has_crime", "has_psychology", "has_romantic_pursuit"]:
        if feature in tags_vibe:
            tags_vibe[feature] = 1

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
        constant.TAGS_VIBE_SECTION: tags_vibe
    }


def setup_temp_project():
    """Готовит временный проект для тестов."""
    temp_dir = tempfile.TemporaryDirectory()
    root = Path(temp_dir.name)

    old_paths = {
        "DATA_DIR": constant.DATA_DIR,
        "FILE_NAME": constant.FILE_NAME,
        "TST_SCORES_JSON": constant.TST_SCORES_JSON,
        "WEIGHTS_JSON": constant.WEIGHTS_JSON,
        "BACKUP_DIR": constant.BACKUP_DIR,
        "DIR_META": constant.DIR_META,
        "META_JSON": constant.META_JSON,
    }

    constant.DATA_DIR = str(root / "data")
    constant.FILE_NAME = str(root / "data" / "dataset.json")
    constant.TST_SCORES_JSON = str(root / "data" / "dataset_from_tst.json")
    constant.WEIGHTS_JSON = str(root / "data" / "weights.json")
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
    changed_tag = constant.TAGS_VIBE[0]
    second_movie[constant.TAGS_VIBE_SECTION][changed_tag] = 1

    assert_check("Повторная запись с тем же title добавляется в пустой dataset", storage.add_movie(second_movie))

    saved_movie = storage.load_dataset()["Known Movie"]
    assert_check("Raw kp_score взят из meta, а не из нового ввода", saved_movie["raw_scores"]["kp_score"] == 9.0)
    assert_check("Tag взят из нового ввода", saved_movie[constant.TAGS_VIBE_SECTION][changed_tag] == 1)


def test_duplicate_rejected() -> None:
    """Проверяет запрет дублей."""
    print("\n4) Проверяем запрет дублей")
    storage.clean_dataset()
    movie = make_movie(title="Duplicate Movie")

    assert_check("Первая запись добавляется", storage.add_movie(movie))

    with contextlib.redirect_stdout(io.StringIO()):
        second_result = storage.add_movie(movie)

    assert_check("Повторная запись не добавляется", second_result is False)
    assert_check("В dataset осталась 1 запись", len(storage.load_dataset()) == 1)


def test_feature_formatting() -> None:
    """Проверяет расчет признаков."""
    print("\n5) Проверяем расчет признаков")
    raw_scores = make_movie()["raw_scores"]
    computed = format_score.raw_to_struct(raw_scores, make_movie()["main_info"])

    assert_check("Computed содержит все ожидаемые ключи", set(computed) == set(constant.COMPUTED_SCORES))
    assert_check("kp_score переносится без изменений", computed["kp_score"] == raw_scores["kp_score"])
    assert_check("imdb_score переносится без изменений", computed["imdb_score"] == raw_scores["imdb_score"])
    assert_check("imdb_popularity находится от 0 до 10", 0 <= computed["imdb_popularity"] <= 10)


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
    changed_tag = constant.TAGS_VIBE[0]
    assert_check("Invalid binary tag is rejected", storage.is_valid_tags_vibe({**normalized, changed_tag: 2}) is False)


def test_training() -> None:
    """Проверяет обучение модели."""
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


def test_tst_scores_import() -> None:
    """Проверяет чтение оценок из TST JSON."""
    print("\n8) Проверяем чтение оценок TST")
    storage.clean_dataset()

    movie = make_movie("TST Movie", user_score=5.0, raw_score=7.0)
    assert_check("Тестовая запись добавляется", storage.add_movie(movie))

    with open(constant.TST_SCORES_JSON, "w", encoding="UTF-8") as file:
        json.dump({
            "TST Movie": 8.5,
            "Missing Movie": 7.0,
            "Bad Score": 11
        }, file, ensure_ascii=False, indent=4)

    result = tst_scores.apply_tst_scores()
    data = storage.load_dataset()

    assert_check("Оценка совпавшего сериала обновлена", data["TST Movie"]["main_info"]["user_score"] == 8.5)
    assert_check("Лишний сериал попал в not_found", result["not_found"] == ["Missing Movie"])
    assert_check("Некорректная оценка попала в invalid", result["invalid"] == ["Bad Score"])
    assert_check("Обновлена ровно одна оценка", result["updated"] == 1)


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
        test_validation()
        test_tag_compatibility()
        test_training()
        test_tst_scores_import()
        test_backup_restore()
        print("\nВсе проверки пройдены: True")
    finally:
        restore_project_paths(temp_dir, old_paths)


if __name__ == "__main__":
    run_tests()
