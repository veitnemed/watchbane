"""The reviewed add path owns a single watched row, not the watched snapshot."""
import sqlite3

import pytest

from candidates import title_state_service as states
from dataset.add_flow.save import save_add_title_record
from dataset.records import add
from storage.sqlite import action_repository
from storage.sqlite.connection import connect, get_db_path


def item(tmdb_id, title="Общее название"):
    return {
        "title": title, "year": 2020, "media_type": "movie", "country": "US",
        "tmdb_id": tmdb_id, "tmdb_score": 7.5, "tmdb_votes": 1000,
    }


def reviewed(candidate, score, *, include_meta_id=True):
    main = {k: candidate[k] for k in ("title", "year", "media_type", "country")}
    raw = {k: candidate[k] for k in ("tmdb_score", "tmdb_votes")}
    meta = {"tmdb_id": candidate["tmdb_id"]} if include_meta_id else None
    return save_add_title_record({"main_info": main, "raw_scores": raw}, score,
                                 meta_payload=meta, pool_candidate=candidate)


def active_rows():
    conn = connect()
    try:
        return {(row["media_type"], row["tmdb_id"]): (row["dataset_key"], row["user_score"])
                for row in conn.execute("SELECT * FROM watched_records WHERE payload_json != '{}'")}
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def no_external_side_effects(monkeypatch):
    monkeypatch.setattr(add, "run_after_add_side_effects", lambda **kwargs: [])


def test_reviewed_add_preserves_write_between_review_and_commit(monkeypatch):
    first = item(101, "Первый фильм")
    second = item(202, "Второй фильм")
    third = item(303, "Третий фильм")
    states.mark_watched(first, optional_user_score=3)
    original = states.save_watched_dataset_transition

    def interleave(data, meta, selected):
        states.mark_watched(third, optional_user_score=2)
        return original(data, meta, selected)

    monkeypatch.setattr(states, "save_watched_dataset_transition", interleave)
    assert reviewed(second, 1).ok
    assert active_rows() == {
        ("movie", 101): (first["title"], 3),
        ("movie", 202): (second["title"], 1),
        ("movie", 303): (third["title"], 2),
    }


def test_reviewed_homonym_saves_separately_but_alias_is_a_duplicate():
    first, second, third = (item(i) for i in (101, 202, 303))
    first_key = states.mark_watched(first, optional_user_score=3)["dataset_key"]
    states.add_to_watchlist(second)
    states.add_to_watchlist(third)
    result = reviewed(second, 1, include_meta_id=False)
    assert result.ok and result.title != first_key
    assert active_rows() == {("movie", 101): (first_key, 3), ("movie", 202): (result.title, 1)}
    assert states.get_title_state(third) == states.STATE_WATCHLIST
    alias = item(202, "Другое локализованное название")
    duplicate = reviewed(alias, 2)
    assert not duplicate.ok and duplicate.reason == "duplicate_tmdb_identity"
    assert duplicate.title == result.title
    assert active_rows()[("movie", 202)][1] == 1


def test_reviewed_legacy_candidate_is_ok_without_id_but_not_when_ambiguous():
    legacy = item(None)
    states.add_to_watchlist(legacy)
    assert reviewed(legacy, 2).ok
    assert not states.load_action_candidates(action_repository.ACTION_WATCHLIST)
    incoming = reviewed(item(101), 3)
    assert not incoming.ok and incoming.reason == "duplicate_title"
    assert active_rows() == {("movie", None): (legacy["title"], 2)}


def test_full_snapshot_is_rejected_without_changing_watched_or_actions():
    first, second = item(101, "Первый фильм"), item(202, "Второй фильм")
    states.mark_watched(first, optional_user_score=3)
    states.add_to_watchlist(second)
    before = active_rows()
    with pytest.raises(ValueError, match="exactly one"):
        states.save_watched_dataset_transition({"1": {}, "2": {}}, {}, second)
    assert active_rows() == before
    assert states.get_title_state(second) == states.STATE_WATCHLIST


def test_action_failure_after_watched_write_rolls_back_single_row():
    first, second = item(101, "Первый фильм"), item(202, "Второй фильм")
    states.mark_watched(first, optional_user_score=3)
    states.add_to_watchlist(second)
    path = get_db_path()
    conn = sqlite3.connect(path)
    try:
        conn.execute("""
            CREATE TRIGGER interrupt_reviewed_transfer BEFORE DELETE ON candidate_actions
            WHEN OLD.identity_key = 'tmdb:movie:202'
            BEGIN SELECT RAISE(ABORT, 'simulated interrupted transfer'); END
        """)
    finally:
        conn.close()
    result = reviewed(second, 1)
    assert not result.ok and result.reason == "save_error"
    assert active_rows() == {("movie", 101): (first["title"], 3)}
    assert states.get_title_state(second) == states.STATE_WATCHLIST
