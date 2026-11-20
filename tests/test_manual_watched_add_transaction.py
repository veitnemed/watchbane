"""Manual/ordinary TMDb add must not replace a watched-library snapshot."""
import sqlite3

import pytest

from candidates import title_state_service as states
from dataset.add_flow.save import save_add_title_record
from dataset.records import add
from storage.sqlite.connection import get_db_path


def item(tmdb_id, title, *, year=2020):
    return {
        "title": title, "year": year, "media_type": "movie", "country": "US",
        "tmdb_id": tmdb_id, "tmdb_score": 7.6, "tmdb_votes": 1200,
    }


def manual(candidate, score):
    main = {key: candidate[key] for key in ("title", "year", "media_type", "country")}
    raw = {key: candidate[key] for key in ("tmdb_score", "tmdb_votes")}
    meta = {"tmdb_id": candidate["tmdb_id"]} if candidate["tmdb_id"] else None
    return save_add_title_record({"main_info": main, "raw_scores": raw}, score, meta_payload=meta)


def active_rows():
    conn = sqlite3.connect(get_db_path())
    try:
        return {(row[0], row[1]): (row[2], row[3]) for row in conn.execute(
            "SELECT media_type, tmdb_id, dataset_key, user_score FROM watched_records WHERE payload_json != '{}'"
        )}
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def no_external_side_effects(monkeypatch):
    monkeypatch.setattr(add, "run_after_add_side_effects", lambda **kwargs: [])


def test_ordinary_tmdb_add_does_not_remove_interleaved_create(monkeypatch):
    first, second, third = item(101, "Первый"), item(202, "Второй"), item(303, "Третий")
    assert manual(first, 3).ok
    original = states.save_watched_dataset_transition

    def interleave(data, meta, candidate):
        assert candidate is None
        states.mark_watched(third, optional_user_score=2)
        return original(data, meta, candidate)

    monkeypatch.setattr(states, "save_watched_dataset_transition", interleave)
    assert manual(second, 1).ok
    assert active_rows() == {
        ("movie", 101): (first["title"], 3),
        ("movie", 202): (second["title"], 1),
        ("movie", 303): (third["title"], 2),
    }


def test_manual_homonym_add_uses_meta_id_without_touching_other_candidate():
    first, second, third = [item(n, "Общее имя") for n in (101, 202, 303)]
    first_key = manual(first, 3).title
    states.add_to_watchlist(third)
    result = manual(second, 1)
    assert result.ok and result.title != first_key
    assert active_rows() == {("movie", 101): (first_key, 3), ("movie", 202): (result.title, 1)}
    assert states.get_title_state(third) == states.STATE_WATCHLIST
    duplicate = manual(item(202, "Алиас"), 2)
    assert not duplicate.ok and duplicate.reason == "duplicate_tmdb_identity"


def test_manual_entry_without_known_id_retains_legacy_duplicate_guard():
    item_with_no_id = item(None, "Ручная запись")
    assert manual(item_with_no_id, 2).ok
    duplicate = manual(item_with_no_id, 3)
    assert not duplicate.ok and duplicate.reason == "duplicate_title"
    assert active_rows() == {("movie", None): ("Ручная запись", 2)}


def test_manual_add_reuses_only_verified_metadata_keys(monkeypatch):
    from storage.sqlite.watched_meta import load_meta_dict, save_meta_dict

    title = "Метаданные отдельно"
    known = item(101, title)
    unlinked = item(None, title)
    main = {key: known[key] for key in ("title", "year", "media_type", "country")}
    save_meta_dict({
        "Known legacy key": {
            "main_info": main, "tmdb_id": 101, "description": "Stored known synopsis",
            "raw_scores": {"tmdb_score": 8.9, "tmdb_votes": 555, "tmdb_popularity": 99},
            "custom_field": {"keep": True},
        },
        "Unlinked legacy key": {
            "main_info": main, "description": "Stored unlinked synopsis",
            "raw_scores": {"tmdb_popularity": 50},
        },
    })

    # The typed ID proves a match even if the dataset key is an old alias.
    observed_side_effects = []
    monkeypatch.setattr(add, "run_after_add_side_effects",
                        lambda **kwargs: observed_side_effects.append(kwargs) or [])
    result = manual(known, 3)
    assert result.ok and result.title == "Known legacy key"
    # The now-present known homonym cannot be adopted by generic manual input.
    ambiguous = manual(unlinked, 2)
    assert not ambiguous.ok and ambiguous.reason == "duplicate_title"
    assert load_meta_dict()["Unlinked legacy key"]["description"] == "Stored unlinked synopsis"
    assert load_meta_dict()["Known legacy key"]["description"] == "Stored known synopsis"
    old = load_meta_dict()["Known legacy key"]
    assert old["custom_field"] == {"keep": True}
    assert old["raw_scores"] == {"tmdb_score": 7.6, "tmdb_votes": 1200, "tmdb_popularity": 99}
    from storage.sqlite.watched_read import load_dataset_dict
    stored = load_dataset_dict()["Known legacy key"]
    assert stored["raw_scores"] == old["raw_scores"]
    assert stored["computed_scores"]["tmdb_score"] == 7.6
    assert observed_side_effects[0]["meta_obj"] == old
    assert observed_side_effects[0]["movie"]["raw_scores"] == stored["raw_scores"]


def test_idless_manual_add_reuses_single_exact_idless_metadata_key():
    from storage.sqlite.watched_meta import load_meta_dict, save_meta_dict

    legacy = item(None, "Выбранное название")
    save_meta_dict({"External title": {
        "main_info": {key: legacy[key] for key in ("title", "year", "media_type", "country")},
        "description": "Stored unlinked synopsis",
    }})
    result = manual(legacy, 2)
    assert result.ok and result.title == "External title"
    assert load_meta_dict()["External title"]["description"] == "Stored unlinked synopsis"
    assert active_rows() == {("movie", None): ("External title", 2)}


def test_nested_legacy_tmdb_id_is_used_instead_of_storing_duplicate():
    first = item(71, "Canonical title")
    assert manual(first, 3).ok
    different_title = {"title": "Алиас", "year": 2020, "media_type": "movie", "country": "US"}
    result = save_add_title_record(
        {"main_info": different_title, "raw_scores": {"tmdb_score": 7.5}}, 2,
        meta_payload={"raw_scores": {"tmdb_id": "71", "tmdb_score": 7.5}},
    )
    assert not result.ok and result.reason == "duplicate_tmdb_identity"
    assert active_rows() == {("movie", 71): (first["title"], 3)}
