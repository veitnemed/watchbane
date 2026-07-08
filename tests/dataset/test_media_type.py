import pytest

from dataset.models.media_type import (
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TV,
    is_movie,
    is_tv,
    normalize_media_type,
)


@pytest.mark.parametrize("value", [None, "", " ", "unknown", object(), [], {}, False])
def test_normalize_media_type_defaults_legacy_or_unknown_values_to_tv(value) -> None:
    assert normalize_media_type(value) == MEDIA_TYPE_TV


@pytest.mark.parametrize("value", ["tv", "TV", " series ", "show", "serial", "tv_show", "tv-show"])
def test_normalize_media_type_accepts_tv_aliases(value) -> None:
    assert normalize_media_type(value) == MEDIA_TYPE_TV


@pytest.mark.parametrize("value", ["movie", "MOVIE", " film "])
def test_normalize_media_type_accepts_movie_aliases(value) -> None:
    assert normalize_media_type(value) == MEDIA_TYPE_MOVIE


def test_media_type_predicates_use_normalized_values() -> None:
    assert is_movie("film") is True
    assert is_movie("series") is False
    assert is_tv("show") is True
    assert is_tv("movie") is False
