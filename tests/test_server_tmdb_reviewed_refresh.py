"""Review binding at the detached SQLite boundary; no external traffic."""
from contextlib import closing
from dataclasses import replace
from datetime import date
from hashlib import sha256
import json
import sqlite3

import pytest

from web import tmdb_reviewed_refresh as audit
from web.tmdb_catalog_audit import ReviewedLanguage
from web.tmdb_change_windows import commit_change_window, pending_change, stage_and_ack_change
from web.tmdb_ids import QueueItem


MOVIE = QueueItem("movie", 42)
TV = QueueItem("tv", 42)


def _commit(db, day, *items):
    window = date(2026, 1, day)
    commit_change_window(checkpoint=db, start=window, end=window, pages_by_media={
        media: [{"page": 1, "total_pages": 1, "results": [
            {"id": item.tmdb_id} for item in items if item.media_type == media
        ]}] for media in ("movie", "tv")
    })


def _stage(db, item, synopsis, locale, language):
    pending = pending_change(db, item)
    assert stage_and_ack_change(db, pending, staged_payload=json.dumps({
        "media_type": item.media_type, "tmdb_id": item.tmdb_id,
        "title": "Fixture " + item.media_type, "overview": synopsis, "year": 2020,
        "requested_locale": locale, "private_fixture_marker": "do not surface",
    }).encode())
    return audit.ReviewedRefresh(pending.version, locale, ReviewedLanguage(sha256(synopsis.encode()).hexdigest(),
                                                                          language))


def test_exact_typed_review_separates_provider_locale_and_reviewed_language(tmp_path):
    db = tmp_path / "changes.sqlite"
    _commit(db, 1, MOVIE, TV)
    movie = _stage(db, MOVIE, "Foreign text under a Russian request.", "ru-RU", "en")
    tv = _stage(db, TV, "Русское описание", "en-US", "ru")
    before = db.read_bytes()
    assert audit.read_reviewed_refresh(checkpoint=db, reviewed={TV: tv, MOVIE: movie}) == (
        audit.RefreshSeedRow(MOVIE, movie.version, "en-US", "Fixture movie", "Foreign text under a Russian request.", 2020),
        audit.RefreshSeedRow(TV, tv.version, "ru-RU", "Fixture tv", "Русское описание", 2020),
    )
    for bad in (replace(tv, version=tv.version + 1), replace(tv, requested_locale="ru-RU"),
                replace(tv, language=movie.language)):
        with pytest.raises(ValueError, match="refresh review|exact review"):
            audit.read_reviewed_refresh(checkpoint=db, reviewed={MOVIE: movie, TV: bad})
    assert db.read_bytes() == before


def test_review_is_a_coherent_snapshot_and_newer_pending_blocks_reuse(tmp_path, monkeypatch):
    db = tmp_path / "changes.sqlite"
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    _commit(db, 1, MOVIE, TV)
    movie = _stage(db, MOVIE, "First review", "ru-RU", "en")
    tv = _stage(db, TV, "Second review", "ru-RU", "en")
    reviews = {MOVIE: movie, TV: tv}
    committed = False

    def hashing(raw):
        nonlocal committed
        if not committed:
            committed = True
            # Concurrent writer changes only TV, between validating movie and TV.
            _commit(db, 2, TV)
        return sha256(raw)

    monkeypatch.setattr(audit, "sha256", hashing)
    assert [r.item for r in audit.read_reviewed_refresh(checkpoint=db, reviewed=reviews)] == [MOVIE, TV]
    with pytest.raises(ValueError, match="pending"):
        audit.read_reviewed_refresh(checkpoint=db, reviewed=reviews)
    tv_new = _stage(db, TV, "New second review", "ru-RU", "en")
    with pytest.raises(ValueError, match="superseded"):
        audit.read_reviewed_refresh(checkpoint=db, reviewed=reviews)
    assert audit.read_reviewed_refresh(checkpoint=db, reviewed={TV: tv_new})[0].overview == "New second review"


def test_invalid_path_or_empty_review_never_creates_database(tmp_path):
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(ValueError):
        audit.read_reviewed_refresh(checkpoint=missing, reviewed={})
    with pytest.raises(sqlite3.OperationalError):
        audit.read_reviewed_refresh(checkpoint=missing, reviewed={
            MOVIE: audit.ReviewedRefresh(1, "ru-RU", ReviewedLanguage("0" * 64, "ru"))
        })
    assert not missing.exists()
