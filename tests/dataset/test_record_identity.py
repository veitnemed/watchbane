from dataset.models.identity import (
    build_dataset_record_key,
    duplicate_title_exists,
    find_case_insensitive_key,
    find_dataset_title,
    normalize_title_key,
)


def test_normalize_title_key() -> None:
    assert normalize_title_key("  Breaking Bad  ") == "breaking bad"


def test_find_dataset_title_case_insensitive() -> None:
    data = {"Breaking Bad": {}, "The Wire": {}}
    assert find_dataset_title(data, "breaking bad") == "Breaking Bad"
    assert find_dataset_title(data, "THE WIRE") == "The Wire"
    assert find_dataset_title(data, "missing") is None


def test_duplicate_title_exists() -> None:
    data = {"Breaking Bad": {}}
    assert duplicate_title_exists(data, "breaking bad") is True
    assert duplicate_title_exists(data, "The Wire") is False


def test_duplicate_title_exists_uses_year_and_media_type_when_provided() -> None:
    data = {
        "Watchmen": {"main_info": {"title": "Watchmen", "year": 2019, "media_type": "tv"}},
    }

    assert duplicate_title_exists(data, "watchmen", year=2019, media_type="tv") is True
    assert duplicate_title_exists(data, "watchmen", year=2019, media_type="movie") is False
    assert duplicate_title_exists(data, "watchmen", year=2009, media_type="movie") is False


def test_build_dataset_record_key_keeps_plain_title_when_available() -> None:
    assert build_dataset_record_key({}, "Watchmen", year=2009, media_type="movie") == "Watchmen"


def test_build_dataset_record_key_adds_identity_suffix_for_same_title_different_type() -> None:
    data = {
        "Watchmen": {"main_info": {"title": "Watchmen", "year": 2019, "media_type": "tv"}},
    }

    assert build_dataset_record_key(data, "Watchmen", year=2009, media_type="movie") == "Watchmen (2009, movie)"


def test_find_case_insensitive_key_for_meta() -> None:
    meta = {"Breaking Bad": {"description": "test"}}
    assert find_case_insensitive_key(meta, "BREAKING BAD") == "Breaking Bad"
    assert find_case_insensitive_key(meta, "other") is None
