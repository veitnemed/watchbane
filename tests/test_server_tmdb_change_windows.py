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
