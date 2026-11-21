from __future__ import annotations

import hashlib
import json
from pathlib import Path

from candidates.pool.normalization import normalize_storage_pool
from storage.normalize import normalize_movie_tags
from storage.legacy_json.exporter import export_sqlite_to_legacy_json
from storage.legacy_json.importer import import_legacy_json_to_sqlite


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_export_sqlite_to_legacy_json_preserves_file_names(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    output_dir = tmp_path / "export"
    from storage.sqlite import watched_repository

    watched_repository.save_dataset_dict(
        {"Метод": {"main_info": {"title": "Метод", "year": 2015, "user_score": 3, "country": "Россия"}}},
        path=db_path,
    )

    report = export_sqlite_to_legacy_json(output_dir=output_dir, db_path=db_path)

    assert report["counts"]["watched/titles.json"] == 1
    for relative_path in (
        "watched/titles.json",
        "watched/meta.json",
        "candidates/pool.json",
        "candidates/criteria.json",
        "candidates/watchlist.json",
        "candidates/hidden.json",
        "settings.json",
        "cache/posters/posters.json",
    ):
        assert (output_dir / relative_path).is_file()
    assert _read_json(output_dir / "_watchbane_export.json") == {
        "format": "watchbane-legacy-json",
        "schema_version": 2,
        "watched_rating_scale": "watchbane-reaction-1-to-3",
        "watched_titles_sha256": hashlib.sha256((output_dir / "watched/titles.json").read_bytes()).hexdigest(),
    }


def test_export_sqlite_to_legacy_json_writes_complete_json_files(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    output_dir = tmp_path / "export"
    from storage.sqlite import settings_repository

    settings_repository.save_settings_dict({"ui_scale": 1.25}, path=db_path)

    export_sqlite_to_legacy_json(output_dir=output_dir, db_path=db_path)

    settings_path = output_dir / "settings.json"
    assert settings_path.read_text(encoding="utf-8").endswith("\n")
    assert _read_json(settings_path) == {"ui_scale": 1.25}
    assert (output_dir / "settings.json.tmp").exists() is False


def test_import_then_export_matches_canonicalized_legacy_data(tmp_path) -> None:
    base = tmp_path / "data"
    db_path = tmp_path / "watchbane.sqlite3"
    output_dir = tmp_path / "export"
    watched = {
        "Метод": {
            "main_info": {
                "title": "Метод",
                "year": 2015,
                "user_score": 8,
                "country": "Россия",
            },
            "raw_scores": {},
            "genre": {},
        }
    }
    pool = {"legacy": {"title": "Dark", "year": 2017, "final_score": 9}}
    payloads = {
        base / "watched" / "titles.json": watched,
        base / "watched" / "meta.json": {"Метод": {"raw_scores": {"tmdb_id": 693}}},
        base / "candidates" / "pool.json": pool,
        base / "candidates" / "criteria.json": {"pool": {"count": 50}},
        base / "candidates" / "watchlist.json": {"dark|2017": {"candidate": {"title": "Dark", "year": 2017}, "added_at": "2026-01-01T00:00:00"}},
        base / "candidates" / "hidden.json": {},
        base / "settings.json": {"ui_scale": 1.25},
        base / "cache" / "posters" / "posters.json": {"метод|2015": {"title": "Метод", "year": 2015, "status": "found"}},
    }
    for path, payload in payloads.items():
        _write_json(path, payload)

    import_legacy_json_to_sqlite(base_dir=base, db_path=db_path, create_backup=False)
    export_sqlite_to_legacy_json(output_dir=output_dir, db_path=db_path)

    expected_watched = {key: normalize_movie_tags(value) for key, value in watched.items()}
    expected_watched["Метод"]["main_info"]["user_score"] = 3
    assert _read_json(output_dir / "watched" / "titles.json") == expected_watched
    assert _read_json(output_dir / "watched" / "meta.json") == payloads[base / "watched" / "meta.json"]
    assert _read_json(output_dir / "candidates" / "pool.json") == normalize_storage_pool(pool)
    assert _read_json(output_dir / "candidates" / "criteria.json") == {"pool": {"count": 50}}
    assert _read_json(output_dir / "candidates" / "watchlist.json") == payloads[base / "candidates" / "watchlist.json"]
    assert _read_json(output_dir / "settings.json") == {"ui_scale": 1.25}
    assert _read_json(output_dir / "cache" / "posters" / "posters.json") == payloads[base / "cache" / "posters" / "posters.json"]


def test_export_modify_import_and_restore_round_trip(tmp_path) -> None:
    from storage.sqlite import watched_repository
    from storage.sqlite.backup import restore_sqlite_database

    db_path = tmp_path / "watchbane.sqlite3"
    export_dir = tmp_path / "export"
    alpha = {"Alpha": {"main_info": {"title": "Alpha", "year": 2020}}}
    beta = {"Beta": {"main_info": {"title": "Beta", "year": 2021}}}
    watched_repository.save_dataset_dict(alpha, path=db_path)
    export_sqlite_to_legacy_json(output_dir=export_dir, db_path=db_path)

    watched_repository.save_dataset_dict(beta, path=db_path)
    report = import_legacy_json_to_sqlite(base_dir=export_dir, db_path=db_path)

    assert list(watched_repository.load_dataset_dict(path=db_path)) == ["Alpha"]
    recovery_backup = Path(report["runtime_backup"])
    assert recovery_backup.is_file()

    restore_sqlite_database(recovery_backup, db_path=db_path)
    assert list(watched_repository.load_dataset_dict(path=db_path)) == ["Beta"]


def _rated(scores):
    return {
        str(index): {"main_info": {"title": f"Title {index}", "user_score": score}}
        for index, score in enumerate(scores)
    }


def _stored_ratings(path):
    from storage.sqlite import watched_repository

    return [
        item["main_info"].get("user_score")
        for item in watched_repository.load_dataset_dict(path=path).values()
    ]


def test_manifested_ratings_survive_repeated_import_and_sqlite_restore(tmp_path):
    from storage.sqlite import watched_repository
    from storage.sqlite.backup import restore_sqlite_database

    source, target = tmp_path / "source.sqlite3", tmp_path / "target.sqlite3"
    output = tmp_path / "export"
    ratings = [1, 2, 3, None]
    watched_repository.save_dataset_dict(_rated(ratings), path=source)
    watched_repository.save_dataset_dict(_rated([3, 2]), path=target)
    export_sqlite_to_legacy_json(output_dir=output, db_path=source)
    first = import_legacy_json_to_sqlite(base_dir=output, db_path=target, create_backup=False)
    assert _stored_ratings(target) == ratings
    import_legacy_json_to_sqlite(base_dir=output, db_path=target, create_backup=False)
    assert _stored_ratings(target) == ratings
    restore_sqlite_database(first["runtime_backup"], db_path=target)
    assert _stored_ratings(target) == [3, 2]

    # Historical manifest v1 was generated with the same canonical reaction
    # contract, but did not carry a digest or explicit scale.
    _write_json(output / "_watchbane_export.json", {"format": "watchbane-legacy-json", "schema_version": 1})
    import_legacy_json_to_sqlite(base_dir=output, db_path=target, create_backup=False)
    assert _stored_ratings(target) == ratings


def test_unmanifested_legacy_rating_scale_is_still_converted(tmp_path):
    source, target = tmp_path / "legacy", tmp_path / "target.sqlite3"
    _write_json(source / "watched/titles.json", _rated([0, 2, 5, 8, 10, None]))
    import_legacy_json_to_sqlite(base_dir=source, db_path=target, create_backup=False)
    assert _stored_ratings(target) == [1, 1, 2, 3, 3, None]


def test_mismatched_or_falsely_declared_ratings_are_rejected_before_mutation(tmp_path):
    import pytest
    from storage.sqlite import watched_repository

    source, target = tmp_path / "source.sqlite3", tmp_path / "target.sqlite3"
    output = tmp_path / "export"
    watched_repository.save_dataset_dict(_rated([2, 3]), path=source)
    watched_repository.save_dataset_dict(_rated([3]), path=target)
    export_sqlite_to_legacy_json(output_dir=output, db_path=source)
    manifest_path = output / "_watchbane_export.json"
    manifest = _read_json(manifest_path)
    titles_path = output / "watched/titles.json"

    # Even a canonical-looking edit fails with a stale v2 manifest.
    _write_json(titles_path, _rated([1, 2]))
    with pytest.raises(ValueError, match="does not match"):
        import_legacy_json_to_sqlite(base_dir=output, db_path=target, create_backup=False)

    # Matching checksum cannot make out-of-scale values valid canonical data.
    _write_json(titles_path, _rated([8]))
    manifest["watched_titles_sha256"] = hashlib.sha256(titles_path.read_bytes()).hexdigest()
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="Invalid canonical"):
        import_legacy_json_to_sqlite(base_dir=output, db_path=target, create_backup=False)

    _write_json(manifest_path, {"format": "watchbane-legacy-json", "schema_version": 1})
    with pytest.raises(ValueError, match="Invalid canonical"):
        import_legacy_json_to_sqlite(base_dir=output, db_path=target, create_backup=False)
    _write_json(manifest_path, {"format": "watchbane-legacy-json", "schema_version": True})
    with pytest.raises(ValueError, match="schema version"):
        import_legacy_json_to_sqlite(base_dir=output, db_path=target, create_backup=False)
    assert _stored_ratings(target) == [3]
    assert not (output / "backups").exists()
