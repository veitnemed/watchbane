"""Canonical genre normalization for runtime candidate-pool filters."""

from __future__ import annotations

from candidates import genre_schema


def normalize_genre_name(value) -> str:
    """Returns canonical genre key for one genre label."""
    genre_key = genre_schema.normalize_genre_to_key(str(value or ""))
    if genre_key is not None:
        return genre_key
    return str(value or "").strip().casefold()


def normalize_genre_list(values) -> list[str]:
    """Returns ordered unique canonical genre keys."""
    return genre_schema.normalize_genre_filter_list(values)


def genres_match_any(candidate_genres, required_genres) -> bool:
    """True when candidate has at least one required genre after normalization."""
    candidate_keys = normalize_genre_list(candidate_genres)
    required_keys = normalize_genre_list(required_genres)
    return genre_schema.genre_keys_match_any(candidate_keys, required_keys)


def genres_match_all(candidate_genres, required_genres) -> bool:
    """True when candidate has all required genres after normalization."""
    candidate_keys = set(normalize_genre_list(candidate_genres))
    required_keys = normalize_genre_list(required_genres)
    if len(required_keys) == 0:
        return True
    return set(required_keys).issubset(candidate_keys)


def genres_match_none(candidate_genres, excluded_genres) -> bool:
    """True when excluded genres do not intersect with candidate genres."""
    candidate_keys = normalize_genre_list(candidate_genres)
    excluded_keys = normalize_genre_list(excluded_genres)
    return genre_schema.genre_keys_match_none(candidate_keys, excluded_keys)
