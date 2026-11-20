import sqlite3

import pytest

from app.use_cases.watched_library import update_user_score
from dataset.records.update import update_dataset_record
from storage.sqlite.connection import connect
from storage.sqlite.json_codec import loads_json
from storage.sqlite.migrations import apply_migrations
from storage.sqlite.watched_write import upsert_watched_row


def _seed(key: str, title: str, tmdb_id: int, score: int = 1) -> dict:
    payload = {
        "main_info": {
            "title": title, "year": 2020, "user_score": score, "country": "US",
            "media_type": "movie", "editor_flag": "keep",
        },
        "tmdb_id": tmdb_id,
        "imdb_id": f"tt{tmdb_id}",
        "overview": "Keep synopsis",
        "raw_scores": {"tmdb_score": 7.6},
        "computed_scores": {"tmdb_score": 7.6},
        "localized": {"ru": {"title": title}},
        "genres_tmdb": [18],
    }
    conn = connect()
    try:
        apply_migrations(conn)
        with conn:
            upsert_watched_row(
                conn, dataset_key=key, payload=payload,
                meta={"tmdb_id": tmdb_id, "main_info": {"title": title}, "origin": "keep"},
                created_at="then", updated_at="then",
            )
    finally:
        conn.close()
    return payload


def _row(key: str) -> dict:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM watched_records WHERE dataset_key = ?", (key,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def test_score_updates_only_selected_row_without_replacing_full_payload(monkeypatch) -> None:
    from storage.sqlite import watched_write

    selected = "Alpha (2020, movie, 11)"
    expected_payload = _seed(selected, "Alpha", 11)
    _seed("Alpha", "Alpha", 12)
    before = _row(selected)
    other = _row("Alpha")

    # Reproduce the old race once, with an unrelated committed write in the
    # interval between entering the edit flow and its actual DB operation.
    create_connection = watched_write.connection

    def add_unrelated_before_edit(conn, path):
        _seed("Late arrival", "Beta", 13)
        return create_connection(conn, path)

    monkeypatch.setattr(watched_write, "connection", add_unrelated_before_edit)
    result = update_user_score(selected, 2)

    assert result.ok and result.changed_fields == ["main_info.user_score"]
    assert _row("Alpha") == other
    assert _row("Late arrival")["tmdb_id"] == 13
    after = _row(selected)
    assert after["user_score"] == 2
    expected_payload["main_info"]["user_score"] = 2
    assert loads_json(after["payload_json"]) == expected_payload
    assert {key: value for key, value in before.items() if key not in {"user_score", "payload_json", "updated_at"}} == {
        key: value for key, value in after.items() if key not in {"user_score", "payload_json", "updated_at"}
    }


def test_score_returns_distinct_missing_invalid_unchanged_and_write_error_results() -> None:
    _seed("Alpha", "Alpha", 11, score=1)
    before = _row("Alpha")
    assert update_user_score("alpha", 2).reason == "not_found"
    assert update_dataset_record("Alpha", {"main_info": {"user_score": True}}, source_name="desktop_gui").reason == "invalid_patch"
    with pytest.raises(ValueError, match="1 to 3"):
        update_user_score("Alpha", 4)
    assert update_user_score("Alpha", 1).reason == "nothing_changed"
    assert _row("Alpha") == before

    conn = connect()
    try:
        with conn:
            conn.execute(
                "CREATE TRIGGER simulated_score_error BEFORE UPDATE ON watched_records "
                "BEGIN SELECT RAISE(ABORT, 'simulated write error'); END"
            )
    finally:
        conn.close()
    result = update_user_score("Alpha", 2)
    assert not result.ok and result.reason == "save_error"
    assert _row("Alpha") == before


def test_raw_score_patch_keeps_typed_payload_and_atomically_merges_meta(monkeypatch) -> None:
    from storage.sqlite import watched_write

    selected = "Common (2020, movie, 11)"
    expected_payload = _seed(selected, "Common", 11)
    _seed("Common", "Common", 12)
    old_peer = _row("Common")
    create_connection = watched_write.connection

    def before_write(conn, path):
        _seed("Concurrent", "Concurrent", 13)
        return create_connection(conn, path)

    monkeypatch.setattr(watched_write, "connection", before_write)
    result = update_dataset_record(selected.lower(), {"raw_scores": {"tmdb_score": 8.1}})
    assert result.ok and result.title == selected
    assert result.changed_fields == ["raw_scores.tmdb_score"]
    actual = _row(selected)
    expected_payload["raw_scores"]["tmdb_score"] = 8.1
    expected_payload["computed_scores"]["tmdb_score"] = 8.1
    assert loads_json(actual["payload_json"]) == expected_payload
    assert actual["title"] == "Common" and actual["tmdb_id"] == 11
    assert _row("Common") == old_peer
    assert _row("Concurrent")["tmdb_id"] == 13
    meta = loads_json(actual["meta_json"])
    assert meta["tmdb_id"] == 11 and meta["origin"] == "keep"
    assert meta["main_info"]["title"] == "Common" and meta["raw_scores"]["tmdb_score"] == 8.1

    monkeypatch.setattr(watched_write, "connection", create_connection)
    conn = connect()
    try:
        with conn:
            conn.execute(
                "CREATE TRIGGER simulated_meta_error BEFORE UPDATE OF meta_json ON watched_records "
                "BEGIN SELECT RAISE(ABORT, 'simulated meta error'); END"
            )
    finally:
        conn.close()
    assert update_dataset_record(selected, {"raw_scores": {"tmdb_score": 6.4}}).reason == "save_error"
    assert _row(selected) == actual
