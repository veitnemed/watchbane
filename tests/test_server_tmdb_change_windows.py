from contextlib import closing
from datetime import date
import sqlite3

import pytest

from web.tmdb_change_windows import commit_change_window


START = date(2026, 1, 1)
END = date(2026, 1, 14)


def _page(page, total, *ids):
    return {"page": page, "total_pages": total, "results": [{"id": i} for i in ids]}


def _commit(db, pages, start=START, end=END):
    return commit_change_window(checkpoint=db, start=start, end=end, pages_by_media=pages)


def _snapshot(db):
    with closing(sqlite3.connect(db)) as conn:
        return (conn.execute("SELECT completed_through FROM change_watermark").fetchone()[0],
                conn.execute("SELECT media, tmdb_id FROM change_pending ORDER BY media, tmdb_id").fetchall())


def test_typed_pages_commit_together_and_overlap_never_deletes(tmp_path):
    db = tmp_path / "changes.sqlite3"
    first = {"movie": [_page(1, 2, 11, 12), _page(2, 2, 12)], "tv": [_page(1, 1, 11)]}
    assert _commit(db, first).newly_queued == 3
    assert _commit(db, first).replayed
    assert _snapshot(db) == ("2026-01-14", [("movie", 11), ("movie", 12), ("tv", 11)])
    second = {"movie": [_page(1, 0)], "tv": [_page(1, 1, 11, 13)]}
    result = _commit(db, second, date(2026, 1, 13), date(2026, 1, 16))
    assert (result.distinct_changed, result.newly_queued, result.replayed) == (2, 1, False)
    assert _snapshot(db) == ("2026-01-16", [("movie", 11), ("movie", 12), ("tv", 11), ("tv", 13)])


@pytest.mark.parametrize("pages", [
    {"movie": [_page(1, 1, 2)]},
    {"movie": [_page(1, 2, 2)], "tv": [_page(1, 0)]},
    {"movie": [_page(1, 2, 2), _page(1, 2, 3)], "tv": [_page(1, 0)]},
    {"movie": [_page(1, 2, 2), _page(2, 1, 3)], "tv": [_page(1, 0)]},
    {"movie": [_page(1, 0, 3)], "tv": [_page(1, 0)]},
    {"movie": [_page(1, 501)], "tv": [_page(1, 0)]},
    {"movie": [_page(1, 1, True)], "tv": [_page(1, 0)]},
    {"movie": [_page(1, 1)], "tv": [{"page": 1, "total_pages": 1, "results": [{"id": 3, "media_type": "movie"}]}]},
])
def test_invalid_windows_do_not_create_or_advance_checkpoint(tmp_path, pages):
    db = tmp_path / "changes.sqlite3"
    with pytest.raises(ValueError):
        _commit(db, pages)
    assert not db.exists()
    _commit(db, {"movie": [_page(1, 1, 8)], "tv": [_page(1, 0)]})
    before = db.read_bytes()
    with pytest.raises(ValueError):
        _commit(db, pages, date(2026, 1, 14), date(2026, 1, 15))
    assert db.read_bytes() == before


def test_dates_must_advance_contiguously_and_span_at_most_14_inclusive(tmp_path):
    db = tmp_path / "changes.sqlite3"
    pages = {"movie": [_page(1, 0)], "tv": [_page(1, 0)]}
    for start, end in ((END, START), (START, date(2026, 1, 15)), ("2026-01-01", END)):
        with pytest.raises(ValueError, match="calendar dates"):
            _commit(db, pages, start, end)
    assert not db.exists()
    _commit(db, pages)
    with pytest.raises(ValueError, match="without a calendar gap"):
        _commit(db, pages, date(2026, 1, 16), date(2026, 1, 16))
    assert _snapshot(db) == ("2026-01-14", [])
    assert _commit(db, pages, date(2026, 1, 15), date(2026, 1, 15)).completed_through.day == 15


def test_database_error_after_queue_writes_rolls_back_queue_and_watermark(tmp_path):
    db = tmp_path / "changes.sqlite3"
    _commit(db, {"movie": [_page(1, 1, 12)], "tv": [_page(1, 0)]})
    before = _snapshot(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("""CREATE TRIGGER fail_watermark BEFORE UPDATE ON change_watermark
                        BEGIN SELECT raise(ABORT, 'fixture failure after queue writes'); END""")
    pages = {"movie": [_page(1, 1, 13)], "tv": [_page(1, 1, 13)]}
    with pytest.raises(sqlite3.IntegrityError, match="fixture failure"):
        _commit(db, pages, END, date(2026, 1, 15))
    assert _snapshot(db) == before
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DROP TRIGGER fail_watermark")
    assert _commit(db, pages, END, date(2026, 1, 15)).newly_queued == 2


def test_detached_change_completion_uses_monotonic_typed_ticket_and_atomic_ack(tmp_path):
    import json
    from web.tmdb_change_windows import pending_change, stage_and_ack_change
    from web.tmdb_ids import QueueItem

    db = tmp_path / "changes.sqlite3"
    movie, tv = QueueItem("movie", 17), QueueItem("tv", 17)

    def staged(item, overview):
        return json.dumps({"media_type": item.media_type, "tmdb_id": item.tmdb_id,
                           "requested_locale": "ru-RU", "title": "Fixture", "overview": overview}).encode()

    def completed():
        with closing(sqlite3.connect(db)) as conn:
            return conn.execute("SELECT media, tmdb_id, version, payload FROM change_completed").fetchall()

    a = {"movie": [_page(1, 1, 17)], "tv": [_page(1, 1, 17)]}
    b = {"movie": [_page(1, 1, 17)], "tv": [_page(1, 0)]}
    _commit(db, a)
    fetched, tv_before = pending_change(db, movie), pending_change(db, tv)
    payload_a = staged(movie, "A result fetched before B")
    next_day = date(2026, 1, 15)
    assert _commit(db, b, next_day, next_day).newly_queued == 0
    ticket_b = pending_change(db, movie)
    assert ticket_b.version > fetched.version
    assert _commit(db, b, next_day, next_day).replayed
    assert pending_change(db, movie) == ticket_b
    assert not stage_and_ack_change(db, fetched, staged_payload=payload_a)
    assert pending_change(db, movie) == ticket_b and pending_change(db, tv) == tv_before
    assert completed() == []

    payload_b = staged(movie, "B result")
    with pytest.raises(ValueError, match="Invalid typed"):
        stage_and_ack_change(db, ticket_b, staged_payload=staged(tv, "Wrong type"))
    for extra in (b',"tmdb_id":17}', b',"anything":NaN}'):
        with pytest.raises(ValueError, match="Invalid typed"):
            stage_and_ack_change(db, ticket_b, staged_payload=payload_b[:-1] + extra)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("""CREATE TRIGGER fail_complete BEFORE INSERT ON change_completed
                        BEGIN SELECT raise(ABORT, 'failed private write'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="failed private write"):
        stage_and_ack_change(db, ticket_b, staged_payload=payload_b)
    assert pending_change(db, movie) == ticket_b and completed() == []
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DROP TRIGGER fail_complete")
    assert stage_and_ack_change(db, ticket_b, staged_payload=payload_b)
    assert completed() == [("movie", 17, ticket_b.version, payload_b)]
    assert pending_change(db, movie) is None and pending_change(db, tv) == tv_before
    assert not stage_and_ack_change(db, ticket_b, staged_payload=payload_b)
    assert _commit(db, b, next_day, next_day).replayed
    assert pending_change(db, movie) is None

    third = date(2026, 1, 16)
    assert _commit(db, b, third, third).newly_queued == 1
    assert pending_change(db, movie).version > ticket_b.version
    assert not stage_and_ack_change(db, ticket_b, staged_payload=payload_b)
    assert completed() == [("movie", 17, ticket_b.version, payload_b)]


def test_existing_legacy_pending_rows_survive_migration(tmp_path):
    from web.tmdb_change_windows import pending_change
    from web.tmdb_ids import QueueItem

    db = tmp_path / "legacy.sqlite3"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("CREATE TABLE change_watermark (singleton INTEGER PRIMARY KEY, completed_through TEXT, signature TEXT)")
        conn.execute("INSERT INTO change_watermark VALUES (1, '2026-01-14', 'fixture')")
        conn.execute("CREATE TABLE change_pending (media TEXT, tmdb_id INTEGER, PRIMARY KEY(media, tmdb_id))")
        conn.executemany("INSERT INTO change_pending VALUES (?, ?)", [("movie", 17), ("tv", 17)])
    movie = QueueItem("movie", 17)
    tv = QueueItem("tv", 17)
    assert pending_change(db, movie).version == pending_change(db, tv).version == 0
    b = {"movie": [_page(1, 1, 17)], "tv": [_page(1, 0)]}
    day = date(2026, 1, 15)
    assert _commit(db, b, day, day).newly_queued == 0
    assert pending_change(db, movie).version == day.toordinal()
    assert pending_change(db, tv).version == 0
    assert _snapshot(db)[0] == "2026-01-15"


def test_completion_never_creates_a_missing_checkpoint(tmp_path):
    from web.tmdb_change_windows import PendingChange, stage_and_ack_change
    from web.tmdb_ids import QueueItem

    db = tmp_path / "missing.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        stage_and_ack_change(db, PendingChange(QueueItem("movie", 17), 0), staged_payload=(
            b'{"media_type":"movie","tmdb_id":17,"requested_locale":"ru-RU","title":"Test","overview":"Fixture"}'
        ))
    assert not db.exists()
