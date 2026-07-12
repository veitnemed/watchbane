"""TMDb discovery and genre endpoints."""

from apis.tmdb.client import (  # noqa: F401
    discover_tv_candidates,
    get_movie_genre_list,
    get_tv_genre_list,
)
