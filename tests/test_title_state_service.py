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
from storage.sqlite import impression_repository


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

    states.mark_watched(candidate, optional_user_score=3, path=db_path)
    states.mark_watched(candidate, path=db_path)

    rows = _watched_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["user_score"] == 3


def test_restore_returns_candidate_to_available_without_deleting_metadata(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    candidate = _candidate()
    save_candidate_pool_dict(
        {"shared title|2024": candidate},
        path=db_path,
        purge_watched=False,
    )
    impression_repository.record_impressions([candidate], deck_id="deck-before-hide", path=db_path)
    states.hide_candidate(candidate, path=db_path)

    result = states.restore_candidate(candidate, path=db_path)

    assert result["state"] == states.STATE_AVAILABLE
    assert states.get_title_state(candidate, path=db_path) == states.STATE_AVAILABLE
    assert impression_repository.get_impression(
        "shared title|2024",
        "tv",
        path=db_path,
    ) is None
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
        states.mark_watched(candidate, optional_user_score=3, path=db_path)

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
    states.mark_watched(candidate, optional_user_score=3, path=db_path)

    result = states.remove_from_watched(candidate, path=db_path)

    assert result["state"] == states.STATE_AVAILABLE
    assert states.get_title_state(candidate, path=db_path) == states.STATE_AVAILABLE
    assert _watched_rows(db_path)[0]["payload_json"] == "{}"


def test_stale_repeated_unrated_mark_preserves_exact_watched_payload(tmp_path):
    from storage.sqlite.watched_repository import save_dataset_dict, save_meta_dict

    db = tmp_path / "state.sqlite3"
    stale_card = _candidate(media_type="movie")
    assert states.get_title_state(stale_card, path=db) == states.STATE_AVAILABLE
    # Another caller finishes writing the film after search captured the card.
    save_dataset_dict({"Original label": {
        "main_info": {"title": "Edited title", "year": 2024, "media_type": "movie",
                      "user_score": 3, "overview": "Rich description"},
        "raw_scores": {"tmdb_id": 101},
        "local_notes": "Retain my notes",
    }}, path=db)
    save_meta_dict({"Original label": {"private_tag": "retain metadata"}}, path=db)
    add_candidate_action(ACTION_WATCHLIST, stale_card, path=db)
    other = _candidate(media_type="tv")
    states.hide_candidate(other, path=db)
    before = _watched_rows(db)

    result = states.mark_watched(stale_card, path=db)

    assert result["state"] == states.STATE_WATCHED and result["dataset_key"] == "Original label"
    assert _watched_rows(db) == before
    assert _actions(stale_card, db) == set()
    assert _actions(other, db) == {ACTION_HIDDEN}


def test_first_unrated_mark_with_metadata_only_row_still_creates_watched_record(tmp_path):
    from storage.sqlite.watched_repository import save_meta_dict

    db = tmp_path / "state.sqlite3"
    candidate = _candidate(media_type="movie")
    save_meta_dict({"Old key": {"main_info": {"media_type": "movie"}, "raw_scores": {"tmdb_id": 101}}}, path=db)
    assert states.get_title_state(candidate, path=db) == states.STATE_AVAILABLE
    assert states.mark_watched(candidate, path=db)["dataset_key"] == "Old key"
    assert states.get_title_state(candidate, path=db) == states.STATE_WATCHED
    assert len(_watched_rows(db)) == 1


def test_stale_explicit_rating_updates_only_the_score_of_existing_typed_record(tmp_path):
    import json
    from storage.sqlite.watched_repository import save_dataset_dict, save_meta_dict

    db = tmp_path / "state.sqlite3"
    candidate = _candidate(media_type="movie")
    save_dataset_dict({"Original label": {
        "main_info": {"title": "Edited title", "year": 2024, "media_type": "movie",
                      "user_score": 3, "overview": "Rich description"},
        "raw_scores": {"tmdb_id": 101},
        "local_notes": "Retain my notes",
    }}, path=db)
    save_meta_dict({"Original label": {"private_tag": "retain metadata"}}, path=db)
    before, = _watched_rows(db)
    result = states.mark_watched(candidate, optional_user_score=1, path=db)
    assert result["dataset_key"] == "Original label"
    after, = _watched_rows(db)
    assert after["user_score"] == 1
    expected_payload = json.loads(before["payload_json"])
    expected_payload["main_info"]["user_score"] = 1
    assert json.loads(after["payload_json"]) == expected_payload
    ignored = {"payload_json", "updated_at", "user_score"}
    assert {k: v for k, v in after.items() if k not in ignored} == {
        k: v for k, v in before.items() if k not in ignored
    }


def test_repeated_rating_rolls_back_if_same_title_action_cleanup_fails(tmp_path, monkeypatch):
    db = tmp_path / "state.sqlite3"
    candidate = _candidate(media_type="movie")
    states.mark_watched(candidate, optional_user_score=3, path=db)
    add_candidate_action(ACTION_WATCHLIST, candidate, path=db)
    before = _watched_rows(db)
    clear_actions = states._clear_candidate_actions

    def fail_after_cleanup(conn, title):
        clear_actions(conn, title)
        raise RuntimeError("injected after cleanup")

    monkeypatch.setattr(states, "_clear_candidate_actions", fail_after_cleanup)
    with pytest.raises(RuntimeError, match="injected"):
        states.mark_watched(candidate, optional_user_score=1, path=db)

    assert _watched_rows(db) == before
    assert _actions(candidate, db) == {ACTION_WATCHLIST}
