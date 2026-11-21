from candidates import title_state_service as state
from storage.sqlite import action_repository as repo


def test_stale_untyped_saved_remove_keeps_imported_homonym_with_another_imdb_id(tmp_path):
    path = tmp_path / "watchbane.sqlite3"
    stale = {"title": "Общее имя", "year": 2020, "media_type": "movie", "imdb_id": "tt1234567"}
    other = dict(stale, imdb_id="tt1234568", overview="Independent saved title")
    bare = "общее имя|2020"
    scoped = bare + "|movie"
    legacy_alias = {"candidate": stale, "added_at": "2026-01-01T00:00:00Z"}
    unrelated = {"candidate": other, "added_at": "2026-01-02T00:00:00Z"}
    repo.save_candidate_actions_dict(repo.ACTION_WATCHLIST, {bare: legacy_alias, scoped: unrelated}, path=path)

    result = state.remove_from_watchlist(stale, path=path)
    assert result["state"] == state.STATE_AVAILABLE

    # Reopen through the repository; the other row and metadata must survive.
    assert repo.load_candidate_actions_dict(repo.ACTION_WATCHLIST, path=path) == {scoped: unrelated}
    assert state.get_title_state(other, path=path) == state.STATE_WATCHLIST
