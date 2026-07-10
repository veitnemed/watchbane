"""Tests for TMDb-only add defaults priority wrapper."""

from config import constant
from dataset.resolve.priority import build_add_defaults_by_priority, build_add_defaults_from_tmdb


def test_tmdb_data_produces_defaults() -> None:
    tmdb_data = {
        "title": "TMDb Title",
        "year": 2020,
        "country": "США",
        "tmdb_score": 7.8,
        "tmdb_votes": 500,
        "tmdb_popularity": 12.3,
        "genres_tmdb": ["Crime", "Drama"],
        "overview": "Overview text",
    }

    built = build_add_defaults_from_tmdb("Input Title", tmdb_data)

    assert built["defaults"]["main_info"]["title"] == "TMDb Title"
    assert built["defaults"]["main_info"]["year"] == 2020
    assert built["defaults"]["main_info"]["country"] == "США"
    assert built["sources"]["title"] == "tmdb_api"
    assert built["defaults"]["raw_scores"] == {
        "tmdb_score": 7.8,
        "tmdb_votes": 500,
        "tmdb_popularity": 12.3,
    }
    assert built["defaults"]["genre"]["has_crime"] == 1
    assert built["defaults"]["genre"]["has_drama"] == 1
    assert built["source_values"]["description"] == "Overview text"


def test_priority_wrapper_uses_tmdb_data_only() -> None:
    tmdb_data = {
        "title": "TMDb Title",
        "year": 2015,
        "genres_tmdb": ["Crime", "Drama"],
        "overview": "Overview text",
    }

    built = build_add_defaults_by_priority("Input Title", tmdb_data)

    assert built["defaults"]["main_info"]["title"] == "TMDb Title"
    assert built["sources"]["year"] == "tmdb_api"
    assert built["sources"]["genres"] == "tmdb_api"
    assert built["defaults"]["genre"]["has_crime"] == 1
    assert built["defaults"]["genre"]["has_drama"] == 1
    assert "sql_identity" not in built
    assert "kp_score" not in built["defaults"]["raw_scores"]
    assert "imdb_score" not in built["defaults"]["raw_scores"]
    assert "kp_api" not in set(built["sources"].values())
    assert "imdb_sql" not in set(built["sources"].values())


def test_empty_tmdb_title_falls_back_to_input_source() -> None:
    built = build_add_defaults_by_priority("Input Title", {})

    assert built["defaults"]["main_info"]["title"] == "Input Title"
    assert built["sources"]["title"] == "input"
    assert built["defaults"]["raw_scores"] == {}


def test_genre_defaults_cover_full_schema() -> None:
    built = build_add_defaults_by_priority(
        "Test",
        {"title": "Test", "genres_tmdb": ["драма"]},
    )
    assert set(built["defaults"]["genre"].keys()) == set(constant.GENRE)
