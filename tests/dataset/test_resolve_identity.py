"""Tests for dataset.resolve.identity."""

from dataset.resolve.identity import (
    is_sql_candidate_identity_safe,
    title_identity_match,
)
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

    accepted, reason = is_sql_candidate_identity_safe(sql_data, api_data, "Псих")
    sql_identity = {"accepted": accepted, "reason": reason}
    sql_status = get_sql_status(sql_data, sql_identity)

    assert accepted is False
    assert reason == "identity_mismatch"
    assert sql_status == "найдено, но отклонено (identity_mismatch)"


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

    assert accepted is True
    assert reason == "imdb_id_match"


def test_sql_only_flow_accepted() -> None:
    sql_data = {
        "title": "Mad",
        "original_title": "Mad",
        "year": 2010,
        "genres": ["Animation"],
        "imdb_rating": 6.0,
        "imdb_votes": 3480,
    }

    accepted, reason = is_sql_candidate_identity_safe(sql_data, None, "Mad")

    assert accepted is True
    assert reason == "sql_only"
