from __future__ import annotations

import json
from pathlib import Path

from storage.sqlite import action_repository
from storage.sqlite import candidate_repository
from storage.sqlite import poster_repository
from storage.sqlite import settings_repository
from storage.sqlite import watched_repository
from storage.legacy_json.importer import import_legacy_json_to_sqlite


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _fixture(base: Path) -> dict:
    payloads = {
        "watched": {"Метод": {"main_info": {"title": "Метод", "year": 2015, "user_score": 8, "country": "Россия"}}},
        "meta": {"Метод": {"raw_scores": {"tmdb_id": 693}}},
        "pool": {"dark": {"title": "Dark", "year": 2017, "final_score": 9}},
        "criteria": {"pool": {"count": 50}},
        "watchlist": {"dark|2017": {"candidate": {"title": "Dark", "year": 2017}, "added_at": "2026-01-01T00:00:00"}},
        "hidden": {"метод|2015": {"candidate": {"title": "Метод", "year": 2015}, "hidden_at": "2026-01-01T00:00:00"}},
        "settings": {"ui_scale": 1.25},
        "posters": {"метод|2015": {"title": "Метод", "year": 2015, "status": "found", "local_path": "data/cache/posters/images/method.jpg"}},
    }
    _write_json(base / "watched" / "titles.json", payloads["watched"])
    _write_json(base / "watched" / "meta.json", payloads["meta"])
    _write_json(base / "candidates" / "pool.json", payloads["pool"])
    _write_json(base / "candidates" / "criteria.json", payloads["criteria"])
    _write_json(base / "candidates" / "watchlist.json", payloads["watchlist"])
    _write_json(base / "candidates" / "hidden.json", payloads["hidden"])
    _write_json(base / "settings.json", payloads["settings"])
    _write_json(base / "cache" / "posters" / "posters.json", payloads["posters"])
    return payloads


def test_import_legacy_json_dry_run_does_not_create_db(tmp_path) -> None:
    base = tmp_path / "data"
    db_path = tmp_path / "watchbane.sqlite3"
    _fixture(base)

    report = import_legacy_json_to_sqlite(base_dir=base, db_path=db_path, dry_run=True)

    assert report["dry_run"] is True
    assert report["counts"]["watched"] == 1
    assert db_path.exists() is False


def test_import_legacy_json_imports_all_payloads_and_creates_backup(tmp_path) -> None:
    base = tmp_path / "data"
    db_path = tmp_path / "watchbane.sqlite3"
    _fixture(base)

    report = import_legacy_json_to_sqlite(base_dir=base, db_path=db_path)

    assert report["dry_run"] is False
    assert Path(report["backup_dir"]).is_dir()
    assert (Path(report["backup_dir"]) / "watched" / "titles.json").is_file()
    assert watched_repository.load_dataset_dict(path=db_path)["Метод"]["main_info"]["title"] == "Метод"
    assert watched_repository.load_meta_dict(path=db_path)["Метод"]["raw_scores"]["tmdb_id"] == 693
    assert candidate_repository.load_candidate_pool_dict(path=db_path)["dark|2017"]["title"] == "Dark"
    assert candidate_repository.load_candidate_criteria_dict(path=db_path) == {"pool": {"count": 50}}
    assert action_repository.load_action_identities(action_repository.ACTION_WATCHLIST, path=db_path) == {"dark|2017"}
    assert action_repository.load_action_identities(action_repository.ACTION_HIDDEN, path=db_path) == {"метод|2015"}
    assert settings_repository.load_settings_dict(path=db_path) == {"ui_scale": 1.25}
    assert poster_repository.load_poster_cache_dict(path=db_path)["метод|2015"]["status"] == "found"


def test_import_legacy_json_is_idempotent(tmp_path) -> None:
    base = tmp_path / "data"
    db_path = tmp_path / "watchbane.sqlite3"
    _fixture(base)

    import_legacy_json_to_sqlite(base_dir=base, db_path=db_path)
    import_legacy_json_to_sqlite(base_dir=base, db_path=db_path)

    assert len(watched_repository.load_dataset_dict(path=db_path)) == 1
    assert len(candidate_repository.load_candidate_pool_dict(path=db_path)) == 1
    assert len(action_repository.load_candidate_actions_dict(action_repository.ACTION_HIDDEN, path=db_path)) == 1


def test_import_rejects_unknown_export_schema_without_touching_runtime(tmp_path) -> None:
    base = tmp_path / "data"
    db_path = tmp_path / "watchbane.sqlite3"
    _fixture(base)
    _write_json(
        base / "_watchbane_export.json",
        {"format": "watchbane-legacy-json", "schema_version": 999},
    )
    watched_repository.save_dataset_dict(
        {"Existing": {"main_info": {"title": "Existing", "year": 2020}}},
        path=db_path,
    )

    try:
        import_legacy_json_to_sqlite(base_dir=base, db_path=db_path)
    except ValueError as error:
        assert "schema version" in str(error)
    else:
        raise AssertionError("unknown export schema should be rejected")

    assert list(watched_repository.load_dataset_dict(path=db_path)) == ["Existing"]


def test_import_rolls_back_every_payload_when_one_repository_fails(
    tmp_path,
    monkeypatch,
) -> None:
    base = tmp_path / "data"
    db_path = tmp_path / "watchbane.sqlite3"
    _fixture(base)
    watched_repository.save_dataset_dict(
        {"Existing": {"main_info": {"title": "Existing", "year": 2020}}},
        path=db_path,
    )

    def fail_candidate_save(*_args, **_kwargs):
        raise RuntimeError("forced import failure")

    monkeypatch.setattr(candidate_repository, "save_candidate_pool_dict", fail_candidate_save)

    try:
        import_legacy_json_to_sqlite(base_dir=base, db_path=db_path)
    except RuntimeError as error:
        assert "forced import failure" in str(error)
    else:
        raise AssertionError("injected repository failure should escape")

    assert list(watched_repository.load_dataset_dict(path=db_path)) == ["Existing"]
    assert watched_repository.load_meta_dict(path=db_path) == {}
    assert candidate_repository.load_candidate_pool_dict(path=db_path) == {}
