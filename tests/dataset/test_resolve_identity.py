"""Tests for dataset.resolve.identity."""

from dataset.resolve.identity import (
    is_sql_candidate_identity_safe,
    title_identity_match,
)
from dataset.resolve.priority import build_add_defaults_by_priority
from dataset.resolve.status import get_sql_status


def test_title_identity_match_equal_titles() -> None:
    assert title_identity_match("Псих", "Псих") is True


def test_sql_rejected_on_identity_mismatch() -> None:
    sql_data = {
        "title": "Mad",
        "original_title": "Mad",
        "year": 2010,
        "genres": ["Animation"],
        "imdb_rating": 6.0,
        "imdb_votes": 3480,
    }
    api_data = {
        "name": "Псих",
        "year": 2020,
        "rating": {"kp": 7.3, "imdb": 7.0},
        "votes": {"kp": 1000, "imdb": 500},
        "genres": [{"name": "драма"}],
    }

    built = build_add_defaults_by_priority("Псих", sql_data, api_data, None)
    sql_status = get_sql_status(sql_data, built["sql_identity"])

    assert built["sql_identity"]["accepted"] is False
    assert built["sql_identity"]["reason"] == "identity_mismatch"
    assert sql_status == "найдено, но отклонено (identity_mismatch)"
    assert built["defaults"]["main_info"]["title"] == "Псих"
    assert built["defaults"]["raw_scores"]["imdb_score"] == 7.0
    assert built["sources"]["imdb_score"] == "kp_api"


def test_sql_accepted_when_imdb_id_matches() -> None:
    sql_data = {
        "tconst": "tt1234567",
        "title": "SQL Title",
        "year": 2020,
        "genres": ["драма"],
        "imdb_rating": 7.8,
        "imdb_votes": 1000,
    }
    api_data = {
        "externalId": {"imdb": "tt1234567"},
        "name": "API Title",
        "year": 2021,
        "rating": {"kp": 8.0, "imdb": 6.0},
        "votes": {"kp": 2000, "imdb": 300},
        "genres": [{"name": "драма"}],
    }

    accepted, reason = is_sql_candidate_identity_safe(sql_data, api_data, "Input Title")
    built = build_add_defaults_by_priority("Input Title", sql_data, api_data, None)

    assert accepted is True
    assert reason == "imdb_id_match"
    assert built["defaults"]["raw_scores"]["imdb_score"] == 7.8
    assert built["sources"]["imdb_score"] == "imdb_sql"


def test_sql_only_flow_accepted() -> None:
    sql_data = {
        "title": "Mad",
        "original_title": "Mad",
        "year": 2010,
        "genres": ["Animation"],
        "imdb_rating": 6.0,
        "imdb_votes": 3480,
    }

    built = build_add_defaults_by_priority("Mad", sql_data, None, None)

    assert built["sql_identity"]["accepted"] is True
    assert built["sql_identity"]["reason"] == "sql_only"
    assert built["defaults"]["raw_scores"]["imdb_score"] == 6.0
    assert built["sources"]["imdb_score"] == "imdb_sql"
