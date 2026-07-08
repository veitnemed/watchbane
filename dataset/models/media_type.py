"""Media type contract for watched records."""

from typing import Any

MEDIA_TYPE_TV = "tv"
MEDIA_TYPE_MOVIE = "movie"
DEFAULT_MEDIA_TYPE = MEDIA_TYPE_TV

TV_MEDIA_TYPE_ALIASES = {
    "series",
    "serial",
    "show",
    "tv",
    "tv_show",
    "tv-show",
}
MOVIE_MEDIA_TYPE_ALIASES = {
    "film",
    "movie",
}


def normalize_media_type(value: Any) -> str:
    """Return a supported media type, defaulting legacy/unknown values to tv."""
    text = str(value or "").strip().casefold()
    if text in MOVIE_MEDIA_TYPE_ALIASES:
        return MEDIA_TYPE_MOVIE
    if text in TV_MEDIA_TYPE_ALIASES:
        return MEDIA_TYPE_TV
    return DEFAULT_MEDIA_TYPE


def is_movie(value: Any) -> bool:
    """Return True when value resolves to movie media type."""
    return normalize_media_type(value) == MEDIA_TYPE_MOVIE


def is_tv(value: Any) -> bool:
    """Return True when value resolves to tv media type."""
    return normalize_media_type(value) == MEDIA_TYPE_TV
