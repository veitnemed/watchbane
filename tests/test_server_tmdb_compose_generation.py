"""Fixture-only composition and atomicity checks through the real seed loader."""
from contextlib import closing
from datetime import date
from hashlib import sha256
import json
import sqlite3

import pytest

from candidates.story_seed_snapshot import load_seed_snapshot_with_digest
from web import tmdb_compose_generation as composer
from web.tmdb_catalog_audit import ReviewedLanguage
from web.tmdb_change_windows import commit_change_window, pending_change, stage_and_ack_change
from web.tmdb_ids import QueueItem
from web.tmdb_reviewed_refresh import ReviewedRefresh


MOVIE = QueueItem("movie", 42)
TV = QueueItem("tv", 42)
NEW = QueueItem("tv", 43)


def _commit(db, day, *items):
    dt = date(2026, 1, day)
    commit_change_window(checkpoint=db, start=dt, end=dt, pages_by_media={
        media: [{"page": 1, "total_pages": 1, "results": [
            {"id": i.tmdb_id} for i in items if i.media_type == media
        ]}] for media in ("movie", "tv")
    })


def _stage(db, item, text, *, locale="ru-RU", language="ru"):
    ticket = pending_change(db, item)
    assert stage_and_ack_change(db, ticket, staged_payload=json.dumps({
        "media_type": item.media_type, "tmdb_id": item.tmdb_id, "title": "Updated fixture",
        "overview": text, "year": 2025, "requested_locale": locale,
        "private_marker": "do not leak",
    }, ensure_ascii=False).encode())
    return ReviewedRefresh(ticket.version, locale, ReviewedLanguage(sha256(text.encode()).hexdigest(), language))


@pytest.fixture
def generation(tmp_path):
    previous, checkpoint, output = (tmp_path / name for name in ("base.jsonl", "changes.sqlite", "next.jsonl"))
    rows = [
        {"media_type": item.media_type, "tmdb_id": item.tmdb_id, "title": "Fixture " + item.media_type,
         "overview": "Исходное описание", "year": 2020, "language": "ru-RU",
         "poster_path": f"/approved_{item.media_type}.png", "ignored": "not seed data"} for item in (TV, MOVIE)
    ]
    previous.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    base_bytes = previous.read_bytes()
    _commit(checkpoint, 1, MOVIE, NEW)
    reviews = {
        NEW: _stage(checkpoint, NEW, "A separate new title", locale="en-US", language="en"),
        MOVIE: _stage(checkpoint, MOVIE, "Новое описание фильма"),
    }
    return dict(previous=previous, previous_sha256=sha256(base_bytes).hexdigest(), checkpoint=checkpoint,
                output=output, reviewed=reviews, use_cleared=True)


def test_fixture_composes_exact_typed_and_unchanged_rows_deterministically(generation, tmp_path):
    before = generation["previous"].read_bytes()
    old_rows, old_digest = load_seed_snapshot_with_digest(generation["previous"])
    result = composer.compose_reviewed_generation(**generation)
    new_rows, sha = load_seed_snapshot_with_digest(generation["output"])
    assert result == composer.ComposedGeneration(
        old_digest, sha, 3, 1, 1,
        tuple(sorted(generation["reviewed"].items(), key=lambda pair: pair[0].key)),
    )
    assert new_rows[TV.key] == old_rows[TV.key]
    assert new_rows[MOVIE.key]["poster_path"] == old_rows[MOVIE.key]["poster_path"]
    assert new_rows[MOVIE.key]["overview"] == "Новое описание фильма"
    assert set(new_rows[NEW.key]["localized"]) == {"en"}
    raw = generation["output"].read_bytes()
    assert list(new_rows) == [TV.key, MOVIE.key, NEW.key]
    assert b"ignored" not in raw and b"private_marker" not in raw
    composer.compose_reviewed_generation(**{**generation, "output": tmp_path / "second.jsonl",
                                            "reviewed": dict(reversed(tuple(generation["reviewed"].items())))})
    assert (tmp_path / "second.jsonl").read_bytes() == raw
    assert generation["previous"].read_bytes() == before


def test_declines_uncleared_wrong_digest_stale_review_and_no_overwrite(generation):
    before = generation["previous"].read_bytes()
    for overrides, error in (
        ({"use_cleared": False}, PermissionError), ({"previous_sha256": "0" * 64}, ValueError),
        ({"output": generation["previous"]}, FileExistsError),
    ):
        with pytest.raises(error):
            composer.compose_reviewed_generation(**{**generation, **overrides})
        assert not generation["output"].exists() and generation["previous"].read_bytes() == before
    _commit(generation["checkpoint"], 2, MOVIE)
    with pytest.raises(ValueError, match="pending"):
        composer.compose_reviewed_generation(**generation)
    assert not generation["output"].exists() and generation["previous"].read_bytes() == before


def test_atomic_link_race_and_size_error_leave_no_artifacts(generation, monkeypatch):
    output = generation["output"]
    before = generation["previous"].read_bytes()
    with monkeypatch.context() as scoped:
        scoped.setattr(composer, "MAX_LINE_BYTES", 20)
        with pytest.raises(ValueError, match="size limits"):
            composer.compose_reviewed_generation(**generation)
        assert not output.exists()
    original_link = composer.os.link

    def competitor(source, target):
        output.write_bytes(b"competitor")
        original_link(source, target)

    monkeypatch.setattr(composer.os, "link", competitor)
    with pytest.raises(FileExistsError):
        composer.compose_reviewed_generation(**generation)
    assert output.read_bytes() == b"competitor" and generation["previous"].read_bytes() == before
    assert not tuple(output.parent.glob(".tmdb-generation-*"))


def test_english_fallback_cannot_remove_preexisting_russian_search_coverage(generation):
    before = generation["previous"].read_bytes()
    _commit(generation["checkpoint"], 2, MOVIE)
    generation["reviewed"][MOVIE] = _stage(generation["checkpoint"], MOVIE, "English fallback", locale="en-US", language="en")
    with pytest.raises(ValueError, match="Russian search coverage"):
        composer.compose_reviewed_generation(**generation)
    assert generation["previous"].read_bytes() == before and not generation["output"].exists()

def test_pre_switch_checks_digest_and_keeps_old_state_for_pending_or_completed_newer_version(generation):
    receipt = composer.compose_reviewed_generation(**generation)
    output, db = generation["output"], generation["checkpoint"]
    raw = output.read_bytes()
    seen = []
    args = dict(checkpoint=db, generation=output, receipt=receipt,
                switch_local=lambda *payload: seen.append(payload), use_cleared=True)
    output.write_bytes(raw.replace(b"Updated fixture", b"Mutated fixture"))
    with pytest.raises(ValueError, match="does not match"):
        composer.apply_reviewed_generation_locally(**args)
    output.write_bytes(raw)
    _commit(db, 2, MOVIE)
    with pytest.raises(ValueError, match="pending"):
        composer.apply_reviewed_generation_locally(**args)
    # Even an identical synopsis staged under a new monotonic ticket is stale.
    _stage(db, MOVIE, "Новое описание фильма")
    with pytest.raises(ValueError, match="superseded"):
        composer.apply_reviewed_generation_locally(**args)
    assert seen == []


def test_switch_excludes_same_checkpoint_writer_on_real_wal_and_uses_verified_rows(generation):
    db, output = generation["checkpoint"], generation["output"]
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    receipt = composer.compose_reviewed_generation(**generation)
    original_bytes = output.read_bytes()
    active = (receipt.previous_sha256, None)

    def switch(expected, candidate, snapshot):
        nonlocal active
        assert active[0] == expected
        # A new window cannot advance during the check-to-switch interval even
        # in WAL mode, with an independent SQLite writer connection.
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            _commit(db, 2, MOVIE)
        assert pending_change(db, MOVIE) is None
        # Simulate a local file being edited after validation. The callback has
        # the validated bytes' snapshot and never reopens this pathname.
        output.write_bytes(original_bytes.replace(b"Updated fixture", b"Mutated fixture"))
        assert snapshot[MOVIE.key]["title"] == "Updated fixture"
        active = (candidate, snapshot)

    composer.apply_reviewed_generation_locally(
        checkpoint=db, generation=output, receipt=receipt, switch_local=switch, use_cleared=True,
    )
    assert active[0] == receipt.sha256 and active[1][MOVIE.key]["title"] == "Updated fixture"
    _commit(db, 2, MOVIE)
    assert pending_change(db, MOVIE).version > generation["reviewed"][MOVIE].version


def test_local_switch_failure_does_not_leave_writer_reserved(generation):
    receipt = composer.compose_reviewed_generation(**generation)
    db = generation["checkpoint"]

    def decline(*_):
        raise RuntimeError("active generation changed")

    args = dict(checkpoint=db, generation=generation["output"], receipt=receipt, switch_local=decline)
    with pytest.raises(PermissionError):
        composer.apply_reviewed_generation_locally(**args)
    with pytest.raises(RuntimeError, match="active generation changed"):
        composer.apply_reviewed_generation_locally(**args, use_cleared=True)
    _commit(db, 2, MOVIE)


def test_preactivation_fails_closed_on_busy_or_missing_checkpoint(generation, tmp_path):
    receipt = composer.compose_reviewed_generation(**generation)

    def unexpected(*_):
        pytest.fail("A failed fence must not call the switch")

    db = generation["checkpoint"]
    args = dict(generation=generation["output"], receipt=receipt, switch_local=unexpected, use_cleared=True)
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        composer.apply_reviewed_generation_locally(checkpoint=missing, **args)
    assert not missing.exists()
    with closing(sqlite3.connect(db)) as writer:
        writer.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            composer.apply_reviewed_generation_locally(checkpoint=db, **args)
