"""Tests for dataset.transfer.candidate."""

import copy

from config import constant
from config import scheme
from dataset.transfer.candidate import (
    build_candidate_genre_transfer_preview,
    build_candidate_transfer_genre_defaults,
    build_candidate_transfer_payload,
)


def test_transfer_payload_uses_genre_keys_mapper() -> None:
    candidate = {
        "title": "Mapped Transfer",
        "year": 2021,
        "genres": ["Mystery"],
        "genre_keys": ["mystery", "drama"],
    }
    payload = build_candidate_transfer_payload(candidate)
    genre_defaults = payload["defaults"][scheme.GENRE]

    assert genre_defaults["has_detective"] == 1
    assert genre_defaults["has_drama"] == 1
    assert "has_mystery" not in genre_defaults
    assert set(genre_defaults.keys()) == set(constant.GENRE)


def test_transfer_payload_falls_back_to_raw_genres() -> None:
    candidate = {
        "title": "Legacy Transfer",
        "genres": ["драма", "криминал"],
    }
    payload = build_candidate_transfer_payload(candidate)
    genre_defaults = payload["defaults"][scheme.GENRE]

    assert genre_defaults["has_drama"] == 1
    assert genre_defaults["has_crime"] == 1


def test_transfer_payload_does_not_mutate_candidate() -> None:
    candidate = {
        "title": "Immutable",
        "genre_keys": ["mystery"],
        "genres": ["Mystery"],
    }
    before = copy.deepcopy(candidate)
    build_candidate_transfer_payload(candidate)
    assert candidate == before


def test_genre_preview_maps_genre_keys() -> None:
    preview = build_candidate_genre_transfer_preview({
        "genre_keys": ["mystery", "drama"],
        "genres": ["Mystery"],
    })

    assert preview["mapper_status"] == "ok"
    assert preview["used_fallback"] is False
    assert "has_detective" in preview["active_has_features"]
    assert preview["dataset_genre"] == build_candidate_transfer_genre_defaults({
        "genre_keys": ["mystery", "drama"],
        "genres": ["Mystery"],
    })


def test_genre_preview_warns_when_all_zero_with_raw_signals() -> None:
    preview = build_candidate_genre_transfer_preview({
        "genres": ["TotallyUnknownGenreXYZ"],
    })

    assert preview["has_raw_genre_signals"] is True
    assert preview["warn_all_genres_zero"] is True
    assert preview["active_has_features"] == []
