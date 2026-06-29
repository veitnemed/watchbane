"""Service layer for desktop/console add-title flows without UI imports."""

from __future__ import annotations

from dataclasses import dataclass

from config import constant
from config import genre_tags
from config import scheme
from dataset import title_resolve
from dataset.storage_movie import add_movie
from web.export import build_watched_movie_card


@dataclass(frozen=True)
class AddTitleResolveBundle:
    """Resolved add-title data ready for preview and save."""

    title: str
    country: str
    defaults: dict
    meta_payload: dict
    poster_hints: dict
    preview_movie: dict
    preview_card: dict
    found: bool
    statuses: dict


def resolve_title_for_add(
    title: str,
    country: str = "",
    *,
    on_progress=None,
) -> AddTitleResolveBundle:
    """Resolve title through SQL/KP/TMDb and build preview card data."""
    resolved = title_resolve.resolve_title_data_for_add(
        title,
        country,
        on_progress=on_progress,
    )
    return build_add_title_resolve_bundle(resolved)


def build_add_title_resolve_bundle(resolved: dict) -> AddTitleResolveBundle:
    """Build preview/save bundle from resolve_title_data_for_add result."""
    defaults = resolved.get("defaults")
    if defaults is None:
        defaults = title_resolve.build_empty_add_defaults(resolved["title"])

    meta_payload = title_resolve.build_add_meta_payload(resolved)
    poster_hints = title_resolve.build_poster_hints_from_resolve(resolved)
    preview_movie = build_preview_movie_from_defaults(defaults)
    preview_card = build_preview_card_from_defaults(
        defaults,
        resolved=resolved,
        meta_payload=meta_payload,
        poster_hints=poster_hints,
    )

    return AddTitleResolveBundle(
        title=str(resolved.get("title") or ""),
        country=str(resolved.get("country") or ""),
        defaults=defaults,
        meta_payload=meta_payload,
        poster_hints=poster_hints,
        preview_movie=preview_movie,
        preview_card=preview_card,
        found=bool(resolved.get("found")),
        statuses=dict(resolved.get("statuses") or {}),
    )


def build_preview_movie_from_defaults(defaults: dict) -> dict:
    """Build a temporary dataset movie dict for read-only preview."""
    main_info = dict(defaults.get(scheme.MAIN_INFO, {}))
    main_info.setdefault("user_score", None)
    return {
        "main_info": main_info,
        "raw_scores": dict(defaults.get(scheme.RAW_SCORES, {})),
        constant.TAGS_VIBE_SECTION: _normalized_tags_vibe(defaults),
        constant.GENRE_SECTION: _normalized_genre(defaults),
    }


def build_preview_card_from_defaults(
    defaults: dict,
    *,
    resolved: dict | None = None,
    meta_payload: dict | None = None,
    poster_hints: dict | None = None,
) -> dict:
    """Build watched-style card dict for GUI preview."""
    preview_movie = build_preview_movie_from_defaults(defaults)
    meta_obj = dict(meta_payload or {})
    card = build_watched_movie_card(preview_movie, meta_obj=meta_obj or None)

    genre_labels = genre_tags.get_genre_labels()
    genre_section = _normalized_genre(defaults)
    genres_display = [
        genre_labels[feature]
        for feature in constant.GENRE
        if genre_section.get(feature) == 1 and feature in genre_labels
    ]
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


def build_movie_record_from_defaults(defaults: dict, user_score: float, *, year: int | None = None) -> dict:
    """Build add_dataset_record payload from resolved defaults."""
    main_info = dict(defaults.get(scheme.MAIN_INFO, {}))
    main_info["user_score"] = float(user_score)
    if year is not None:
        main_info["year"] = int(year)
    return {
        "main_info": main_info,
        "raw_scores": dict(defaults.get(scheme.RAW_SCORES, {})),
        constant.TAGS_VIBE_SECTION: _normalized_tags_vibe(defaults),
        constant.GENRE_SECTION: _normalized_genre(defaults),
    }


def save_add_title_record(
    defaults: dict,
    user_score: float,
    *,
    meta_payload=None,
    poster_hints=None,
    year: int | None = None,
):
    """Save a new watched title through the existing add service."""
    movie = build_movie_record_from_defaults(defaults, user_score, year=year)
    return add_movie(
        movie,
        meta_payload=meta_payload,
        poster_hints=poster_hints,
        print_message=False,
    )


def format_resolve_status_lines(statuses: dict) -> list[str]:
    """Compact status lines for GUI."""
    if not isinstance(statuses, dict):
        return []
    lines = []
    for key, label in (
        ("sql", "IMDb SQL"),
        ("sql_second_pass", "IMDb SQL (2-й проход)"),
        ("kp_api", "KP API"),
        ("tmdb_api", "TMDb API"),
    ):
        value = statuses.get(key)
        if value not in (None, ""):
            lines.append(f"{label}: {value}")
    return lines


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
