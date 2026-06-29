import copy
import json
import tempfile
from pathlib import Path

from candidates.keys import title_identity_key
from config import constant
from config import scheme
from common import format_score


def _make_movie(title: str, user_score: float, year: int, raw_score: float = 8.0) -> dict:
    tags_vibe = {feature: 0 for feature in constant.TAGS_VIBE}
    genre_tags = {feature: 0 for feature in constant.GENRE}

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
        scheme.TAGS_VIBE: tags_vibe,
        constant.GENRE_SECTION: genre_tags,
    }


def test_search_watched_records_requires_multiple_choice_for_similar_titles() -> None:
    from dataset.delete_record import search_watched_records_by_query

    data = {
        "Major": _make_movie("Major", 8.0, 2020),
        "Major 2": _make_movie("Major 2", 7.0, 2021),
    }

    matches = search_watched_records_by_query("Major", data=data)

    assert len(matches) == 2


def test_delete_watched_record_removes_dataset_meta_and_poster_cache(monkeypatch) -> None:
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

    saved_dataset = {}
    saved_meta = {}
    saved_cache = {}

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: copy.deepcopy(dataset))
    monkeypatch.setattr(module.storage_data, "load_meta", lambda: copy.deepcopy(meta))
    monkeypatch.setattr(module, "load_poster_cache", lambda: copy.deepcopy(poster_cache))
    monkeypatch.setattr(module.storage_data, "save_dataset", lambda payload: saved_dataset.update(payload))
    monkeypatch.setattr(module.storage_data, "save_meta", lambda payload: saved_meta.update(payload))
    monkeypatch.setattr(module, "save_poster_cache", lambda payload: saved_cache.update(payload))
    monkeypatch.setattr(module, "backup_before_watched_delete", lambda timestamp=None: ["backup-dataset"])

    result = module.delete_watched_record("Alpha", timestamp="test")

    assert result["ok"] is True
    assert result["deleted_dataset"] == 1
    assert result["deleted_meta"] == 1
    assert result["deleted_poster_cache"] == 1
    assert result.get("deleted_poster_file", 0) == 0
    assert "Alpha" not in saved_dataset
    assert "Beta" in saved_dataset
    assert "Alpha" not in saved_meta
    assert identity not in saved_cache
    assert result["dataset_count"] == 1
    assert result["backups"] == ["backup-dataset"]


def test_delete_watched_record_without_meta_or_cache(monkeypatch) -> None:
    from dataset import delete_record as module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    saved_dataset = {}

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: copy.deepcopy(dataset))
    monkeypatch.setattr(module.storage_data, "load_meta", lambda: {})
    monkeypatch.setattr(module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(module.storage_data, "save_dataset", lambda payload: saved_dataset.update(payload))
    monkeypatch.setattr(module.storage_data, "save_meta", lambda _payload: None)
    monkeypatch.setattr(module, "save_poster_cache", lambda _payload: None)
    monkeypatch.setattr(module, "backup_before_watched_delete", lambda timestamp=None: [])

    result = module.delete_watched_record("Alpha", timestamp="test")

    assert result["ok"] is True
    assert result["deleted_dataset"] == 1
    assert result["deleted_meta"] == 0
    assert result["deleted_poster_cache"] == 0
    assert saved_dataset == {}


def test_delete_watched_record_missing_entry_does_not_save(monkeypatch) -> None:
    from dataset import delete_record as module

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: {})
    monkeypatch.setattr(module, "backup_before_watched_delete", lambda timestamp=None: [])

    save_called = {"dataset": False}

    def fake_save_dataset(_payload):
        save_called["dataset"] = True

    monkeypatch.setattr(module.storage_data, "save_dataset", fake_save_dataset)

    result = module.delete_watched_record("Missing", timestamp="test")

    assert result["ok"] is False
    assert save_called["dataset"] is False


def test_backup_before_watched_delete_creates_files(monkeypatch) -> None:
    from dataset import delete_record as module

    with tempfile.TemporaryDirectory() as temp_root:
        root = Path(temp_root)
        dataset_path = root / "dataset.json"
        meta_path = root / "meta_data.json"
        cache_path = root / "posters.json"
        dataset_path.write_text("{}", encoding="utf-8")
        meta_path.write_text("{}", encoding="utf-8")
        cache_path.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(module.constant, "FILE_NAME", str(dataset_path))
        monkeypatch.setattr(module.constant, "META_JSON", str(meta_path))
        monkeypatch.setattr(module, "DEFAULT_POSTER_CACHE_JSON", cache_path)

        backups = module.backup_before_watched_delete(timestamp="123")

        assert len(backups) == 3
        assert Path(backups[0]).name == "dataset.json.backup_before_delete_123"
        assert Path(backups[1]).name == "meta_data.json.backup_before_delete_123"
        assert Path(backups[2]).name == "posters.json.backup_before_delete_123"


def test_build_watched_delete_preview(monkeypatch) -> None:
    from dataset import delete_record as module
    from posters.cache import poster_identity_key

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {"Alpha": {"main_info": dataset["Alpha"]["main_info"], "raw_scores": dataset["Alpha"]["raw_scores"]}}
    identity = poster_identity_key("Alpha", 2020)
    poster_cache = {identity: {"status": "found", "local_path": "C:/images/alpha.jpg"}}

    monkeypatch.setattr(module.storage_data, "load_meta", lambda: meta)
    monkeypatch.setattr(module, "load_poster_cache", lambda: poster_cache)

    preview = module.build_watched_delete_preview("Alpha", data=dataset)

    assert preview is not None
    assert preview["title"] == "Alpha"
    assert preview["year"] == 2020
    assert preview["has_meta"] is True
    assert preview["has_poster_cache"] is True
    assert preview["poster_local_path"] == "C:/images/alpha.jpg"


def test_delete_watched_record_does_not_touch_candidate_pool(monkeypatch) -> None:
    from dataset import delete_record as module

    with tempfile.TemporaryDirectory() as temp_root:
        root = Path(temp_root)
        pool_path = root / "candidate_pool.json"
        pool_path.write_text(json.dumps({"items": []}), encoding="utf-8")

        original_pool = pool_path.read_text(encoding="utf-8")

        dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}

        monkeypatch.setattr(module.storage_data, "load_dataset", lambda: copy.deepcopy(dataset))
        monkeypatch.setattr(module.storage_data, "load_meta", lambda: {})
        monkeypatch.setattr(module, "load_poster_cache", lambda: {})
        monkeypatch.setattr(module.storage_data, "save_dataset", lambda _payload: None)
        monkeypatch.setattr(module.storage_data, "save_meta", lambda _payload: None)
        monkeypatch.setattr(module, "save_poster_cache", lambda _payload: None)
        monkeypatch.setattr(module, "backup_before_watched_delete", lambda timestamp=None: [])
        monkeypatch.setattr(module.constant, "CANDIDATE_POOL_JSON", str(pool_path))

        module.delete_watched_record("Alpha", timestamp="test")

        assert pool_path.read_text(encoding="utf-8") == original_pool


def test_delete_watched_record_ui_cancelled_without_delete(monkeypatch) -> None:
    from ui.console import interface_funcs

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    delete_called = {"value": False}

    monkeypatch.setattr(interface_funcs.storage_data, "load_dataset", lambda: dataset)
    monkeypatch.setattr(
        interface_funcs.dataset_delete_record,
        "search_watched_records_by_query",
        lambda query, data=None: [{"dataset_key": "Alpha", "title": "Alpha", "year": 2020, "user_score": 8.0}],
    )
    monkeypatch.setattr(
        interface_funcs.dataset_delete_record,
        "build_watched_delete_preview",
        lambda dataset_key, data=None: {"title": "Alpha", "year": 2020, "user_score": 8.0, "has_meta": False, "has_poster_cache": False},
    )
    monkeypatch.setattr(
        interface_funcs.dataset_delete_record,
        "format_watched_delete_preview",
        lambda preview: "preview",
    )

    def fake_delete(_dataset_key):
        delete_called["value"] = True
        return {"ok": True}

    monkeypatch.setattr(interface_funcs.dataset_delete_record, "delete_watched_record", fake_delete)

    inputs = iter(["Alpha", "no"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

    interface_funcs.delete_watched_record()

    assert delete_called["value"] is False


def test_title_identity_key_for_poster_cache_delete() -> None:
    identity = title_identity_key({"title": "Мажор", "year": 2020})
    assert identity == "мажор|2020"
