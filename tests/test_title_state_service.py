from __future__ import annotations

import pytest

from candidates import title_state_service as states
from storage.sqlite.action_repository import (
    ACTION_HIDDEN,
    ACTION_WATCHLIST,
    add_candidate_action,
    load_candidate_state_actions,
)
from storage.sqlite.candidate_pool_repository import save_candidate_pool_dict
from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations


def _candidate(*, media_type: str = "tv", tmdb_id: int = 101) -> dict:
    return {
        "title": "Shared Title",
        "year": 2024,
        "media_type": media_type,
        "tmdb_id": tmdb_id,
        "tmdb_score": 7.5,
        "tmdb_votes": 500,
        "country": "US",
    }


def _actions(candidate: dict, db_path) -> set[str]:
    return load_candidate_state_actions(candidate, path=db_path)


def _watched_rows(db_path) -> list[dict]:
    conn = connect(db_path)
    try:
        apply_migrations(conn)
        return [dict(row) for row in conn.execute("SELECT * FROM watched_records ORDER BY dataset_key")]
    finally:
        conn.close()


def test_watchlist_removes_hidden_atomically(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    candidate = _candidate()
    states.hide_candidate(candidate, path=db_path)

    result = states.add_to_watchlist(candidate, path=db_path)

    assert result["state"] == states.STATE_WATCHLIST
    assert _actions(candidate, db_path) == {ACTION_WATCHLIST}


def test_hidden_removes_watchlist_atomically(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    candidate = _candidate()
    states.add_to_watchlist(candidate, path=db_path)

    result = states.hide_candidate(candidate, path=db_path)

    assert result["state"] == states.STATE_HIDDEN
    assert _actions(candidate, db_path) == {ACTION_HIDDEN}


def test_mark_watched_clears_actions_and_accepts_no_score(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    candidate = _candidate()
    add_candidate_action(ACTION_WATCHLIST, candidate, path=db_path)
    add_candidate_action(ACTION_HIDDEN, candidate, path=db_path)

    result = states.mark_watched(candidate, path=db_path)

    assert result["state"] == states.STATE_WATCHED
    assert _actions(candidate, db_path) == set()
    rows = _watched_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["media_type"] == "tv"
    assert rows[0]["user_score"] is None


def test_repeated_mark_watched_keeps_one_record_and_existing_score(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    candidate = _candidate()

    states.mark_watched(candidate, optional_user_score=8.5, path=db_path)
    states.mark_watched(candidate, path=db_path)

    rows = _watched_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["user_score"] == 8.5


def test_restore_returns_candidate_to_available_without_deleting_metadata(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    candidate = _candidate()
    save_candidate_pool_dict(
        {"shared title|2024": candidate},
        path=db_path,
        purge_watched=False,
    )
    states.hide_candidate(candidate, path=db_path)

    result = states.restore_candidate(candidate, path=db_path)

    assert result["state"] == states.STATE_AVAILABLE
    assert states.get_title_state(candidate, path=db_path) == states.STATE_AVAILABLE
    assert candidate["title"] == "Shared Title"
    conn = connect(db_path)
    try:
        candidate_count = conn.execute("SELECT COUNT(*) AS count FROM candidate_records").fetchone()["count"]
    finally:
        conn.close()
    assert candidate_count == 1


def test_repeated_transition_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    candidate = _candidate()

    first = states.add_to_watchlist(candidate, path=db_path)
    second = states.add_to_watchlist(candidate, path=db_path)

    conn = connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) AS count FROM candidate_actions").fetchone()["count"]
    finally:
        conn.close()
    assert first["identity"] == second["identity"]
    assert count == 1


def test_movie_and_tv_states_do_not_conflict(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    tv = _candidate(media_type="tv", tmdb_id=101)
    movie = _candidate(media_type="movie", tmdb_id=202)

    states.add_to_watchlist(tv, path=db_path)
    states.hide_candidate(movie, path=db_path)

    assert states.get_title_state(tv, path=db_path) == states.STATE_WATCHLIST
    assert states.get_title_state(movie, path=db_path) == states.STATE_HIDDEN
    assert _actions(tv, db_path) == {ACTION_WATCHLIST}
    assert _actions(movie, db_path) == {ACTION_HIDDEN}


def test_mark_watched_rollback_preserves_previous_state(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "state.sqlite3"
    candidate = _candidate()
    states.add_to_watchlist(candidate, path=db_path)

    def fail_upsert(*_args, **_kwargs):
        raise RuntimeError("forced watched write failure")

    monkeypatch.setattr(states, "upsert_watched_row", fail_upsert)

    with pytest.raises(RuntimeError, match="forced watched write failure"):
        states.mark_watched(candidate, optional_user_score=8.0, path=db_path)

    assert states.get_title_state(candidate, path=db_path) == states.STATE_WATCHLIST
    assert _actions(candidate, db_path) == {ACTION_WATCHLIST}
    assert _watched_rows(db_path) == []


def test_remove_from_watchlist_returns_available(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    candidate = _candidate()
    states.add_to_watchlist(candidate, path=db_path)

    result = states.remove_from_watchlist(candidate, path=db_path)

    assert result["state"] == states.STATE_AVAILABLE
    assert _actions(candidate, db_path) == set()


def test_remove_from_watched_returns_available(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    candidate = _candidate()
    states.mark_watched(candidate, optional_user_score=8.0, path=db_path)

    result = states.remove_from_watched(candidate, path=db_path)

    assert result["state"] == states.STATE_AVAILABLE
    assert states.get_title_state(candidate, path=db_path) == states.STATE_AVAILABLE
    assert _watched_rows(db_path)[0]["payload_json"] == "{}"
