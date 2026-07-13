from __future__ import annotations

from storage.sqlite.connection import connect
from storage.sqlite.impression_repository import (
    get_impression,
    get_recently_seen,
    get_shown_counts,
    record_impressions,
)
from storage.sqlite.migrations import MIGRATIONS, apply_migrations, get_current_schema_version


def _candidate(title: str, *, media_type: str = "tv", year: int = 2024) -> dict:
    return {"title": title, "year": year, "media_type": media_type}


def test_first_impression_creates_history_row(tmp_path) -> None:
    db_path = tmp_path / "impressions.sqlite3"

    written = record_impressions(
        [_candidate("Alpha")],
        deck_id="deck-1",
        shown_at="2026-07-11T10:00:00+00:00",
        path=db_path,
    )

    impression = get_impression("alpha|2024", "tv", path=db_path)
    assert written == 1
    assert impression == {
        "identity_key": "alpha|2024",
        "media_type": "tv",
        "shown_count": 1,
        "first_shown_at": "2026-07-11T10:00:00+00:00",
        "last_shown_at": "2026-07-11T10:00:00+00:00",
        "last_deck_id": "deck-1",
    }


def test_repeat_updates_count_and_last_shown_but_preserves_first(tmp_path) -> None:
    db_path = tmp_path / "impressions.sqlite3"
    candidate = _candidate("Alpha")
    record_impressions([candidate], deck_id="deck-1", shown_at="2026-07-10T10:00:00+00:00", path=db_path)

    record_impressions([candidate], deck_id="deck-2", shown_at="2026-07-11T10:00:00+00:00", path=db_path)

    impression = get_impression("alpha|2024", "tv", path=db_path)
    assert impression["shown_count"] == 2
    assert impression["first_shown_at"] == "2026-07-10T10:00:00+00:00"
    assert impression["last_shown_at"] == "2026-07-11T10:00:00+00:00"
    assert impression["last_deck_id"] == "deck-2"


def test_media_type_is_part_of_unique_identity(tmp_path) -> None:
    db_path = tmp_path / "impressions.sqlite3"

    record_impressions(
        [_candidate("Shared", media_type="tv"), _candidate("Shared", media_type="movie")],
        deck_id="deck-media",
        path=db_path,
    )

    assert get_impression("shared|2024", "tv", path=db_path)["shown_count"] == 1
    assert get_impression("shared|2024", "movie", path=db_path)["shown_count"] == 1


def test_batch_insert_and_update_counts_each_unique_item_once(tmp_path) -> None:
    db_path = tmp_path / "impressions.sqlite3"
    alpha = _candidate("Alpha")
    beta = _candidate("Beta", media_type="movie")

    first_count = record_impressions([alpha, beta, alpha], deck_id="deck-1", path=db_path)
    second_count = record_impressions([alpha, beta], deck_id="deck-2", path=db_path)

    assert first_count == 2
    assert second_count == 2
    assert get_shown_counts([alpha, beta], path=db_path) == {
        ("alpha|2024", "tv"): 2,
        ("beta|2024", "movie"): 2,
    }


def test_recently_seen_filters_strictly_after_cutoff(tmp_path) -> None:
    db_path = tmp_path / "impressions.sqlite3"
    record_impressions(
        [_candidate("Old")],
        shown_at="2026-07-01T00:00:00+00:00",
        path=db_path,
    )
    record_impressions(
        [_candidate("New")],
        shown_at="2026-07-11T00:00:00+00:00",
        path=db_path,
    )

    recent = get_recently_seen("2026-07-05T00:00:00+00:00", path=db_path)

    assert [(row["identity_key"], row["media_type"]) for row in recent] == [("new|2024", "tv")]


def test_recent_cutoff_normalizes_timezone_offsets_to_one_instant(tmp_path) -> None:
    db_path = tmp_path / "impressions.sqlite3"
    record_impressions(
        [_candidate("Boundary")],
        shown_at="2026-06-11T15:00:00+03:00",
        path=db_path,
    )

    at_same_instant = get_recently_seen(
        "2026-06-11T12:00:00+00:00",
        path=db_path,
    )
    one_second_before = get_recently_seen(
        "2026-06-11T11:59:59+00:00",
        path=db_path,
    )

    assert at_same_instant == []
    assert [row["identity_key"] for row in one_second_before] == ["boundary|2024"]
    assert get_impression("boundary|2024", "tv", path=db_path)["last_shown_at"] == (
        "2026-06-11T12:00:00+00:00"
    )


def test_v4_migration_upgrades_nonempty_v3_database(tmp_path) -> None:
    db_path = tmp_path / "impressions.sqlite3"
    conn = connect(db_path)
    try:
        assert apply_migrations(conn, migrations=MIGRATIONS[:3]) == 3
        conn.execute("CREATE TABLE preserved_marker(value TEXT NOT NULL)")
        conn.execute("INSERT INTO preserved_marker(value) VALUES('kept')")
        conn.commit()

        assert apply_migrations(conn) == 6
        assert get_current_schema_version(conn) == 6
        assert conn.execute("SELECT value FROM preserved_marker").fetchone()["value"] == "kept"
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "candidate_impressions" in tables
    finally:
        conn.close()
