"""Distinct known TMDb identities must never overwrite a watched payload."""
from candidates import title_state_service as states
from storage.sqlite.connection import connect


def _item(tmdb_id, *, media="movie", title="Одинаковое название"):
    return {"title": title, "year": 2020, "media_type": media, "tmdb_id": tmdb_id}


def _active(db_path):
    conn = connect(db_path)
    try:
        return {(row["media_type"], row["tmdb_id"]): (row["dataset_key"], row["user_score"])
                for row in conn.execute("SELECT * FROM watched_records WHERE payload_json != '{}'")}
    finally:
        conn.close()


def test_distinct_known_same_title_and_year_do_not_share_status_or_data(tmp_path):
    db = tmp_path / "watchbane.sqlite3"
    first, second = _item(101), _item(202)
    first_key = states.mark_watched(first, optional_user_score=3, path=db)["dataset_key"]
    assert states.get_title_state(second, path=db) == states.STATE_AVAILABLE
    # Removing a not-watched homonym must not clear the watched original.
    assert states.remove_from_watched(second, path=db)["state"] == states.STATE_AVAILABLE
    assert _active(db) == {("movie", 101): (first_key, 3)}

    second_key = states.mark_watched(second, optional_user_score=1, path=db)["dataset_key"]
    assert second_key != first_key
    assert _active(db) == {("movie", 101): (first_key, 3), ("movie", 202): (second_key, 1)}
    assert states.remove_from_watched(first, path=db)["state"] == states.STATE_AVAILABLE
    assert _active(db) == {("movie", 202): (second_key, 1)}
    assert states.get_title_state(first, path=db) == states.STATE_AVAILABLE


def test_same_numeric_id_different_media_is_separate_but_alias_reuses_watched_key(tmp_path):
    db = tmp_path / "watchbane.sqlite3"
    movie, series = _item(101), _item(101, media="tv")
    movie_key = states.mark_watched(movie, optional_user_score=3, path=db)["dataset_key"]
    series_key = states.mark_watched(series, optional_user_score=1, path=db)["dataset_key"]
    assert movie_key != series_key
    alias = _item(101, title="Localized title")
    assert states.get_title_state(alias, path=db) == states.STATE_WATCHED
    assert states.mark_watched(alias, path=db)["dataset_key"] == movie_key
    assert _active(db) == {("movie", 101): (movie_key, 3), ("tv", 101): (series_key, 1)}


def test_exact_legacy_match_without_tmdb_id_can_gain_id_in_same_row(tmp_path):
    db = tmp_path / "watchbane.sqlite3"
    unlinked, linked = _item(None), _item(101)
    old_key = states.mark_watched(unlinked, optional_user_score=2, path=db)["dataset_key"]
    assert _active(db) == {("movie", None): (old_key, 2)}
    assert states.get_title_state(linked, path=db) == states.STATE_WATCHED
    assert states.mark_watched(linked, path=db)["dataset_key"] == old_key
    assert _active(db) == {("movie", 101): (old_key, 2)}


def test_homonym_does_not_overwrite_metadata_only_row(tmp_path):
    db = tmp_path / "watchbane.sqlite3"
    first, second = _item(101), _item(202)
    first_key = states.mark_watched(first, optional_user_score=3, path=db)["dataset_key"]
    states.remove_from_watched(first, path=db)
    second_key = states.mark_watched(second, optional_user_score=1, path=db)["dataset_key"]
    assert second_key != first_key
    conn = connect(db)
    try:
        removed = conn.execute("SELECT * FROM watched_records WHERE dataset_key = ?", (first_key,)).fetchone()
        assert removed["tmdb_id"] == 101
        assert removed["payload_json"] == "{}"
        assert removed["meta_json"] is not None
    finally:
        conn.close()
    # The original ID can take its own key back through a different alias.
    assert states.mark_watched(_item(101, title="Alias"), path=db)["dataset_key"] == first_key
    assert _active(db) == {("movie", 101): (first_key, None), ("movie", 202): (second_key, 1)}


def test_missing_id_cannot_change_or_remove_a_linked_homonym(tmp_path):
    db = tmp_path / "watchbane.sqlite3"
    linked, unlinked = _item(101), _item(None)
    linked_key = states.mark_watched(linked, optional_user_score=3, path=db)["dataset_key"]
    assert states.get_title_state(unlinked, path=db) == states.STATE_AVAILABLE
    states.remove_from_watched(unlinked, path=db)
    assert _active(db) == {("movie", 101): (linked_key, 3)}
    legacy_key = states.mark_watched(unlinked, optional_user_score=2, path=db)["dataset_key"]
    assert legacy_key != linked_key
    states.remove_from_watched(_item(202), path=db)
    assert _active(db) == {("movie", 101): (linked_key, 3), ("movie", None): (legacy_key, 2)}


def test_concurrent_homonyms_allocate_unique_keys(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    db = tmp_path / "watchbane.sqlite3"
    first, second = _item(101), _item(202)
    assert states.get_title_state(first, path=db) == states.STATE_AVAILABLE
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(states.mark_watched, first, 3, path=db)
        two = pool.submit(states.mark_watched, second, 1, path=db)
    keys = [one.result()["dataset_key"], two.result()["dataset_key"]]
    assert keys[0] != keys[1]
    assert _active(db) == {("movie", 101): (keys[0], 3), ("movie", 202): (keys[1], 1)}
