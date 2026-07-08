"""Preview movie/card builders for add-title flow."""

from config import constant
from config import scheme
from common.cards import build_watched_movie_card
from dataset.language import choose_genre_labels
from dataset.models.media_type import normalize_media_type


def build_preview_movie_from_defaults(defaults: dict) -> dict:
    """Build a temporary dataset movie dict for read-only preview."""
    main_info = dict(defaults.get(scheme.MAIN_INFO, {}))
    main_info.setdefault("user_score", None)
    movie = {
        "main_info": main_info,
        "raw_scores": dict(defaults.get(scheme.RAW_SCORES, {})),
        constant.TAGS_VIBE_SECTION: _normalized_tags_vibe(defaults),
        constant.GENRE_SECTION: _normalized_genre(defaults),
    }
    localized = defaults.get("localized")
    if isinstance(localized, dict):
        movie["localized"] = dict(localized)
    return movie


def build_preview_card_from_defaults(
    defaults: dict,
    *,
    resolved: dict | None = None,
    meta_payload: dict | None = None,
    poster_hints: dict | None = None,
    data_language: str = "ru",
) -> dict:
    """Build watched-style card dict for GUI preview."""
    preview_movie = build_preview_movie_from_defaults(defaults)
    meta_obj = dict(meta_payload or {})
    card = build_watched_movie_card(
        preview_movie,
        meta_obj=meta_obj or None,
        data_language=data_language,
    )
    preview_main_info = preview_movie.get(scheme.MAIN_INFO, {})
    card["media_type"] = normalize_media_type(preview_main_info.get("media_type"))

    genre_section = _normalized_genre(defaults)
    genre_keys = [
        feature
        for feature in constant.GENRE
        if genre_section.get(feature) == 1
    ]
    genres_display = choose_genre_labels(genre_keys, data_language)
    if len(genres_display) > 0:
        card["genres"] = genres_display

    source_values = (resolved or {}).get("source_values") or {}
    description = source_values.get("description")
    if description not in (None, "") and str(description).strip():
        card["overview"] = str(description).strip()

    poster_url = _poster_url_from_hints(poster_hints)
    if poster_url not in (None, ""):
        card["poster_url"] = poster_url
        from posters.download_images import download_poster_url_for_preview

        local_path = download_poster_url_for_preview(poster_url)
        if local_path not in (None, ""):
            card["poster_src"] = local_path
            card["poster_path"] = local_path
        else:
            card["poster_src"] = poster_url

    return card


def _poster_url_from_hints(poster_hints: dict | None) -> str | None:
    hints = poster_hints if isinstance(poster_hints, dict) else {}
    poster_url = hints.get("poster_url") or hints.get("poster_src")
    if poster_url not in (None, ""):
        return str(poster_url).strip()

    poster_path = hints.get("poster_path")
    if poster_path in (None, ""):
        return None

    from posters.cache import build_tmdb_poster_url

    return build_tmdb_poster_url(str(poster_path).strip())


def _normalized_tags_vibe(defaults: dict) -> dict:
    tags = dict(defaults.get(scheme.TAGS_VIBE, {}) or {})
    for feature in constant.TAGS_VIBE:
        tags.setdefault(feature, 0)
    return tags


def _normalized_genre(defaults: dict) -> dict:
    genre_values = dict(defaults.get(scheme.GENRE, {}) or {})
    for feature in constant.GENRE:
        genre_values.setdefault(feature, 0)
    return genre_values
