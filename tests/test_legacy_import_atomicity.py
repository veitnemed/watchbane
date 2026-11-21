"""Fault after the last legacy-v3 write must roll back the entire profile."""
from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep

import pytest

from storage.legacy_json.exporter import export_sqlite_to_legacy_json
from storage.legacy_json.importer import import_legacy_json_to_sqlite
from storage.sqlite import poster_repository
from storage.sqlite.connection import connect


def _legacy_profile(directory, generation, offset):
    watched, saved, hidden = (f"{generation} {kind}" for kind in ("watched", "saved", "hidden"))
    date = f"2026-01-{offset:02d}T00:00:00"
    payloads = {
        "watched/titles.json": {
            watched: {"main_info": {"title": watched, "year": 2020, "user_score": offset + 6}},
        },
        "watched/meta.json": {watched: {"raw_scores": {"tmdb_id": offset + 100}}},
        "candidates/pool.json": {saved: {"title": saved, "year": 2021}},
        "candidates/criteria.json": {"pool": {"count": offset}},
        "candidates/watchlist.json": {
            saved: {"candidate": {"title": saved, "year": 2021}, "added_at": date},
        },
        "candidates/hidden.json": {
            hidden: {"candidate": {"title": hidden, "year": 2022}, "added_at": date},
        },
        "settings.json": {"ui_scale": 1 + offset / 4},
        "cache/posters/posters.json": {watched: {"title": watched, "year": 2020, "status": "found"}},
    }
    for relative, payload in payloads.items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")


_QUERIES = {
    "watched": "SELECT * FROM watched_records WHERE payload_json != '{}' ORDER BY dataset_key",
    "meta": "SELECT dataset_key, meta_json FROM watched_records WHERE meta_json IS NOT NULL ORDER BY dataset_key",
    "pool": "SELECT * FROM candidate_records ORDER BY pool_key",
    "criteria": "SELECT * FROM candidate_criteria ORDER BY criteria_name",
    "watchlist": "SELECT * FROM candidate_actions WHERE action='watchlist' ORDER BY identity_key",
    "hidden": "SELECT * FROM candidate_actions WHERE action='hidden' ORDER BY identity_key",
    "settings": "SELECT * FROM app_settings ORDER BY key",
    "posters": "SELECT * FROM poster_cache_entries ORDER BY identity_key",
}


def _snapshot(conn):
    return {section: [tuple(row) for row in conn.execute(sql)] for section, sql in _QUERIES.items()}


@pytest.fixture
def v3_import(tmp_path):
    source, target = tmp_path / "source.sqlite3", tmp_path / "target.sqlite3"
    for db, generation, offset in ((source, "replacement", 2), (target, "original", 1)):
        directory = tmp_path / generation
        _legacy_profile(directory, generation, offset)
        import_legacy_json_to_sqlite(base_dir=directory, db_path=db, create_backup=False)
    v3 = tmp_path / "v3"
    export_sqlite_to_legacy_json(output_dir=v3, db_path=source)
    manifest = json.loads((v3 / "_watchbane_export.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert len(manifest["files_sha256"]) == len(_QUERIES)
    with closing(connect(target)) as reader:
        before = _snapshot(reader)
    assert all(before.values()), "all eight existing sections must be populated"
    return v3, target, before


def test_v3_legacy_import_rolls_back_every_section_after_last_write(v3_import, monkeypatch):
    v3, target, before = v3_import

    class LateFailure(RuntimeError):
        pass

    original_write_posters = poster_repository.save_poster_cache_dict
    observed = {}

    def fail_after_real_final_write(payload, *, conn):
        original_write_posters(payload, conn=conn)
        observed.update(_snapshot(conn))
        with closing(connect(target)) as concurrent_reader:
            assert _snapshot(concurrent_reader) == before
        raise LateFailure("after the final real SQLite write")

    with monkeypatch.context() as scope:
        scope.setattr(poster_repository, "save_poster_cache_dict", fail_after_real_final_write)
        with pytest.raises(LateFailure, match="final real SQLite write"):
            import_legacy_json_to_sqlite(base_dir=v3, db_path=target, create_backup=False)
    assert observed.keys() == before.keys()
    assert all(observed[section] and observed[section] != rows for section, rows in before.items())
    with closing(connect(target)) as reopened:
        assert _snapshot(reopened) == before
        assert reopened.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def _child_pause_before_commit(v3, target, ready):
    original_write_posters = poster_repository.save_poster_cache_dict

    def pause_after_final_write(payload, *, conn):
        original_write_posters(payload, conn=conn)
        assert conn.in_transaction
        new_rows = _snapshot(conn)
        pending = ready.with_suffix(".pending")
        pending.write_text(json.dumps({"status": "READY", "rows": new_rows}), encoding="utf-8")
        pending.replace(ready)
        # The parent must terminate us. This fallback never commits.
        sleep(30)
        raise TimeoutError("the parent did not terminate the importer")

    poster_repository.save_poster_cache_dict = pause_after_final_write
    import_legacy_json_to_sqlite(base_dir=v3, db_path=target, create_backup=False)


def test_v3_import_recovers_after_process_termination_before_commit(tmp_path, v3_import):
    v3, target, before = v3_import
    ready = tmp_path / "child-ready.json"
    test_file = Path(__file__).resolve()
    child_code = (
        "from pathlib import Path; import runpy, sys; "
        "runpy.run_path(sys.argv[1])['_child_pause_before_commit']"
        "(*map(Path, sys.argv[2:]))"
    )
    with (tmp_path / "child.log").open("wb") as child_log:
        child = subprocess.Popen(
            [sys.executable, "-c", child_code, str(test_file), str(v3), str(target), str(ready)],
            cwd=test_file.parents[1],
            stdout=child_log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = monotonic() + 10
            while not ready.is_file() and child.poll() is None and monotonic() < deadline:
                sleep(0.02)
            assert ready.is_file(), (tmp_path / "child.log").read_text(encoding="utf-8", errors="replace")
            handshake = json.loads(ready.read_text(encoding="utf-8"))
            assert handshake["status"] == "READY"
            new_rows = handshake["rows"]
            assert new_rows.keys() == before.keys()
            assert all(new_rows[name] and list(map(tuple, new_rows[name])) != rows
                       for name, rows in before.items())
            assert child.poll() is None
            with closing(connect(target)) as concurrent_reader:
                assert _snapshot(concurrent_reader) == before
            assert child.poll() is None
            child.terminate()
            assert child.wait(timeout=5) != 0
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
    with closing(connect(target)) as reopened:
        assert _snapshot(reopened) == before
        assert reopened.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
