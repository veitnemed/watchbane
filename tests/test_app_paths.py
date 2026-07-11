from __future__ import annotations

from pathlib import Path
import sqlite3

from config.app_paths import (
    APP_DIR_NAME,
    DATA_DIR_ENV,
    build_app_paths,
    get_app_paths,
    migrate_legacy_database,
)
from config import constant
from storage import profiles, runtime


def test_windows_runtime_uses_local_app_data(tmp_path) -> None:
    local_app_data = tmp_path / "LocalAppData"

    paths = get_app_paths(
        environ={"LOCALAPPDATA": str(local_app_data)},
        platform="nt",
        home=tmp_path / "home",
    )

    assert paths.root == (local_app_data / APP_DIR_NAME).resolve()
    assert paths.database_path == paths.root / "data" / "watchbane.sqlite3"
    assert paths.posters_dir == paths.root / "posters"
    assert paths.logs_dir == paths.root / "logs"
    assert paths.backups_dir == paths.root / "backups"
    assert paths.config_dir == paths.root / "config"


def test_data_dir_override_controls_complete_runtime(tmp_path) -> None:
    runtime_root = tmp_path / "portable-test-runtime"

    paths = get_app_paths(
        environ={DATA_DIR_ENV: str(runtime_root), "LOCALAPPDATA": str(tmp_path / "ignored")},
        platform="nt",
    )

    assert paths.root == runtime_root.resolve()
    assert all(path == paths.root or paths.root in path.parents for path in paths.directories())
    assert paths.database_path == runtime_root.resolve() / "data" / "watchbane.sqlite3"


def test_legacy_database_copy_creates_backup_first(tmp_path) -> None:
    source = tmp_path / "repo" / "data" / "watchbane.sqlite3"
    source.parent.mkdir(parents=True)
    connection = sqlite3.connect(source)
    try:
        connection.execute("CREATE TABLE sentinel(value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel(value) VALUES('legacy-database')")
        connection.commit()
    finally:
        connection.close()
    paths = build_app_paths(tmp_path / "runtime")

    report = migrate_legacy_database(paths=paths, source_path=source)

    backup_path = Path(str(report["backup_path"]))
    assert report["migrated"] is True
    assert report["status"] == "copied"
    assert backup_path.is_file()
    assert paths.backups_dir in backup_path.parents
    for database_path in (backup_path, paths.database_path):
        connection = sqlite3.connect(database_path)
        try:
            value = connection.execute("SELECT value FROM sentinel").fetchone()[0]
        finally:
            connection.close()
        assert value == "legacy-database"


def test_legacy_database_never_overwrites_existing_target(tmp_path) -> None:
    source = tmp_path / "repo" / "data" / "watchbane.sqlite3"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"legacy")
    paths = build_app_paths(tmp_path / "runtime")
    paths.database_path.parent.mkdir(parents=True)
    paths.database_path.write_bytes(b"current")

    report = migrate_legacy_database(paths=paths, source_path=source)

    assert report["migrated"] is False
    assert report["status"] == "target_exists"
    assert report["backup_path"] is None
    assert paths.database_path.read_bytes() == b"current"
    assert paths.backups_dir.exists() is False


def test_runtime_override_never_imports_repo_legacy_database(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "isolated"
    data_dir = runtime_root / "data"
    monkeypatch.setenv(DATA_DIR_ENV, str(runtime_root))
    monkeypatch.setattr(constant, "APP_DATA_DIR", str(data_dir))
    profiles.set_base_data_dir(data_dir)

    result = runtime.ensure_runtime_data_layout()

    assert result["legacy_database_migration"]["status"] == "custom_runtime"
    assert Path(result["sqlite_db_path"]) == data_dir / "watchbane.sqlite3"


def test_main_profile_applies_installed_poster_log_backup_and_config_paths(monkeypatch, tmp_path) -> None:
    runtime_root = tmp_path / "installed"
    monkeypatch.setenv(DATA_DIR_ENV, str(runtime_root))
    paths = get_app_paths()
    profiles.set_base_data_dir(paths.data_dir)

    profiles.apply_profile_to_constants(profiles.MAIN_PROFILE)

    assert Path(constant.APP_DATA_DIR) == paths.data_dir
    assert Path(constant.POSTERS_DIR) == paths.posters_dir
    assert Path(constant.LOGS_DIR) == paths.logs_dir
    assert Path(constant.BACKUP_DIR) == paths.backups_dir
    assert Path(constant.CONFIG_DIR) == paths.config_dir
