"""Checks that Cyrillic text survives source, JSON and storage round-trips."""

import json
import tempfile
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import constant
from storage import data as storage_data
from dataset import storage_movie
from dataset import tags_work


CYRILLIC_TITLE = "Ёлки и тёмный лес"
CYRILLIC_NOTE = "Кириллица: фильм, оценка, теги, ёжик"


def assert_check(text: str, result: bool) -> None:
    print(f"{text}: {result}")
    assert result, text


def setup_temp_project():
    temp_dir = tempfile.TemporaryDirectory()
    root = Path(temp_dir.name)

    old_paths = {
        "DATA_DIR": constant.DATA_DIR,
        "FILE_NAME": constant.FILE_NAME,
        "WEIGHTS_JSON": constant.WEIGHTS_JSON,
        "BACKUP_DIR": constant.BACKUP_DIR,
        "DIR_META": constant.DIR_META,
        "META_JSON": constant.META_JSON,
    }

    constant.DATA_DIR = str(root / "data")
    constant.FILE_NAME = str(root / "data" / "dataset.json")
    constant.WEIGHTS_JSON = str(root / "data" / "weights.json")
    constant.BACKUP_DIR = str(root / "backup") + "/"
    constant.DIR_META = str(root / "meta")
    constant.META_JSON = str(root / "meta" / "meta_data.json")

    storage_data.init_dataset()
    storage_data.init_meta()
    storage_data.init_weights()

    return temp_dir, old_paths


def restore_project_paths(temp_dir, old_paths: dict) -> None:
    for name, value in old_paths.items():
        setattr(constant, name, value)
    temp_dir.cleanup()


def make_cyrillic_movie() -> dict:
    tags_vibe = {feature: 0 for feature in constant.TAGS_VIBE}
    if constant.TAGS_VIBE:
        tags_vibe[constant.TAGS_VIBE[0]] = 1

    return {
        "main_info": {
            "title": CYRILLIC_TITLE,
            "user_score": "8,5",
            "year": "2024",
        },
        "raw_scores": {
            "kp_score": "7,4",
            "kp_votes": "150000",
            "imdb_score": "7.1",
            "imdb_votes": "26000",
        },
        constant.TAGS_VIBE_SECTION: tags_vibe,
    }


def test_source_files_are_utf8() -> None:
    print("\n1) Проверяем чтение исходников как UTF-8")
    test_source = (ROOT_DIR / "tests" / "test.py").read_text(encoding="utf-8")
    readme = (ROOT_DIR / "docs" / "README.md").read_text(encoding="utf-8")

    assert_check("tests/test.py содержит нормальную кириллицу", "Проверяет основные сценарии" in test_source)
    assert_check("docs/README.md содержит нормальную кириллицу", "Консольный Python-проект" in readme)


def test_tags_json_are_utf8() -> None:
    print("\n2) Проверяем config/tags.json")
    tags = tags_work.load_tags()
    raw_tags = (ROOT_DIR / "config" / "tags.json").read_bytes()
    assert_check("Пустой каталог вайб-тегов читается корректно", isinstance(tags, dict))
    assert_check("Пустой tags.json хранится как UTF-8 JSON", raw_tags.strip() == b"{}")


def test_storage_cyrillic_roundtrip() -> None:
    print("\n3) Проверяем dataset/meta round-trip с кириллицей")
    temp_dir, old_paths = setup_temp_project()
    try:
        movie = make_cyrillic_movie()
        assert_check("Фильм с русским title добавляется", storage_movie.add_movie(movie))

        dataset = storage_data.load_dataset()
        meta = storage_data.load_meta()
        dataset_bytes = Path(constant.FILE_NAME).read_bytes()

        assert_check("Ключ dataset не искажается", CYRILLIC_TITLE in dataset)
        assert_check("Title внутри main_info не искажается", dataset[CYRILLIC_TITLE]["main_info"]["title"] == CYRILLIC_TITLE)
        assert_check("Ключ meta не искажается", CYRILLIC_TITLE in meta)
        assert_check("Файл содержит настоящие UTF-8 байты", CYRILLIC_TITLE.encode("utf-8") in dataset_bytes)
        assert_check("Файл не заменяет кириллицу на \\uXXXX", b"\\u0401" not in dataset_bytes)

        Path(constant.FILE_NAME).write_text(
            json.dumps(dataset, ensure_ascii=False, indent=4),
            encoding="utf-8-sig",
        )
        assert_check("Файл с UTF-8 BOM тоже читается", CYRILLIC_TITLE in storage_data.load_dataset())
    finally:
        restore_project_paths(temp_dir, old_paths)


def test_generic_json_helpers_keep_cyrillic() -> None:
    print("\n4) Проверяем JSON helpers на временном файле")
    with tempfile.TemporaryDirectory() as temp_name:
        file_name = Path(temp_name) / "кириллица.json"
        payload = {"title": CYRILLIC_TITLE, "note": CYRILLIC_NOTE}

        tags_work.save_json(str(file_name), payload)
        loaded = tags_work.load_json(str(file_name))
        raw_bytes = file_name.read_bytes()

        assert_check("Временный JSON читается без искажений", loaded == payload)
        assert_check("Русский текст записан UTF-8 байтами", CYRILLIC_NOTE.encode("utf-8") in raw_bytes)


def run_tests() -> None:
    print("=== Тесты кодировки recommended ===")
    test_source_files_are_utf8()
    test_tags_json_are_utf8()
    test_storage_cyrillic_roundtrip()
    test_generic_json_helpers_keep_cyrillic()
    print("\nВсе проверки кодировки пройдены: True")


if __name__ == "__main__":
    run_tests()
