from __future__ import annotations

from storage.sqlite.candidate_mapper import extract_candidate_record
from storage.sqlite.json_codec import dumps_json, loads_json
from storage.sqlite.watched_mapper import extract_watched_record


def test_extract_watched_record_defaults_legacy_tv_record() -> None:
    row = extract_watched_record(
        "Метод",
        {
            "main_info": {
                "title": "Метод",
                "year": "2015",
                "user_score": 3,
                "country": "Россия",
            },
            "raw_scores": {"tmdb_score": 7.4},
        },
    )

    assert row.dataset_key == "Метод"
    assert row.title == "Метод"
    assert row.title_normalized == "метод"
    assert row.media_type == "tv"
    assert row.year == 2015
    assert row.user_score == 3
    assert row.country == "Россия"
    assert loads_json(row.payload_json)["main_info"]["title"] == "Метод"
    assert row.meta_json is None


def test_extract_watched_record_supports_movie_identity_and_meta_ids() -> None:
    row = extract_watched_record(
        "Watchmen (2009, movie)",
        {"main_info": {"title": "Watchmen", "year": 2009, "media_type": "movie"}},
        meta={"raw_scores": {"tmdb_id": "13183", "imdb_id": "tt0409459"}},
    )

    assert row.title == "Watchmen"
    assert row.media_type == "movie"
    assert row.year == 2009
    assert row.tmdb_id == 13183
    assert row.imdb_id == "tt0409459"
    assert loads_json(row.meta_json)["raw_scores"]["imdb_id"] == "tt0409459"


def test_extract_candidate_record_handles_missing_optional_fields() -> None:
    row = extract_candidate_record(None, {"title": "Severance"})

    assert row.pool_key == "severance|"
    assert row.media_type == "tv"
    assert row.year is None
    assert row.tmdb_id is None
    assert row.final_score is None


def test_extract_candidate_record_uses_unicode_stable_identity() -> None:
    row = extract_candidate_record(None, {"title": "Ёлки!", "year": "2010", "media_type": "film"})

    assert row.pool_key == "елки|2010|movie"
    assert row.title_normalized == "елки"
    assert row.media_type == "movie"
    assert row.year == 2010


def test_dumps_json_is_canonical_and_unicode_safe() -> None:
    left = dumps_json({"b": "Ю", "a": 1})
    right = dumps_json({"a": 1, "b": "Ю"})

    assert left == right
    assert "Ю" in left
    assert loads_json(left) == {"a": 1, "b": "Ю"}
