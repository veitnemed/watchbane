"""Tests for dataset.resolve.priority source merge."""

from config import constant
from dataset.resolve.priority import build_add_defaults_by_priority


def test_priority_prefers_kp_title_over_input_and_sql() -> None:
    sql_data = {
        "title": "SQL Title",
        "year": 2010,
        "genres": ["Animation"],
        "imdb_rating": 6.0,
        "imdb_votes": 100,
    }
    api_data = {
        "name": "KP Title",
        "year": 2020,
        "rating": {"kp": 7.0},
        "votes": {"kp": 500},
        "genres": [{"name": "драма"}],
    }

    built = build_add_defaults_by_priority("Input Title", sql_data, api_data, None)

    assert built["defaults"]["main_info"]["title"] == "KP Title"
    assert built["sources"]["title"] == "kp_api"
    assert built["sources"]["year"] == "kp_api"
    assert built["sources"]["genres"] == "kp_api"


def test_priority_uses_tmdb_when_kp_missing() -> None:
    sql_data = None
    api_data = None
    tmdb_data = {
        "title": "TMDb Title",
        "year": 2015,
        "genres_tmdb": ["Crime", "Drama"],
        "overview": "Overview text",
    }

    built = build_add_defaults_by_priority("Input Title", sql_data, api_data, tmdb_data)

    assert built["defaults"]["main_info"]["title"] == "Input Title"
    assert built["sources"]["year"] == "tmdb_api"
    assert built["sources"]["genres"] == "tmdb_api"
    assert built["defaults"]["genre"]["has_crime"] == 1
    assert built["defaults"]["genre"]["has_drama"] == 1


def test_priority_rejects_sql_year_mismatch() -> None:
    sql_data = {
        "title": "Псих",
        "year": 2010,
        "genres": ["драма"],
        "imdb_rating": 6.0,
        "imdb_votes": 100,
    }
    api_data = {
        "name": "Псих",
        "year": 2020,
        "rating": {"kp": 7.3, "imdb": 7.0},
        "votes": {"kp": 1000, "imdb": 500},
        "genres": [{"name": "драма"}],
    }

    built = build_add_defaults_by_priority("Псих", sql_data, api_data, None)

    assert built["sql_identity"]["accepted"] is False
    assert built["sql_identity"]["reason"] == "year_mismatch"
    assert built["defaults"]["raw_scores"]["imdb_score"] == 7.0


def test_genre_defaults_cover_full_schema() -> None:
    built = build_add_defaults_by_priority(
        "Test",
        None,
        {"name": "Test", "genres": [{"name": "драма"}]},
        None,
    )
    assert set(built["defaults"]["genre"].keys()) == set(constant.GENRE)
