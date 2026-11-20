"""Canonical current actions are scoped by media and TMDb ID."""
import sqlite3

import pytest

from candidates import title_state_service as state
from candidates.search.filtering import filter_candidates
from storage.sqlite import action_repository as repo
from storage.sqlite.connection import connect


def item(tmdb_id, *, title="Общее имя", media="movie", **extra):
    return dict(title=title, year=2020, media_type=media, tmdb_id=tmdb_id, **extra)


def test_saved_alias_collapses_and_keeps_history_and_metadata(tmp_path):
    path = tmp_path / "watchbane.sqlite3"
    first = item(1, overview="Original synopsis")
    alias = item(1, title="Translated title")
    initial = state.add_to_watchlist(first, path=path)
    assert initial["identity"] == "tmdb:movie:1"
    assert state.get_title_state(alias, path=path) == state.STATE_WATCHLIST
    raw_initial = repo.load_candidate_actions_dict(repo.ACTION_WATCHLIST, path=path)
    state.add_to_watchlist(alias, path=path)
    raw_final = repo.load_candidate_actions_dict(repo.ACTION_WATCHLIST, path=path)
    key = initial["identity"]
    assert set(raw_final) == {key}
    assert raw_final[key]["added_at"] == raw_initial[key]["added_at"]
    assert raw_final[key]["candidate"]["overview"] == "Original synopsis"
    assert len(state.load_action_candidates(repo.ACTION_WATCHLIST, path=path)) == 1


def test_known_homonyms_have_independent_actions_in_both_media_types(tmp_path):
    path = tmp_path / "watchbane.sqlite3"
    first, homonym, series = item(1), item(2), item(1, media="tv")
    state.add_to_watchlist(first, path=path)
    state.hide_candidate(homonym, path=path)
    state.add_to_watchlist(series, path=path)
    assert state.get_title_state(first, path=path) == state.STATE_WATCHLIST
    assert state.get_title_state(homonym, path=path) == state.STATE_HIDDEN
    assert state.get_title_state(series, path=path) == state.STATE_WATCHLIST
    state.mark_watched(homonym, path=path)
    assert {candidate["media_type"] for candidate in state.load_action_candidates(repo.ACTION_WATCHLIST, path=path)} == {"movie", "tv"}


def test_effective_reads_collapse_preexisting_aliases_without_rewriting_legacy(tmp_path):
    path = tmp_path / "watchbane.sqlite3"
    saved = {
        "first|2020|movie": {"candidate": item(1, title="First"), "added_at": "2026-01-01T00:00:00+00:00"},
        "second|2020|movie": {"candidate": item(1, title="Second"), "added_at": "2026-01-02T00:00:00+00:00"},
    }
    repo.save_candidate_actions_dict(repo.ACTION_WATCHLIST, saved, path=path)
    assert len(state.load_action_candidates(repo.ACTION_WATCHLIST, path=path)) == 1
    assert repo.load_candidate_actions_dict(repo.ACTION_WATCHLIST, path=path) == saved
    hidden = {"third|2020|movie": {"candidate": item(1, title="Third"), "hidden_at": "2026-01-03T00:00:00+00:00"}}
    repo.save_candidate_actions_dict(repo.ACTION_HIDDEN, hidden, path=path)
    assert not state.load_action_candidates(repo.ACTION_WATCHLIST, path=path)
    assert state.get_title_state(item(1), path=path) == state.STATE_HIDDEN
    assert repo.load_action_identities(repo.ACTION_HIDDEN, path=path) == {"tmdb:movie:1"}
    other = item(2, title="Third")
    visible = filter_candidates([item(1), other], {"hidden_identities": {"tmdb:movie:1"}, "only_unwatched": False})
    assert [row["tmdb_id"] for row in visible] == [2]


def test_legacy_title_alone_is_not_proof_but_matching_imdb_can_link(tmp_path):
    path = tmp_path / "watchbane.sqlite3"
    legacy = item(None, imdb_id="tt1234567")
    first = item(1, imdb_id="tt1234567", title="Translated")
    homonym = item(2, imdb_id="tt1234568")
    state.add_to_watchlist(legacy, path=path)
    assert state.get_title_state(homonym, path=path) == state.STATE_AVAILABLE
    assert state.get_title_state(first, path=path) == state.STATE_WATCHLIST
    state.add_to_watchlist(first, path=path)
    assert set(repo.load_candidate_actions_dict(repo.ACTION_WATCHLIST, path=path)) == {"tmdb:movie:1"}
    assert state.get_title_state(first, path=path) == state.STATE_WATCHLIST


def test_interrupted_replace_rolls_back_deletion_of_legacy_action(tmp_path):
    path = tmp_path / "watchbane.sqlite3"
    legacy = {"alias|2020|movie": {"candidate": item(1, title="Alias"), "added_at": "2026-01-01T00:00:00+00:00"}}
    repo.save_candidate_actions_dict(repo.ACTION_WATCHLIST, legacy, path=path)
    conn = connect(path)
    try:
        conn.execute("""
            CREATE TRIGGER interrupt_action BEFORE INSERT ON candidate_actions
            WHEN NEW.action = 'hidden'
            BEGIN SELECT RAISE(ABORT, 'simulated interrupted write'); END
        """)
    finally:
        conn.close()
    with pytest.raises(sqlite3.IntegrityError, match="simulated interrupted write"):
        state.hide_candidate(item(1), path=path)
    assert repo.load_candidate_actions_dict(repo.ACTION_WATCHLIST, path=path) == legacy
    assert not state.load_action_candidates(repo.ACTION_HIDDEN, path=path)


def test_explicit_resave_combines_legacy_alias_metadata_and_keeps_earliest_date(tmp_path):
    path = tmp_path / "watchbane.sqlite3"
    saved = {
        "first|2020|movie": {
            "candidate": item(1, title="First", overview="First synopsis"),
            "added_at": "2026-01-01T00:00:00+00:00",
        },
        "second|2020|movie": {
            "candidate": item(1, title="Second", original_title="Original release"),
            "added_at": "2026-01-02T00:00:00+00:00",
        },
    }
    repo.save_candidate_actions_dict(repo.ACTION_WATCHLIST, saved, path=path)
    state.add_to_watchlist(item(1, title="New alias"), path=path)
    result = repo.load_candidate_actions_dict(repo.ACTION_WATCHLIST, path=path)
    assert set(result) == {"tmdb:movie:1"}
    (entry,) = result.values()
    assert entry["added_at"] == "2026-01-01T00:00:00+00:00"
    assert entry["candidate"]["overview"] == "First synopsis"
    assert entry["candidate"]["original_title"] == "Original release"


def test_legacy_filter_can_hide_bare_title_without_sharing_a_persisted_action(tmp_path):
    path = tmp_path / "watchbane.sqlite3"
    first, homonym = item(1), item(2)
    bare = "общее имя|2020"
    criteria = {"hidden_identities": {bare}, "only_unwatched": False}
    # Older callers supply a title/year exclusion without a resolved TMDb ID.
    assert filter_candidates([first, homonym], criteria) == []

    repo.save_candidate_actions_dict(
        repo.ACTION_HIDDEN,
        {bare: {"candidate": first, "hidden_at": "2026-01-01T00:00:00+00:00"}},
        path=path,
    )
    criteria["hidden_identities"] = repo.load_action_identities(repo.ACTION_HIDDEN, path=path)
    assert criteria["hidden_identities"] == {"tmdb:movie:1"}
    assert [row["tmdb_id"] for row in filter_candidates([first, homonym], criteria)] == [2]
    state.restore_candidate(homonym, path=path)
    state.restore_candidate(item(None), path=path)
    assert state.get_title_state(first, path=path) == state.STATE_HIDDEN


def test_imported_unlinked_conflict_uses_same_state_in_cards_and_collection(tmp_path):
    path = tmp_path / "watchbane.sqlite3"
    old_movie, old_series = item(None), item(None, media="tv")
    bare = "общее имя|2020"
    scoped = bare + "|movie"
    series_key = bare + "|tv"
    saved = {
        bare: {"candidate": old_movie, "added_at": "2026-01-02T00:00:00+00:00"},
        scoped: {"candidate": old_movie, "added_at": "2026-01-03T00:00:00+00:00"},
        series_key: {"candidate": old_series, "added_at": "2026-01-03T00:00:00+00:00"},
    }
    hidden = {scoped: {"candidate": old_movie, "hidden_at": "2026-01-01T00:00:00+00:00"}}
    repo.save_candidate_actions_dict(repo.ACTION_WATCHLIST, saved, path=path)
    repo.save_candidate_actions_dict(repo.ACTION_HIDDEN, hidden, path=path)

    assert state.get_title_state(old_movie, path=path) == state.STATE_HIDDEN
    assert state.get_title_state(old_series, path=path) == state.STATE_WATCHLIST
    assert repo.load_action_identities(repo.ACTION_WATCHLIST, path=path) == {series_key}
    assert repo.load_action_identities(repo.ACTION_HIDDEN, path=path) == {scoped}
    assert repo.load_candidate_actions_dict(repo.ACTION_WATCHLIST, path=path) == saved
    assert repo.load_candidate_actions_dict(repo.ACTION_HIDDEN, path=path) == hidden

    state.add_to_watchlist(old_movie, path=path)
    assert state.get_title_state(old_movie, path=path) == state.STATE_WATCHLIST
    assert repo.load_action_identities(repo.ACTION_WATCHLIST, path=path) == {series_key, scoped}
    assert repo.load_action_identities(repo.ACTION_HIDDEN, path=path) == set()


def test_imported_unlinked_duplicate_collapses_without_losing_bare_filter(tmp_path):
    path = tmp_path / "watchbane.sqlite3"
    old_movie = item(None)
    bare = "общее имя|2020"
    scoped = bare + "|movie"
    saved = {
        bare: {"candidate": old_movie, "added_at": "2026-01-01T00:00:00+00:00"},
        scoped: {"candidate": dict(old_movie, overview="Newest"), "added_at": "2026-01-02T00:00:00+00:00"},
    }
    repo.save_candidate_actions_dict(repo.ACTION_WATCHLIST, saved, path=path)

    assert repo.load_action_identities(repo.ACTION_WATCHLIST, path=path) == {bare}
    assert [row["overview"] for row in state.load_action_candidates(repo.ACTION_WATCHLIST, path=path)] == ["Newest"]
    assert repo.load_candidate_actions_dict(repo.ACTION_WATCHLIST, path=path) == saved
