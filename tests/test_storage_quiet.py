import json

import pytest

from storage import data as storage_data
from storage import files as storage_files


def _patch_storage_paths(monkeypatch, tmp_path) -> None:
    watched_dir = tmp_path / "watched"
    titles_json = watched_dir / "titles.json"
    meta_json = watched_dir / "meta.json"

    monkeypatch.setattr(storage_data.constant, "DATA_DIR", str(watched_dir))
    monkeypatch.setattr(storage_data.constant, "DIR_META", str(watched_dir))
    monkeypatch.setattr(storage_data.constant, "FILE_NAME", str(titles_json))
    monkeypatch.setattr(storage_data.constant, "META_JSON", str(meta_json))


def test_add_movies_to_meta_returns_false_without_printing(monkeypatch, tmp_path, capsys) -> None:
    _patch_storage_paths(monkeypatch, tmp_path)

    result = storage_data.add_movies_to_meta(
        {"title": "", "user_score": 8.0, "year": 2020},
        {},
    )

    assert result is False
    assert capsys.readouterr().out == ""


def test_rename_movie_title_returns_false_without_printing(monkeypatch, tmp_path, capsys) -> None:
    _patch_storage_paths(monkeypatch, tmp_path)

    result = storage_data.rename_movie_title("Missing", "New Title")

    assert result is False
    assert capsys.readouterr().out == ""


def test_load_dataset_returns_empty_dict_for_non_object_json_without_writing(monkeypatch, tmp_path) -> None:
    _patch_storage_paths(monkeypatch, tmp_path)
    dataset_path = tmp_path / "watched" / "titles.json"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(json.dumps(["not", "a", "dataset"]), encoding="utf-8")
    before = dataset_path.read_text(encoding="utf-8")

    assert storage_data.load_dataset() == {}
    assert dataset_path.read_text(encoding="utf-8") == before


def test_load_dataset_skips_non_object_records_without_writing(monkeypatch, tmp_path) -> None:
    _patch_storage_paths(monkeypatch, tmp_path)
    dataset_path = tmp_path / "watched" / "titles.json"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Valid": {"main_info": {"title": "Valid"}, "genre": {}},
        "Broken": "not a movie",
    }
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")
    before = dataset_path.read_text(encoding="utf-8")

    loaded = storage_data.load_dataset()

    assert set(loaded) == {"Valid"}
    assert dataset_path.read_text(encoding="utf-8") == before


def test_load_meta_returns_empty_dict_for_non_object_json_without_writing(monkeypatch, tmp_path) -> None:
    _patch_storage_paths(monkeypatch, tmp_path)
    meta_path = tmp_path / "watched" / "meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(["not", "meta"]), encoding="utf-8")
    before = meta_path.read_text(encoding="utf-8")

    assert storage_data.load_meta() == {}
    assert meta_path.read_text(encoding="utf-8") == before


def test_load_meta_skips_non_object_records_without_writing(monkeypatch, tmp_path) -> None:
    _patch_storage_paths(monkeypatch, tmp_path)
    meta_path = tmp_path / "watched" / "meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"Valid": {"tmdb_id": 101}, "Broken": "not meta"}
    meta_path.write_text(json.dumps(payload), encoding="utf-8")
    before = meta_path.read_text(encoding="utf-8")

    assert storage_data.load_meta() == {"Valid": {"tmdb_id": 101}}
    assert meta_path.read_text(encoding="utf-8") == before


def test_save_dataset_preserves_existing_file_when_atomic_replace_fails(monkeypatch, tmp_path) -> None:
    _patch_storage_paths(monkeypatch, tmp_path)
    dataset_path = tmp_path / "watched" / "titles.json"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    original = {"Existing": {"main_info": {"title": "Existing"}}}
    dataset_path.write_text(json.dumps(original), encoding="utf-8")

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr(storage_files.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        storage_data.save_dataset({"New": {"main_info": {"title": "New"}, "genre": {}}})

    assert json.loads(dataset_path.read_text(encoding="utf-8")) == original
    assert not dataset_path.with_name(f"{dataset_path.name}.tmp").exists()


def test_save_meta_preserves_existing_file_when_atomic_replace_fails(monkeypatch, tmp_path) -> None:
    _patch_storage_paths(monkeypatch, tmp_path)
    meta_path = tmp_path / "watched" / "meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    original = {"Existing": {"tmdb_id": 101}}
    meta_path.write_text(json.dumps(original), encoding="utf-8")

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr(storage_files.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        storage_data.save_meta({"New": {"tmdb_id": 202}})

    assert json.loads(meta_path.read_text(encoding="utf-8")) == original
    assert not meta_path.with_name(f"{meta_path.name}.tmp").exists()
