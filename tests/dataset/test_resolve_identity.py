"""Tests for dataset.resolve.identity."""

from dataset.resolve.identity import title_identity_match


def test_title_identity_match_equal_titles() -> None:
    assert title_identity_match("Псих", "Псих") is True


def test_title_identity_match_substring() -> None:
    assert title_identity_match("Breaking Bad", "Breaking Bad: Original") is True


def test_title_identity_match_empty_values() -> None:
    assert title_identity_match("", "Title") is False
    assert title_identity_match("Title", None) is False
