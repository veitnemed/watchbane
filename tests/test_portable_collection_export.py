import hashlib
import json
import sqlite3
from pathlib import Path
import subprocess
import sys

import pytest

from storage.sqlite import action_repository, candidate_repository, poster_repository, settings_repository, watched_repository


def _run(*args):
    return subprocess.run([sys.executable, "-m", *map(str, args)], check=True, capture_output=True, text=True)


def _snapshot(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file()}


def test_two_profile_cli_portability_without_source_or_destination_leak(tmp_path):
    src, dst = tmp_path / "source", tmp_path / "destination"
    src.mkdir()
    dst.mkdir()
    db, target, bundle = src / "watchbane.db", dst / "watchbane.db", tmp_path / "portable"
    watched = {f"Fixture {i}": {"main_info": {"title": f"Fixture {i}", "user_score": i,
                "year": 2000 + i, "media_type": "movie", "watched_at": "2025-05-13"},
                "raw_scores": {"tmdb_id": 100 + i}} for i in (1, 2, 3)}
    watched_repository.save_dataset_dict(watched, path=db)
    settings_repository.save_settings_dict({
        "ui_scale": 1.25, "interface_language": "en", "data_language": "/fixture/raw",
        "auto_pool_refill": False, "fts_search_enabled": {"private": "sentinel_settings_nested"},
        "story_search.model_dir": "/fixture/sentinel_source_model",
        "fixture_auth": "sentinel_source_auth",
    }, path=db)
    watched_repository.save_meta_dict({"Fixture 1": {"raw_scores": {"tmdb_id": 101}, "note": "Fixture metadata"}}, path=db)
    settings_repository.save_settings_dict({
        "story_search.mode": "lexical", "ui_scale": 1.0, "data_language": "ru",
        "story_search.model_dir": "/fixture/sentinel_target_model",
        "fixture_auth": "sentinel_target_auth",
    }, path=target)
    for database, label in ((db, "source"), (target, "target")):
        candidate_repository.save_candidate_pool_dict({
            "fixture|2020": {"title": f"sentinel_{label}_pool", "year": 2020, "tmdb_id": 220, "media_type": "movie"}
        }, path=database, purge_watched=False)
        candidate_repository.save_candidate_criteria_dict({"pool": {"note": f"sentinel_{label}_criteria"}}, path=database)
        poster_repository.save_poster_cache_dict({
            "fixture": {"title": "Fixture", "year": 2020, "status": "found",
                        "local_path": f"/fixture/sentinel_{label}_poster.png"}
        }, path=database)
    target_pool = candidate_repository.load_candidate_pool_dict(path=target)
    target_criteria = candidate_repository.load_candidate_criteria_dict(path=target)
    assert "sentinel_target_pool" in str(target_pool)
    assert "sentinel_target_criteria" in str(target_criteria)
    source_cache = poster_repository.load_poster_cache_dict(path=db)
    target_cache = poster_repository.load_poster_cache_dict(path=target)
    assert "sentinel_source_poster" in str(source_cache)
    assert "sentinel_target_poster" in str(target_cache)
    saved = {"tmdb:movie:220": {"candidate": {"title": "Saved", "year": 2020, "tmdb_id": 220, "media_type": "movie"},
                            "added_at": "2025-01-02T00:00:00Z"}}
    hidden = {"tmdb:tv:220": {"candidate": {"title": "Hidden", "year": 2020, "tmdb_id": 220, "media_type": "tv"},
                            "hidden_at": "2025-01-03T00:00:00Z"}}
    action_repository.save_candidate_actions_dict(action_repository.ACTION_WATCHLIST, saved, path=db)
    action_repository.save_candidate_actions_dict(action_repository.ACTION_HIDDEN, hidden, path=db)

    _run("tools.migrations.export_sqlite_to_json", "--portable", "--db-path", db, "--output-dir", bundle)
    before = _snapshot(bundle)
    manifest = json.loads((bundle / "_watchbane_export.json").read_text())
    assert manifest["schema_version"] == 4 and len(manifest["files_sha256"]) == 8
    assert all(before[name] == sha for name, sha in manifest["files_sha256"].items())
    for path in bundle.rglob("*.json"):
        assert "sentinel_" not in path.read_text()
    assert json.loads((bundle / "settings.json").read_text()) == {
        "ui_scale": 1.25, "interface_language": "en", "auto_pool_refill": False,
    }
    for p in ("cache/posters/posters.json", "candidates/pool.json", "candidates/criteria.json"):
        assert json.loads((bundle / p).read_text()) == {}

    report = json.loads(_run("tools.migrations.migrate_json_to_sqlite", "--base-dir", bundle,
                             "--db-path", target).stdout)
    assert report["schema_version"] == 4 and report["backup_dir"] is None
    backup = Path(report["runtime_backup"])
    assert backup.is_file() and backup.parent == dst / "backups"
    assert _snapshot(bundle) == before
    target_settings = settings_repository.load_settings_dict(path=target)
    assert target_settings == {"story_search.mode": "lexical", "ui_scale": 1.25, "interface_language": "en", "data_language": "ru",
                               "auto_pool_refill": False, "story_search.model_dir": "/fixture/sentinel_target_model",
                               "fixture_auth": "sentinel_target_auth"}
    assert poster_repository.load_poster_cache_dict(path=target) == target_cache
    assert poster_repository.load_poster_cache_dict(path=db) == source_cache
    assert candidate_repository.load_candidate_pool_dict(path=target) == target_pool
    assert candidate_repository.load_candidate_criteria_dict(path=target) == target_criteria
    restored = watched_repository.load_dataset_dict(path=target)
    assert sorted(x["main_info"]["user_score"] for x in restored.values()) == [1, 2, 3]
    assert all(x["main_info"]["watched_at"] == "2025-05-13" for x in restored.values())
    assert watched_repository.load_meta_dict(path=target)["Fixture 1"]["note"] == "Fixture metadata"
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT media_type, tmdb_id FROM watched_records ORDER BY tmdb_id").fetchall() == [
            ("movie", 101), ("movie", 102), ("movie", 103),
        ]
    assert action_repository.load_candidate_actions_dict(action_repository.ACTION_WATCHLIST, path=target) == saved
    assert action_repository.load_candidate_actions_dict(action_repository.ACTION_HIDDEN, path=target) == hidden
    before_repeat = {k: v for k, v in _snapshot(dst).items() if not k.endswith(("-shm", "-wal"))}
    with pytest.raises(subprocess.CalledProcessError) as refused:
        _run("tools.migrations.migrate_json_to_sqlite", "--base-dir", bundle, "--db-path", target)
    assert "empty destination collection" in refused.value.stderr
    assert {k: v for k, v in _snapshot(dst).items() if not k.endswith(("-shm", "-wal"))} == before_repeat
    assert _snapshot(bundle) == before


def test_portable_import_rejects_machine_settings_and_inside_destination(tmp_path):
    from storage.legacy_json.exporter import export_sqlite_to_legacy_json
    from storage.legacy_json.importer import import_legacy_json_to_sqlite

    src, bundle, dst = tmp_path / "src.db", tmp_path / "portable", tmp_path / "dst.db"
    settings_repository.save_settings_dict({"ui_scale": 1.25}, path=src)
    settings_repository.save_settings_dict({"ui_scale": 1.0}, path=dst)
    export_sqlite_to_legacy_json(db_path=src, output_dir=bundle, portable=True)
    before = _snapshot(bundle)
    with pytest.raises(ValueError, match="outside"):
        import_legacy_json_to_sqlite(base_dir=bundle, db_path=bundle / "target.db")
    assert _snapshot(bundle) == before

    data = b'{"ui_scale": 1.25, "story_search.model_dir": "/fixture/sentinel"}'
    (bundle / "settings.json").write_bytes(data)
    manifest_path = bundle / "_watchbane_export.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files_sha256"]["settings.json"] = hashlib.sha256(data).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="machine-specific"):
        import_legacy_json_to_sqlite(base_dir=bundle, db_path=dst)
    assert settings_repository.load_settings_dict(path=dst) == {"ui_scale": 1.0}
    assert not (tmp_path / "backups").exists()


def test_portable_import_rechecks_concurrent_destination_write(tmp_path, monkeypatch):
    from storage.legacy_json import importer
    from storage.legacy_json.exporter import export_sqlite_to_legacy_json

    src, bundle, dst = tmp_path / "src.db", tmp_path / "portable", tmp_path / "dst.db"
    settings_repository.save_settings_dict({"ui_scale": 1.25}, path=src)
    settings_repository.save_settings_dict({"ui_scale": 1.0}, path=dst)
    export_sqlite_to_legacy_json(db_path=src, output_dir=bundle, portable=True)
    before = _snapshot(bundle)
    original = importer.backup_sqlite_database
    row = {"candidate": {"title": "Concurrent", "year": 2020},
           "added_at": "2025-01-02T00:00:00Z"}

    def intervening_write(**kwargs):
        backup = original(**kwargs)
        action_repository.save_candidate_actions_dict(
            action_repository.ACTION_WATCHLIST, {"concurrent|2020": row}, path=dst,
        )
        return backup

    monkeypatch.setattr(importer, "backup_sqlite_database", intervening_write)
    with pytest.raises(ValueError, match="empty destination collection"):
        importer.import_legacy_json_to_sqlite(base_dir=bundle, db_path=dst)
    assert action_repository.load_candidate_actions_dict(action_repository.ACTION_WATCHLIST, path=dst) == {
        "concurrent|2020": row,
    }
    assert settings_repository.load_settings_dict(path=dst) == {"ui_scale": 1.0}
    assert _snapshot(bundle) == before


@pytest.mark.parametrize("case, error", [
    ("saved_hidden", "Saved, Hidden"),
    ("watched_saved", "Watched, Saved"),
    ("duplicate_watched", "Watched, Watched"),
    ("duplicate_saved", "Saved, Saved"),
    ("different_action_id", "action key"),
])
def test_portable_conflict_rejected_before_export_or_import_writes(tmp_path, case, error):
    from storage.legacy_json.exporter import export_sqlite_to_legacy_json
    from storage.legacy_json.importer import import_legacy_json_to_sqlite

    db, private, portable = tmp_path / "source.db", tmp_path / "private", tmp_path / "portable"
    target = tmp_path / "destination" / "watchbane.db"
    entry = {"candidate": {"title": "Film fixture", "tmdb_id": 700, "media_type": "movie"}}
    record = {"main_info": {"title": "Film fixture", "user_score": 2}, "raw_scores": {"tmdb_id": 700}}
    if case != "duplicate_watched":
        mapping = {"tmdb:movie:701" if case == "different_action_id" else "tmdb:movie:700": entry}
        if case == "duplicate_saved":
            mapping["different title|2020|movie"] = entry
        action_repository.save_candidate_actions_dict(action_repository.ACTION_WATCHLIST, mapping, path=db)
    if case == "saved_hidden":
        action_repository.save_candidate_actions_dict(
            action_repository.ACTION_HIDDEN, {"tmdb:movie:700": entry}, path=db,
        )
    if case in {"watched_saved", "duplicate_watched"}:
        keys = ["Film fixture"] if case == "watched_saved" else ["Film fixture", "Alternate title"]
        watched_repository.save_dataset_dict({key: record for key in keys}, path=db)
        watched_repository.save_meta_dict({key: {"media_type": "film"} for key in keys}, path=db)

    # Exact v3 still supports diagnostics and recovery, including ambiguous states.
    export_sqlite_to_legacy_json(db_path=db, output_dir=private)
    assert import_legacy_json_to_sqlite(base_dir=private, db_path=tmp_path / "recovery.db")["ok"]
    source_before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match=error):
        export_sqlite_to_legacy_json(db_path=db, output_dir=portable, portable=True)
    assert not portable.exists()
    assert {k: v for k, v in _snapshot(tmp_path).items() if not k.endswith(("-shm", "-wal"))} == {
        k: v for k, v in source_before.items() if not k.endswith(("-shm", "-wal"))
    }

    # A portable manifest from before preflight may contain that same collection.
    manifest_path = private / "_watchbane_export.json"
    manifest = json.loads(manifest_path.read_text())
    manifest_path.write_text(json.dumps({**manifest, "schema_version": 4}))
    target.parent.mkdir()
    settings_repository.save_settings_dict({"ui_scale": 1.25}, path=target)
    target_before = {k: v for k, v in _snapshot(target.parent).items() if not k.endswith(("-shm", "-wal"))}
    bundle_before = _snapshot(private)
    for dry_run in (True, False):
        with pytest.raises(ValueError, match=error):
            import_legacy_json_to_sqlite(base_dir=private, db_path=target, dry_run=dry_run)
    assert _snapshot(private) == bundle_before
    assert {k: v for k, v in _snapshot(target.parent).items() if not k.endswith(("-shm", "-wal"))} == target_before


def test_portable_validator_does_not_infer_typed_identity_from_unknown_records():
    from storage.legacy_json.portable import validate_portable_collection

    validate_portable_collection(
        watched={
            "same|2020": {"main_info": {"title": "Same"}, "raw_scores": {"tmdb_id": 8}},
            "another|2020": {"main_info": {"title": "Same", "media_type": "unknown"}, "raw_scores": {"tmdb_id": 8}},
        },
        meta={},
        watchlist={"same|2020|tv": {"candidate": {"title": "Same", "tmdb_id": 8, "media_type": "tv"}}},
        hidden={"same|2020|movie": {"candidate": {"title": "Same", "tmdb_id": 8, "media_type": "movie"}}},
    )
