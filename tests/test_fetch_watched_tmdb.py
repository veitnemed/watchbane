import copy
import tempfile
from pathlib import Path
from unittest.mock import patch

from config import constant
from config import scheme
from common import format_score
from candidates.keys import title_identity_key


def _make_movie(title: str, user_score: float, year: int, raw_score: float = 8.0) -> dict:
    tags_vibe = {feature: 0 for feature in constant.TAGS_VIBE}
    genre_tags = {feature: 0 for feature in constant.GENRE}

    return {
        "main_info": {
            "title": title,
            "user_score": user_score,
            "year": year,
        },
        "raw_scores": {
            "kp_score": raw_score,
            "kp_votes": 120000,
            "imdb_score": raw_score,
            "imdb_votes": 1200,
        },
        "computed_scores": format_score.raw_to_struct(
            {
                "kp_score": raw_score,
                "kp_votes": 120000,
                "imdb_score": raw_score,
                "imdb_votes": 1200,
            },
            {
                "title": title,
                "user_score": user_score,
                "year": year,
            },
        ),
        scheme.TAGS_VIBE: tags_vibe,
        constant.GENRE_SECTION: genre_tags,
    }


def test_match_tmdb_search_result_accepts_title_and_year() -> None:
    from posters.fetch_watched_tmdb import match_tmdb_search_result

    results = [
        {
            "id": 101,
            "name": "Breaking Bad",
            "original_name": "Breaking Bad",
            "first_air_date": "2008-01-20",
        }
    ]

    matched, status = match_tmdb_search_result("Breaking Bad", 2008, results)

    assert status == "matched"
    assert matched["id"] == 101


def test_match_tmdb_search_result_uncertain_when_multiple_matches() -> None:
    from posters.fetch_watched_tmdb import match_tmdb_search_result

    results = [
        {"id": 1, "name": "Show", "original_name": "Show", "first_air_date": "2020-01-01"},
        {"id": 2, "name": "Show", "original_name": "Show", "first_air_date": "2020-06-01"},
    ]

    matched, status = match_tmdb_search_result("Show", 2020, results)

    assert matched is None
    assert status == "uncertain_match"


def test_merge_watched_meta_fields_does_not_overwrite_existing() -> None:
    from posters.fetch_watched_tmdb import merge_watched_meta_fields

    movie = _make_movie("Alpha", 8.0, 2020)
    meta = {
        "Alpha": {
            "main_info": movie["main_info"],
            "raw_scores": movie["raw_scores"],
            "tmdb_id": 42,
            "description": "Existing description",
        }
    }
    original = copy.deepcopy(meta)

    updated_meta, merged = merge_watched_meta_fields(
        "Alpha",
        movie,
        {
            "tmdb_id": 999,
            "description": "New description",
            "poster_url": "https://example.com/poster.jpg",
        },
        meta=meta,
    )

    assert meta == original
    assert merged["tmdb_id"] == 42
    assert merged["description"] == "Existing description"
    assert updated_meta["Alpha"]["poster_url"] == "https://example.com/poster.jpg"


def test_fetch_watched_tmdb_metadata_fills_meta_and_poster_cache(monkeypatch) -> None:
    from posters import fetch_watched_tmdb as module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {
        "Alpha": {
            "main_info": dataset["Alpha"]["main_info"],
            "raw_scores": dataset["Alpha"]["raw_scores"],
        }
    }
    poster_cache = {}

    def fake_search(title: str):
        return [
            {
                "id": 101,
                "name": title,
                "original_name": title,
                "first_air_date": "2020-01-01",
            }
        ]

    def fake_details(tmdb_id: int):
        return {
            "id": tmdb_id,
            "name": "Alpha",
            "original_name": "Alpha",
            "first_air_date": "2020-01-01",
            "overview": "Alpha overview",
            "poster_path": "/alpha.jpg",
        }

    saved_meta = {}
    saved_cache = {}

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: dataset)
    monkeypatch.setattr(module.storage_data, "load_meta", lambda: dict(meta))
    monkeypatch.setattr(module.storage_data, "save_meta", lambda payload: saved_meta.update(payload))
    monkeypatch.setattr(module, "load_poster_cache", lambda: poster_cache)
    monkeypatch.setattr(module, "save_poster_cache", lambda payload: saved_cache.update(payload))

    stats = module.fetch_watched_tmdb_metadata(search_func=fake_search, details_func=fake_details)

    assert stats["found_tmdb_id"] == 1
    assert stats["added_description"] == 1
    assert stats["added_poster_url"] == 1
    assert stats["poster_cache_updated"] == 1
    assert stats["manual_overrides_used"] == 0
    assert saved_meta["Alpha"]["tmdb_id"] == 101
    assert saved_meta["Alpha"]["description"] == "Alpha overview"
    assert saved_cache


def test_fetch_watched_tmdb_metadata_network_error_does_not_crash(monkeypatch) -> None:
    from posters import fetch_watched_tmdb as module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {
        "Alpha": {
            "main_info": dataset["Alpha"]["main_info"],
            "raw_scores": dataset["Alpha"]["raw_scores"],
        }
    }

    def fake_search(_title: str):
        raise OSError("offline")

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: dataset)
    monkeypatch.setattr(module.storage_data, "load_meta", lambda: dict(meta))
    monkeypatch.setattr(module.storage_data, "save_meta", lambda _payload: None)
    monkeypatch.setattr(module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(module, "save_poster_cache", lambda _payload: None)

    stats = module.fetch_watched_tmdb_metadata(search_func=fake_search, details_func=lambda _id: {})

    assert stats["network_errors"] == 1
    assert stats["found_tmdb_id"] == 0
    assert stats["unresolved"][0]["reason"] == "network_error"


def test_get_watched_tmdb_override_uses_title_identity_key() -> None:
    from posters.tmdb_overrides import get_watched_tmdb_override

    identity = title_identity_key({"title": "Идентификация", "year": 2022})
    overrides = {
        identity: {
            "tmdb_id": 555,
            "media_type": "tv",
            "note": "manual confirmed",
        }
    }

    entry = get_watched_tmdb_override("Идентификация", 2022, overrides=overrides)

    assert entry is not None
    assert entry["tmdb_id"] == 555


def test_fetch_watched_tmdb_metadata_uses_override_before_search(monkeypatch) -> None:
    from posters import fetch_watched_tmdb as module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {
        "Alpha": {
            "main_info": dataset["Alpha"]["main_info"],
            "raw_scores": dataset["Alpha"]["raw_scores"],
        }
    }
    identity = title_identity_key({"title": "Alpha", "year": 2020})
    overrides = {
        identity: {
            "tmdb_id": 909,
            "media_type": "tv",
            "note": "manual confirmed",
        }
    }

    def fake_search(_title: str):
        raise AssertionError("search must not run when manual override exists")

    def fake_details(tmdb_id: int):
        assert tmdb_id == 909
        return {
            "id": tmdb_id,
            "name": "Alpha",
            "original_name": "Alpha",
            "first_air_date": "2020-01-01",
            "overview": "Override overview",
            "poster_path": "/override.jpg",
        }

    saved_meta = {}
    saved_cache = {}

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: dataset)
    monkeypatch.setattr(module.storage_data, "load_meta", lambda: dict(meta))
    monkeypatch.setattr(module.storage_data, "save_meta", lambda payload: saved_meta.update(payload))
    monkeypatch.setattr(module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(module, "save_poster_cache", lambda payload: saved_cache.update(payload))

    stats = module.fetch_watched_tmdb_metadata(
        search_func=fake_search,
        details_func=fake_details,
        overrides=overrides,
    )

    assert stats["manual_overrides_used"] == 1
    assert stats["found_tmdb_id"] == 1
    assert stats["added_description"] == 1
    assert stats["added_poster_url"] == 1
    assert stats["poster_cache_updated"] == 1
    assert saved_meta["Alpha"]["source"] == "tmdb_manual_override"
    assert saved_meta["Alpha"]["description"] == "Override overview"
    assert saved_cache


def test_fetch_watched_tmdb_metadata_bad_override_does_not_crash(monkeypatch) -> None:
    from posters import fetch_watched_tmdb as module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    meta = {
        "Alpha": {
            "main_info": dataset["Alpha"]["main_info"],
            "raw_scores": dataset["Alpha"]["raw_scores"],
        }
    }
    identity = title_identity_key({"title": "Alpha", "year": 2020})
    overrides = {
        identity: {
            "tmdb_id": 909,
            "media_type": "tv",
        }
    }

    def fake_search(_title: str):
        return []

    def fake_details(_tmdb_id: int):
        raise OSError("bad override")

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: dataset)
    monkeypatch.setattr(module.storage_data, "load_meta", lambda: dict(meta))
    monkeypatch.setattr(module.storage_data, "save_meta", lambda _payload: None)
    monkeypatch.setattr(module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(module, "save_poster_cache", lambda _payload: None)

    stats = module.fetch_watched_tmdb_metadata(
        search_func=fake_search,
        details_func=fake_details,
        overrides=overrides,
    )

    assert stats["manual_overrides_failed"] == 1
    assert stats["manual_overrides_used"] == 0
    assert stats["skipped_not_found"] == 0
    assert stats["unresolved"] == [{"title": "Alpha", "year": 2020, "reason": "manual_override_failed"}]


def test_fetch_watched_tmdb_metadata_does_not_modify_dataset(monkeypatch) -> None:
    from posters import fetch_watched_tmdb as module

    dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
    original_dataset = copy.deepcopy(dataset)

    monkeypatch.setattr(module.storage_data, "load_dataset", lambda: dataset)
    monkeypatch.setattr(module.storage_data, "load_meta", lambda: {})
    monkeypatch.setattr(module.storage_data, "save_meta", lambda _payload: None)
    monkeypatch.setattr(module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(module, "save_poster_cache", lambda _payload: None)

    module.fetch_watched_tmdb_metadata(
        search_func=lambda _title: [],
        details_func=lambda _id: {},
        overrides={},
    )

    assert dataset == original_dataset


def test_format_watched_tmdb_unresolved_report() -> None:
    from posters.fetch_watched_tmdb import format_watched_tmdb_unresolved_report

    report = format_watched_tmdb_unresolved_report(
        [
            {"title": "Псих", "year": 2020, "reason": "uncertain_match"},
            {"title": "Alpha", "year": 2021, "reason": "not_found"},
        ]
    )

    assert "Псих" in report
    assert "uncertain_match" in report
    assert "not_found" in report


def test_build_add_meta_payload_includes_poster_fields() -> None:
    from dataset.title_resolve import build_add_meta_payload

    payload = build_add_meta_payload(
        {
            "source_values": {"description": "Overview"},
            "sources": {"description": "tmdb_api"},
            "tmdb_data": {
                "tmdb_id": 55,
                "poster_path": "/poster.jpg",
                "poster_url": "https://image.tmdb.org/t/p/original/poster.jpg",
            },
            "api_data": {},
        }
    )

    assert payload["tmdb_id"] == 55
    assert payload["poster_path"] == "/poster.jpg"
    assert payload["poster_url"] == "https://image.tmdb.org/t/p/original/poster.jpg"


def test_add_dataset_record_syncs_poster_cache_from_meta_payload(monkeypatch) -> None:
    from dataset import dataset_records

    movie = _make_movie("New Show", 8.5, 2021)
    meta_payload = {
        "tmdb_id": 777,
        "description": "New overview",
        "poster_path": "/new.jpg",
        "poster_url": "https://image.tmdb.org/t/p/w342/new.jpg",
        "source": "tmdb_api",
    }
    synced = {}

    def fake_sync(title, year, meta_obj=None, movie=None, extra_sources=None, cache=None, persist=True):
        synced["title"] = title
        synced["meta_obj"] = meta_obj
        return {"status": "found", "poster_url": "https://image.tmdb.org/t/p/w342/new.jpg"}

    with patch.object(dataset_records, "load_dataset", return_value={}):
        with patch.object(dataset_records, "save_dataset"):
            with patch.object(dataset_records, "add_movies_to_meta", return_value=True):
                with patch.object(dataset_records, "get_meta_obj", return_value=None):
                    with patch("posters.cache.sync_poster_cache_from_meta_and_sources", side_effect=fake_sync):
                        result = dataset_records.add_dataset_record(
                            movie,
                            meta_payload=meta_payload,
                            poster_hints={
                                "poster_path": "/new.jpg",
                                "poster_url": "https://image.tmdb.org/t/p/w342/new.jpg",
                                "status": "found",
                            },
                        )

    assert result.ok is True
    assert synced["title"] == "New Show"
