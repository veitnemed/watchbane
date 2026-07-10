"""Save resolved add-title defaults to watched dataset."""

from copy import deepcopy

from config import scheme
from dataset.add_flow.preview import build_preview_movie_from_defaults
from dataset.storage_movie import add_movie


def build_movie_record_from_defaults(defaults: dict, user_score: float) -> dict:
    """Build add_dataset_record payload from resolved defaults."""
    movie = build_preview_movie_from_defaults(defaults)
    movie["main_info"]["user_score"] = float(user_score)
    localized = defaults.get("localized")
    if isinstance(localized, dict):
        movie["localized"] = deepcopy(localized)
    genres_tmdb = defaults.get("genres_tmdb")
    if isinstance(genres_tmdb, list) and genres_tmdb:
        movie["genres_tmdb"] = list(genres_tmdb)
    return movie


def save_add_title_record(
    defaults: dict,
    user_score: float,
    *,
    meta_payload=None,
    poster_hints=None,
    pool_candidate: dict | None = None,
):
    """Save a new watched title through the existing add service."""
    movie = build_movie_record_from_defaults(defaults, user_score)
    return add_movie(
        movie,
        meta_payload=meta_payload,
        poster_hints=poster_hints,
        pool_candidate=pool_candidate,
        print_message=False,
    )
