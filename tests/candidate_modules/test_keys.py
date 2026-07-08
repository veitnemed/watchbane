"""Tests for candidate identity keys."""

from candidates.models.keys import normalize_key_part, pool_entry_key, title_identity_key


def test_title_identity_key_stable() -> None:
    candidate = {"title": "Breaking Bad", "year": 2008}
    assert title_identity_key(candidate) == "breaking bad|2008"


def test_pool_entry_key_matches_title_identity() -> None:
    candidate = {"title": "Show", "year": 2018, "criteria_name": "pool"}
    assert pool_entry_key(candidate) == title_identity_key(candidate)


def test_normalize_key_part_handles_russian_yo_and_quotes() -> None:
    assert normalize_key_part("\u00abНадёжный метод\u00bb!") == "надежный метод"
