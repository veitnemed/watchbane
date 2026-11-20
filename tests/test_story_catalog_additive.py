from contextlib import closing

import pytest

from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.service import add_candidate_to_watchlist, mark_story_watched
from candidates.sources.tmdb.importer import import_story_catalog_candidates
from candidates.story_catalog import fill_story_catalog
from candidates.title_state_service import get_title_state
from storage import data
from storage.sqlite.candidate_criteria_repository import load_candidate_criteria_dict, save_candidate_criteria_dict
from storage.sqlite.candidate_pool_repository import load_candidate_pool_dict
from storage.sqlite.candidate_write import insert_candidate_record
from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations
from storage.sqlite.session import utc_now


def _candidate(identifier, title="Тёзки", **fields):
    return {
        "title": title, "year": 2022, "media_type": "movie", "tmdb_id": identifier,
        "overview": "Преступник ищет спрятанное сокровище.",
        "tmdb_score": 8, "tmdb_votes": 1000, **fields,
    }


def _insert(pool_key, payload):
    with closing(connect()) as conn:
        apply_migrations(conn)
        with conn:
            insert_candidate_record(conn, pool_key=pool_key, candidate=payload, timestamp=utc_now())


class OfflineProvider:
    def __init__(self, during_details=None):
        self.during_details = during_details

    def discover(self, media, _params):
        return {"results": [{"id": 101}, {"id": 202}] if media == "movie" else [], "total_pages": 1}

    def details(self, media, identifier, language):
        assert media == "movie" and language == "ru-RU"
        if self.during_details:
            self.during_details()
            self.during_details = None
        return {
            "id": identifier, "title": "Тёзки", "release_date": "2022-02-02", "adult": False,
            "overview": f"Преступник ищет сокровище {identifier}.", "genres": [{"id": 18, "name": "Drama"}],
            "vote_average": 8.1, "vote_count": 1000, "runtime": 90, "popularity": 11,
        }


def test_active_story_fill_preserves_homonyms_and_concurrent_pool_user_state():
    concurrent = _candidate(303, "Другой фильм")
    save_candidate_criteria_dict({
        COMMON_POOL_CRITERIA_NAME: {"min_tmdb_score": 7.2, "user_note": "keep"},
        "unrelated": {"count": 44},
    })

    def insert_concurrently():
        _insert("existing:303", concurrent)
        assert add_candidate_to_watchlist(concurrent)["state"] == "watchlist"

    report = fill_story_catalog(client=OfflineProvider(insert_concurrently))
    assert report["saved_count"] == report["created_count"] == 2
    assert report["save_stats"]["added"] == 2
    assert report["save_stats"]["pool_size_before"] == 1
    assert report["save_stats"]["pool_size_after"] == 3
    rows = load_candidate_pool_dict()
    assert {entry["tmdb_id"] for entry in rows.values()} == {101, 202, 303}
    assert rows["existing:303"] == concurrent
    assert get_title_state(concurrent) == "watchlist"
    criteria = load_candidate_criteria_dict()
    assert criteria["unrelated"] == {"count": 44}
    assert criteria[COMMON_POOL_CRITERIA_NAME]["min_tmdb_score"] == 7.2
    assert criteria[COMMON_POOL_CRITERIA_NAME]["user_note"] == "keep"
    assert fill_story_catalog(client=OfflineProvider())["saved_count"] == 0
    assert load_candidate_pool_dict() == rows


def test_additive_story_import_skips_only_exact_watched_or_unambiguous_legacy():
    watched = _candidate(101)
    mark_story_watched(watched)
    existing_payload = data.load_dataset()
    existing_payload["Legacy watch"] = {"main_info": {"title": "Legacy watch", "year": 2022, "media_type": "movie"}}
    data.save_dataset(existing_payload)
    report = import_story_catalog_candidates([
        _candidate(101, "Alternate exact title"), _candidate(202), _candidate(404, "Legacy watch")
    ])
    assert report["watched_skipped"] == 2 and report["added"] == 1
    assert {row["tmdb_id"] for row in load_candidate_pool_dict().values()} == {202}
    assert get_title_state(watched) == "watched"


def test_additive_story_updates_one_typed_alias_and_preserves_localized_fields():
    old = _candidate(101, tmdb_score=4, tmdb_votes=10, localized={
        "ru": {"title": "Русское название", "poster_path": "/ru.jpg"},
        "en": {"title": "English", "overview": "Retain existing English overview"},
    })
    _insert("old-key:101", old)
    report = import_story_catalog_candidates([
        _candidate(101, "Локальный псевдоним", localized={"ru": {"overview": "Новая аннотация"}})
    ])
    assert report["updated"] == 1 and report["added"] == 0 and report["pool_size"] == 1
    saved = load_candidate_pool_dict()["old-key:101"]
    assert saved["localized"]["ru"] == {
        "title": "Русское название", "poster_path": "/ru.jpg", "overview": "Новая аннотация"
    }
    assert saved["localized"]["en"] == old["localized"]["en"]


def test_additive_story_does_not_apply_refill_cap():
    with closing(connect()) as conn:
        apply_migrations(conn)
        with conn:
            for identifier in range(1000, 2001):
                title = f"Stored {identifier}"
                insert_candidate_record(conn, pool_key=title, candidate=_candidate(identifier, title), timestamp=utc_now())
    result = import_story_catalog_candidates([_candidate(202)])
    rows = load_candidate_pool_dict()
    assert result["pool_size_before"] == 1001
    assert result["pool_size_after"] == len(rows) == 1002
    assert {row["tmdb_id"] for row in rows.values()} == {202, *range(1000, 2001)}


def test_additive_story_rolls_back_criteria_and_candidates_together(monkeypatch):
    _insert("existing-key", _candidate(101))
    save_candidate_criteria_dict({COMMON_POOL_CRITERIA_NAME: {"count": 30, "user_tag": "unchanged"}})
    old_pool = load_candidate_pool_dict()
    old_criteria = load_candidate_criteria_dict()

    def fail(_conn):
        raise RuntimeError("synthetic FTS write failure")

    monkeypatch.setattr("storage.sqlite.candidate_pool_repository.rebuild_fts_index", fail)
    with pytest.raises(RuntimeError, match="synthetic FTS write failure"):
        import_story_catalog_candidates([_candidate(202)])
    assert load_candidate_pool_dict() == old_pool
    assert load_candidate_criteria_dict() == old_criteria


def test_additive_story_import_serializes_with_simultaneous_sqlite_writer(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from threading import Event

    from candidates.sources.tmdb import importer
    from config import constant
    from storage.sqlite.candidate_pool_repository import merge_candidate_pool_dict

    entered_import = Event()
    writer_attempted = Event()
    normalize = importer.normalize_tmdb_candidate_for_common_import
    db = Path(constant.APP_DATA_DIR) / "watchbane.sqlite3"

    def paused_import(raw, criteria):
        entered_import.set()
        assert writer_attempted.wait(5)
        return normalize(raw, criteria)

    def refill():
        assert entered_import.wait(5)
        writer_attempted.set()
        return merge_candidate_pool_dict({"refill": _candidate(303, "Another film")}, path=db)

    monkeypatch.setattr(importer, "normalize_tmdb_candidate_for_common_import", paused_import)
    with ThreadPoolExecutor(max_workers=2) as workers:
        imported = workers.submit(import_story_catalog_candidates, [_candidate(202)])
        written = workers.submit(refill)
        assert imported.result(timeout=10)["added"] == 1
        assert written.result(timeout=10)["merged"] == 1
    assert {value["tmdb_id"] for value in load_candidate_pool_dict().values()} == {202, 303}


def test_additive_story_preserves_unverifiable_existing_payload_with_reason():
    original = _candidate(101)
    _insert("legacy:broken-payload", original)
    with closing(connect()) as conn, conn:
        conn.execute("UPDATE candidate_records SET payload_json = '{}' WHERE tmdb_id = 101")
    stats = import_story_catalog_candidates([_candidate(101)])
    assert stats["retained_unverifiable_existing"] == stats["skipped_existing"] == 1
    assert stats["updated"] == stats["added"] == 0
    assert load_candidate_pool_dict() == {"legacy:broken-payload": {}}
