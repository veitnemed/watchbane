import json
import tempfile
from pathlib import Path

from candidates.models.keys import title_identity_key
from common import format_score
from storage import data as storage_data
from storage.sqlite.connection import connect
from storage.sqlite.poster_repository import load_poster_cache_dict, save_poster_cache_dict


def _isolated_runtime(tmp_path, monkeypatch):
    from dataset.records import delete as records_delete

    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("config.constant.BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(records_delete, "DEFAULT_POSTER_CACHE_JSON", tmp_path / "legacy-posters.json")
    monkeypatch.setattr("posters.download_images.DEFAULT_POSTER_IMAGES_DIR", tmp_path / "images")


def _make_movie(title: str, user_score: float, year: int, raw_score: float = 8.0) -> dict:

    return {
        "main_info": {
            "title": title,
            "user_score": user_score,
            "year": year,
        },
        "raw_scores": {
            "kp_score": raw_score,
            "kp_votes": 120000,
            "imdb_score": raw_score,
            "imdb_votes": 1200,
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
                "year": year,
            },
        ),
    }


def test_search_watched_records_requires_multiple_choice_for_similar_titles() -> None:
    from dataset.delete_record import search_watched_records_by_query

    data = {
        "Major": _make_movie("Major", 8.0, 2020),
        "Major 2": _make_movie("Major 2", 7.0, 2021),
    }

    matches = search_watched_records_by_query("Major", data=data)

    assert len(matches) == 2


def test_delete_watched_record_removes_dataset_meta_and_poster_cache(monkeypatch, tmp_path) -> None:
    from dataset import delete_record as module
    from posters.cache import poster_identity_key

    dataset = {
        "Alpha": _make_movie("Alpha", 8.0, 2020),
        "Beta": _make_movie("Beta", 7.0, 2021),
    }
    meta = {
        "Alpha": {
            "main_info": dataset["Alpha"]["main_info"],
            "raw_scores": dataset["Alpha"]["raw_scores"],
            "tmdb_id": 101,
        }
    }
    identity = poster_identity_key("Alpha", 2020)
    poster_cache = {
        identity: {
            "title": "Alpha",
            "year": 2020,
            "status": "found",
            "poster_url": "https://example.com/a.jpg",
            "local_path": "C:/images/alpha.jpg",
        }
    }

    _isolated_runtime(tmp_path, monkeypatch)
    storage_data.save_dataset_and_meta(dataset, meta)
    save_poster_cache_dict(poster_cache)
    result = module.delete_watched_record("Alpha", timestamp="test")

    assert result["ok"] is True
    assert result["deleted_dataset"] == 1
    assert result["deleted_meta"] == 1
    assert result["deleted_poster_cache"] == 1
    assert result.get("deleted_poster_file", 0) == 0
    assert "Alpha" not in storage_data.load_dataset()
    assert "Beta" in storage_data.load_dataset()
    assert "Alpha" not in storage_data.load_meta()
    assert identity not in load_poster_cache_dict()
    assert result["dataset_count"] == 1
    assert len(result["backups"]) == 1
    assert Path(result["backups"][0]).is_file()


def test_delete_watched_record_without_meta_or_cache(monkeypatch, tmp_path) -> None:
    from dataset import delete_record as module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    _isolated_runtime(tmp_path, monkeypatch)
    storage_data.save_dataset(dataset)

    result = module.delete_watched_record("Alpha", timestamp="test")

    assert result["ok"] is True
    assert result["deleted_dataset"] == 1
    assert result["deleted_meta"] == 0
    assert result["deleted_poster_cache"] == 0
    assert storage_data.load_dataset() == {}


def test_delete_watched_record_missing_entry_does_not_save(monkeypatch, tmp_path) -> None:
    from dataset import delete_record as module
    from dataset.records import delete as records_delete

    _isolated_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(
        records_delete, "backup_before_watched_delete",
        lambda **_: (_ for _ in ()).throw(AssertionError("unexpected backup")),
    )

    result = module.delete_watched_record("Missing", timestamp="test")

    assert result["ok"] is False
    assert storage_data.load_dataset() == {}


def test_delete_watched_record_save_failure_keeps_local_poster(monkeypatch, tmp_path) -> None:
    from dataset.records import delete as records_delete
    from posters.cache import poster_identity_key

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    identity = poster_identity_key("Alpha", 2020)
    poster_path = tmp_path / "alpha.jpg"
    poster_path.write_bytes(b"poster")
    poster_cache = {
        identity: {
            "title": "Alpha",
            "year": 2020,
            "status": "found",
            "local_path": str(poster_path),
        }
    }

    _isolated_runtime(tmp_path, monkeypatch)
    storage_data.save_dataset(dataset)
    save_poster_cache_dict(poster_cache)
    with connect() as conn:
        conn.execute("""
            CREATE TRIGGER reject_poster_delete BEFORE DELETE ON poster_cache_entries
            BEGIN SELECT RAISE(ABORT, 'forced save failure'); END
        """)
    conn.close()

    result = records_delete.delete_watched_record("Alpha", timestamp="test")

    assert result.ok is False
    assert result.reason == "save_error"
    assert poster_path.is_file() is True
    assert "Alpha" in storage_data.load_dataset()
    assert load_poster_cache_dict() == poster_cache


def test_backup_before_watched_delete_creates_files(monkeypatch, tmp_path) -> None:
    from dataset.records import delete as records_delete

    cache_path = tmp_path / "posters.json"
    cache_path.write_text("{}", encoding="utf-8")
    sqlite_backup = tmp_path / "runtime.sqlite3"
    sqlite_backup.write_bytes(b"sqlite-backup")

    monkeypatch.setattr(records_delete, "DEFAULT_POSTER_CACHE_JSON", cache_path)

    import storage.files as files_module

    monkeypatch.setattr(files_module, "create_backup", lambda: sqlite_backup)

    backups = records_delete.backup_before_watched_delete(timestamp="123")

    assert str(sqlite_backup) in backups
    assert any(Path(path).name == "posters.json.backup_before_delete_123" for path in backups)


def test_backup_failure_cancels_delete_without_partial_write(monkeypatch, tmp_path) -> None:
    from dataset.records import delete as records_delete

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    _isolated_runtime(tmp_path, monkeypatch)
    storage_data.save_dataset(dataset)
    monkeypatch.setattr(
        records_delete,
        "backup_before_watched_delete",
        lambda timestamp=None: (_ for _ in ()).throw(PermissionError("backup denied")),
    )

    result = records_delete.delete_watched_record("Alpha", timestamp="test")

    assert result.ok is False
    assert result.reason == "backup_error"
    assert result.dataset_count == 1
    assert "denied" not in result.message
    assert "Alpha" in storage_data.load_dataset()


def test_build_watched_delete_preview(monkeypatch) -> None:
    from dataset.delete_record import build_watched_delete_preview
    from dataset.records import delete as records_delete
    from posters.cache import poster_identity_key

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {"Alpha": {"main_info": dataset["Alpha"]["main_info"], "raw_scores": dataset["Alpha"]["raw_scores"]}}
    identity = poster_identity_key("Alpha", 2020)
    poster_cache = {identity: {"status": "found", "local_path": "C:/images/alpha.jpg"}}

    monkeypatch.setattr(records_delete.storage_data, "load_meta", lambda: meta)
    monkeypatch.setattr(records_delete, "load_poster_cache", lambda: poster_cache)

    preview = build_watched_delete_preview("Alpha", data=dataset)

    assert preview is not None
    assert preview["title"] == "Alpha"
    assert preview["year"] == 2020
    assert preview["has_meta"] is True
    assert preview["has_poster_cache"] is True
    assert preview["poster_local_path"] == "C:/images/alpha.jpg"


def test_delete_watched_record_does_not_touch_candidate_pool(monkeypatch, tmp_path) -> None:
    from dataset import delete_record as module

    with tempfile.TemporaryDirectory() as temp_root:
        root = Path(temp_root)
        pool_path = root / "candidate_pool.json"
        pool_path.write_text(json.dumps({"items": []}), encoding="utf-8")

        original_pool = pool_path.read_text(encoding="utf-8")

        dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}

        _isolated_runtime(tmp_path, monkeypatch)
        storage_data.save_dataset(dataset)
        assert module.delete_watched_record("Alpha", timestamp="test")["ok"]

        assert pool_path.read_text(encoding="utf-8") == original_pool


def test_delete_watched_record_ui_cancelled_without_delete(monkeypatch) -> None:
    from ui.console import interface_funcs

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    delete_called = {"value": False}

    monkeypatch.setattr(interface_funcs.storage_data, "load_dataset", lambda: dataset)
    monkeypatch.setattr(
        interface_funcs.service,
        "search_watched_records_by_query",
        lambda query, data=None: [{"dataset_key": "Alpha", "title": "Alpha", "year": 2020, "user_score": 8.0}],
    )
    monkeypatch.setattr(
        interface_funcs.service,
        "build_watched_delete_preview",
        lambda dataset_key, data=None: {"title": "Alpha", "year": 2020, "user_score": 8.0, "has_meta": False, "has_poster_cache": False},
    )
    monkeypatch.setattr(
        interface_funcs.service,
        "format_watched_delete_preview",
        lambda preview: "preview",
    )

    def fake_delete(_dataset_key):
        delete_called["value"] = True
        return {"ok": True}

    monkeypatch.setattr(interface_funcs.service, "delete_watched_record", fake_delete)

    inputs = iter(["Alpha", "no"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

    interface_funcs.delete_watched_record()

    assert delete_called["value"] is False


def test_title_identity_key_for_poster_cache_delete() -> None:
    identity = title_identity_key({"title": "Мажор", "year": 2020})
    assert identity == "мажор|2020"


def test_delete_keeps_rows_and_cache_committed_after_backup(monkeypatch, tmp_path):
    from dataset.records import delete as records_delete
    from posters.cache import poster_identity_key
    from storage.sqlite.backup import restore_sqlite_database
    from storage.sqlite.watched_read import load_dataset_dict
    from storage.sqlite.watched_write import upsert_watched_row

    _isolated_runtime(tmp_path, monkeypatch)
    storage_data.save_dataset({"Alpha": _make_movie("Alpha", 8.0, 2020)})
    make_backup = records_delete.backup_before_watched_delete
    new_identity = poster_identity_key("After backup", 2021)

    def backup_then_insert(**kwargs):
        backups = make_backup(**kwargs)
        with connect() as conn:
            upsert_watched_row(
                conn, dataset_key="After backup", payload=_make_movie("After backup", 6.0, 2021),
                meta={"custom": "still here"},
            )
        conn.close()
        save_poster_cache_dict({new_identity: {"status": "found", "poster_path": "/new.jpg"}})
        return backups

    monkeypatch.setattr(records_delete, "backup_before_watched_delete", backup_then_insert)
    result = records_delete.delete_watched_record("Alpha")
    assert result.ok and result.dataset_count == 1
    assert set(storage_data.load_dataset()) == {"After backup"}
    assert storage_data.load_meta() == {"After backup": {"custom": "still here"}}
    assert load_poster_cache_dict()[new_identity]["poster_path"] == "/new.jpg"
    restored = tmp_path / "restored.sqlite3"
    assert restore_sqlite_database(result.backups[0], db_path=restored) == 1
    assert set(load_dataset_dict(path=restored)) == {"Alpha"}


def test_delete_does_not_remove_replaced_key_after_backup(monkeypatch, tmp_path):
    from dataset.records import delete as records_delete
    from storage.sqlite.watched_write import upsert_watched_row

    _isolated_runtime(tmp_path, monkeypatch)
    storage_data.save_dataset({"Alpha": _make_movie("Alpha", 8.0, 2020)})
    make_backup = records_delete.backup_before_watched_delete

    def backup_then_replace(**kwargs):
        backups = make_backup(**kwargs)
        with connect() as conn:
            upsert_watched_row(
                conn, dataset_key="Alpha", payload=_make_movie("Different film", 7.0, 2022), meta=None
            )
        conn.close()
        return backups

    monkeypatch.setattr(records_delete, "backup_before_watched_delete", backup_then_replace)
    result = records_delete.delete_watched_record("Alpha")
    assert not result.ok and result.reason == "record_changed"
    assert storage_data.load_dataset()["Alpha"]["main_info"]["title"] == "Different film"


def test_delete_keeps_homonym_metadata_and_shared_poster(monkeypatch, tmp_path):
    from dataset.records import delete as records_delete
    from posters.cache import poster_identity_key

    _isolated_runtime(tmp_path, monkeypatch)
    movie = _make_movie("Alpha", 8.0, 2020)
    movie["raw_scores"]["tmdb_id"] = 101
    sibling = _make_movie("Alpha", 7.0, 2020)
    sibling["raw_scores"]["tmdb_id"] = 202
    meta = {"Alpha (101)": {"tmdb_id": 101}, "Alpha": {"tmdb_id": 202}}
    storage_data.save_dataset_and_meta({"Alpha (101)": movie, "Alpha": sibling}, meta)
    image = tmp_path / "alpha.jpg"
    image.write_bytes(b"shared")
    identity = poster_identity_key("Alpha", 2020)
    save_poster_cache_dict({identity: {"local_path": str(image), "status": "found"}})

    result = records_delete.delete_watched_record("Alpha (101)")
    assert result.ok and result.deleted_meta == 1
    assert result.deleted_poster_cache == result.deleted_poster_file == 0
    assert storage_data.load_dataset()["Alpha"]["raw_scores"]["tmdb_id"] == 202
    assert storage_data.load_meta() == {"Alpha": {"tmdb_id": 202}}
    assert identity in load_poster_cache_dict()
    assert image.read_bytes() == b"shared"


def test_delete_keeps_mismatched_legacy_metadata_on_selected_key(monkeypatch, tmp_path):
    from dataset.records import delete as records_delete
    from posters.cache import poster_identity_key

    _isolated_runtime(tmp_path, monkeypatch)
    movie = _make_movie("Alpha", 8.0, 2020)
    movie["raw_scores"]["tmdb_id"] = 101
    meta = {"Alpha": {"tmdb_id": 202, "custom": "belongs to other title"}}
    storage_data.save_dataset_and_meta({"Alpha": movie}, meta)
    identity = poster_identity_key("Alpha", 2020)
    save_poster_cache_dict({identity: {"status": "found"}})

    result = records_delete.delete_watched_record("Alpha")
    assert result.ok and result.deleted_meta == 0
    assert storage_data.load_dataset() == {}
    assert storage_data.load_meta() == meta
    assert identity in load_poster_cache_dict()


def test_delete_refuses_invalid_backup(monkeypatch, tmp_path):
    from dataset.records import delete as records_delete

    _isolated_runtime(tmp_path, monkeypatch)
    storage_data.save_dataset({"Alpha": _make_movie("Alpha", 8.0, 2020)})
    bad_backup = tmp_path / "bad.sqlite3"
    bad_backup.write_bytes(b"invalid")
    monkeypatch.setattr(records_delete, "backup_before_watched_delete", lambda **_: [str(bad_backup)])

    result = records_delete.delete_watched_record("Alpha")
    assert not result.ok and result.reason == "backup_error"
    assert set(storage_data.load_dataset()) == {"Alpha"}


def test_delete_keeps_poster_changed_after_backup(monkeypatch, tmp_path):
    from dataset.records import delete as records_delete
    from posters.cache import poster_identity_key

    _isolated_runtime(tmp_path, monkeypatch)
    storage_data.save_dataset({"Alpha": _make_movie("Alpha", 8.0, 2020)})
    identity = poster_identity_key("Alpha", 2020)
    save_poster_cache_dict({identity: {"status": "pending"}})
    make_backup = records_delete.backup_before_watched_delete
    image = tmp_path / "new.jpg"
    image.write_bytes(b"new poster")
    after_backup = {identity: {"status": "found", "local_path": str(image)}}

    def backup_then_change_poster(**kwargs):
        backups = make_backup(**kwargs)
        save_poster_cache_dict(after_backup)
        return backups

    monkeypatch.setattr(records_delete, "backup_before_watched_delete", backup_then_change_poster)
    result = records_delete.delete_watched_record("Alpha")
    assert result.ok and result.deleted_poster_cache == result.deleted_poster_file == 0
    assert load_poster_cache_dict() == after_backup
    assert image.read_bytes() == b"new poster"


def test_delete_never_removes_external_poster_path(monkeypatch, tmp_path):
    from dataset.records import delete as records_delete
    from posters.cache import poster_identity_key

    _isolated_runtime(tmp_path, monkeypatch)
    (tmp_path / "images").mkdir()
    external = tmp_path / "user-photo.jpg"
    external.write_bytes(b"not application data")
    identity = poster_identity_key("Alpha", 2020)
    storage_data.save_dataset({"Alpha": _make_movie("Alpha", 8.0, 2020)})
    save_poster_cache_dict({identity: {"local_path": str(external)}})

    result = records_delete.delete_watched_record("Alpha")
    assert result.ok and result.deleted_poster_cache == 1 and result.deleted_poster_file == 0
    assert external.read_bytes() == b"not application data"


def test_delete_never_follows_poster_symlinks(monkeypatch, tmp_path):
    import pytest
    from dataset.records import delete as records_delete
    from posters.cache import poster_identity_key

    _isolated_runtime(tmp_path, monkeypatch)
    managed = tmp_path / "images"
    managed.mkdir()
    external_dir = tmp_path / "private"
    external_dir.mkdir()
    external = external_dir / "user-photo.jpg"
    external.write_bytes(b"not application data")
    directory_link = managed / "outside"
    file_link = managed / "alpha_2020.jpg"
    try:
        directory_link.symlink_to(external_dir, target_is_directory=True)
        file_link.symlink_to(external)
    except (NotImplementedError, OSError):
        pytest.skip("Symlinks unavailable in this environment")

    identity = poster_identity_key("Alpha", 2020)
    storage_data.save_dataset({"Alpha": _make_movie("Alpha", 8.0, 2020)})
    save_poster_cache_dict({identity: {"local_path": str(directory_link / external.name)}})

    result = records_delete.delete_watched_record("Alpha")
    assert result.ok and result.deleted_poster_cache == 1 and result.deleted_poster_file == 0
    assert external.read_bytes() == b"not application data"
    assert directory_link.is_symlink()
    assert file_link.is_symlink()


def test_delete_keeps_managed_poster_referenced_by_another_cache_entry(monkeypatch, tmp_path):
    from dataset.records import delete as records_delete
    from posters.cache import poster_identity_key

    _isolated_runtime(tmp_path, monkeypatch)
    managed = tmp_path / "images"
    managed.mkdir()
    image = managed / "shared.jpg"
    image.write_bytes(b"shared managed poster")
    alpha = poster_identity_key("Alpha", 2020)
    beta = poster_identity_key("Beta", 2021)
    entry = {"local_path": str(image), "status": "found"}
    storage_data.save_dataset({"Alpha": _make_movie("Alpha", 8.0, 2020)})
    save_poster_cache_dict({alpha: entry, beta: entry})

    result = records_delete.delete_watched_record("Alpha")
    assert result.ok and result.deleted_poster_cache == 1 and result.deleted_poster_file == 0
    assert load_poster_cache_dict() == {beta: entry}
    assert image.read_bytes() == b"shared managed poster"
