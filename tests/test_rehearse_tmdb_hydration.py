from pathlib import Path
import gzip
import json
import os
import sqlite3
import subprocess
import sys

import pytest


_MODULE = "tools.qa.rehearse_tmdb_hydration"
_ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable, "-m", _MODULE, *map(str, args)], cwd=_ROOT,
                          text=True, capture_output=True, timeout=20, env={
                              **os.environ,
                              "TMDB_API_KEY": "inherited-key-must-not-be-used",
                              "TMDB_BEARER_TOKEN": "inherited-token-must-not-be-used",
                          })


def output(*args):
    result = run(*args)
    assert result.returncode == 0, result.stderr
    assert not result.stderr and "must-not-be-used" not in result.stdout
    return json.loads(result.stdout)


def state(checkpoint):
    with sqlite3.connect(checkpoint) as connection:
        return tuple(connection.execute("SELECT media, tmdb_id, status FROM hydration_items ORDER BY media, tmdb_id"))


def test_offline_429_stops_process_then_restarts_without_replaying_committed_item(tmp_path):
    directory = tmp_path / "trial"
    first = output("rehearse", "--checkpoint-dir", directory)
    db, = directory.iterdir()
    assert first["phase"] == "interrupted" and first["stop_reason"] == "throttled"
    assert (first["planned"], first["completed"], first["pending"], first["http_429_this_run"]) == (4, 1, 3, 1)
    assert first["attempts_this_run"] == 3
    before = state(db)
    assert len(before) == 1 and before[0][0::2] == ("movie", "hydrated")
    assert first["audit"]["by_media"]["movie"]["pending"] == 1

    second = output("rehearse", "--resume", "--checkpoint-dir", directory)
    assert second["phase"] == "resumed" and second["stop_reason"] is None and second["complete"]
    assert (second["completed_before"], second["completed_this_run"], second["pending"]) == (1, 3, 0)
    assert second["http_429_this_run"] == 0 and second["attempts_this_run"] == 5
    assert second["requests_by_media_this_run"] == {"movie": 2, "tv": 3}
    assert (second["hydrated"], second["missing_overview"], second["unavailable"]) == (2, 1, 1)
    assert before[0] in state(db)
    assert {(media, identifier) for media, identifier, _ in state(db)} == {
        ("movie", 101), ("movie", 102), ("tv", 101), ("tv", 102),
    }
    assert second["audit"]["by_media"]["tv"]["requested_locale"] == {"ru-RU": 0, "en-US": 1}
    assert second["audit"]["by_media"]["tv"]["observed_language"]["unverified"] == 1

    previous = db.read_bytes()
    third = output("rehearse", "--resume", "--checkpoint-dir", directory)
    assert third["phase"] == "already_complete" and third["attempts_this_run"] == third["completed_this_run"] == 0
    assert db.read_bytes() == previous


def test_plan_only_reads_pinned_filename_and_prints_aggregates(tmp_path):
    movie = tmp_path / "movie_ids_01_10_2026.json.gz"
    tv = tmp_path / "tv_series_ids_01_10_2026.json.gz"
    movie.write_bytes(gzip.compress(b'{"id":101,"adult":false}\n{"id":102,"adult":true}\n'))
    tv.write_bytes(gzip.compress(b'{"id":101,"adult":false}\n{"id":102}\n'))
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    args = ("plan", "--export-date", "2026-01-10", "--movie", movie, "--tv", tv, "--per-media-limit", 3)
    first = output(*args)
    assert first == output(*args)
    assert first["mode"] == "read_only_dry_run"
    assert first["planned_by_media"] == {"movie": 1, "tv": 1}
    assert first["sources"][0]["adult_rows"] == first["sources"][1]["unknown_adult_rows"] == 1
    assert str(tmp_path) not in json.dumps(first)
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert output(*args, "--cohort", 2, 0)["cohort"] == {"count": 2, "index": 0}


def test_resume_refuses_missing_unrelated_or_aliased_file_without_writes(tmp_path):
    nonexistent = tmp_path / "nonexistent"
    selection = tmp_path / "profile"
    selection.mkdir()
    db = selection / "synthetic-hydration.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE user_profile(marker TEXT)")
        connection.execute("INSERT INTO user_profile VALUES ('unrelated content')")
    before = db.read_bytes()
    for flags, target in (((), selection), (("--resume",), selection), (("--resume",), nonexistent)):
        result = run("rehearse", "--checkpoint-dir", target, *flags)
        assert result.returncode == 2 and not result.stdout and str(target) not in result.stderr
    assert db.read_bytes() == before and not nonexistent.exists()

    alias = tmp_path / "alias"
    try:
        alias.symlink_to(selection, target_is_directory=True)
    except OSError:
        return  # Symlinks may require a privilege unavailable on Windows.
    assert run("rehearse", "--resume", "--checkpoint-dir", alias).returncode == 2
    assert db.read_bytes() == before


def test_resume_refuses_surprising_sidecar_without_opening_it(tmp_path):
    directory = tmp_path / "trial"
    output("rehearse", "--checkpoint-dir", directory)
    db, = directory.iterdir()
    before = db.read_bytes()
    unrelated = tmp_path / "not-a-journal"
    unrelated.write_text("must survive", encoding="utf-8")
    try:
        db.with_name(db.name + "-journal").symlink_to(unrelated)
    except OSError:
        pytest.skip("symlink creation unavailable")
    result = run("rehearse", "--resume", "--checkpoint-dir", directory)
    assert result.returncode == 2
    assert unrelated.read_text(encoding="utf-8") == "must survive"
    assert db.read_bytes() == before
