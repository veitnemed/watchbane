"""Pure helpers for desktop candidate list display (presenters)."""

from __future__ import annotations

from candidates import service as candidate_service
from dataset import service
from dataset.resolve.poster_hints import build_poster_hints_from_candidate

SORT_MODE_METRIC_PREFIX = {
    "final_score": "Итог",
    "quality_score": "Качество",
    "tmdb_score": "TMDb",
    "tmdb_votes": "TMDb",
    "tmdb_popularity": "Популярность",
    "year": "Год",
}


def format_candidate_title_line(candidate: dict) -> str:
    """Primary list row text: title and year."""
    title = candidate.get("title") or candidate.get("name") or "Без названия"
    year = candidate.get("year") or "?"
    return f"{title} ({year})"


def format_candidate_metric_value(candidate: dict, sort_mode: str) -> str:
    """Secondary list metric for the active sort mode."""
    from candidates.models.schema import coerce_candidate_number

    field_name = sort_mode if sort_mode in candidate_service.SEARCH_SORT_MODES else candidate_service.DEFAULT_SEARCH_SORT_MODE
    prefix = SORT_MODE_METRIC_PREFIX.get(field_name, "")
    value = coerce_candidate_number(candidate.get(field_name))
    if value is None:
        return f"{prefix} —" if prefix else "—"
    if field_name.endswith("_votes"):
        try:
            return f"{prefix} {int(value):,}".replace(",", " ")
        except (TypeError, ValueError):
            return f"{prefix} {value}"
    try:
        return f"{prefix} {float(value):.1f}"
    except (TypeError, ValueError):
        return f"{prefix} {value}"


def format_candidate_list_label(candidate: dict, sort_mode: str = "final_score") -> str:
    """Legacy single-line label (title + metric)."""
    return f"{format_candidate_title_line(candidate)}  {format_candidate_metric_value(candidate, sort_mode)}"


def candidate_search_text(candidate: dict) -> str:
    """Lowercase haystack for local title search in the Candidates tab."""
    parts = [
        candidate.get("title"),
        candidate.get("name"),
        candidate.get("alternative_title"),
        candidate.get("alternativeName"),
        candidate.get("enName"),
        candidate.get("original_title"),
    ]
    return " ".join(str(part).strip() for part in parts if part not in (None, "")).casefold()


def filter_candidates_by_title(candidates: list[dict], query: str) -> list[dict]:
    """Return candidates whose title fields contain the query (case-insensitive)."""
    normalized = str(query or "").strip().casefold()
    if normalized == "":
        return list(candidates)
    return [
        candidate
        for candidate in candidates
        if normalized in candidate_search_text(candidate)
    ]


def build_candidate_search_index(candidates: list[dict]):
    """Build reusable search index for candidate list filtering."""
    from desktop.shared.widgets.list_search import SearchIndex, SearchIndexItem

    items = [
        SearchIndexItem(
            item=candidate,
            haystack=candidate_search_text(candidate),
            selection_key=candidate_detail_identity(candidate),
        )
        for candidate in candidates
    ]
    return SearchIndex(items)


def candidate_detail_identity(candidate: dict) -> str:
    """Stable key for caching detail entries in the Candidates tab."""
    return str(candidate.get("pool_entry_key") or candidate.get("title") or "candidate")


def resolve_local_poster_path_for_candidate(candidate: dict) -> str | None:
    """Return a local poster path from pool fields. Never downloads or uses network."""
    from desktop.shared.detail.posters import resolve_local_poster_path_from_record

    return resolve_local_poster_path_from_record(
        candidate,
        title=candidate.get("title") or candidate.get("name"),
        year=candidate.get("year"),
    )


def candidate_poster_url_for_download(candidate: dict) -> str | None:
    """Return poster URL when local preview file is missing."""
    if resolve_local_poster_path_for_candidate(candidate) not in (None, ""):
        return None

    hints = build_poster_hints_from_candidate(candidate)
    poster_url = hints.get("poster_url")
    if poster_url in (None, ""):
        return None
    text = str(poster_url).strip()
    if text.startswith(("http://", "https://")) is False:
        return None
    return text


def build_candidate_readonly_card(candidate: dict) -> dict:
    """Build a WatchedDetailCard dict from pool fields without transfer/network IO."""
    from candidates.models.schema import coerce_candidate_number

    title = candidate.get("title") or candidate.get("name") or "Без названия"
    overview = candidate.get("overview") or candidate.get("description")
    overview_text = str(overview).strip() if overview not in (None, "") else ""
    country = candidate.get("country_display") or candidate.get("country")
    object_type = candidate.get("media_type") or candidate.get("object_type")
    if object_type in (None, "") and (
        candidate.get("number_of_seasons") not in (None, "", 0, "0")
        or candidate.get("number_of_episodes") not in (None, "", 0, "0")
    ):
        object_type = "series"

    card: dict = {
        "title": title,
        "year": candidate.get("year"),
        "country": country,
        "object_type": object_type or "unknown",
        "number_of_seasons": candidate.get("number_of_seasons"),
        "number_of_episodes": candidate.get("number_of_episodes"),
    }
    if overview_text:
        card["overview"] = overview_text

    for field in ("tmdb_score", "tmdb_votes", "final_score"):
        value = coerce_candidate_number(candidate.get(field))
        if value is not None:
            card[field] = value
    if candidate.get("imdb_id") not in (None, ""):
        card["imdb_id"] = candidate.get("imdb_id")

    genres_display = candidate.get("genres_display") or candidate.get("genres") or []
    if isinstance(genres_display, list) and len(genres_display) > 0:
        card["genres"] = [str(item).strip() for item in genres_display if str(item).strip()]

    local_poster = resolve_local_poster_path_for_candidate(candidate)
    if local_poster not in (None, ""):
        card["poster_path"] = local_poster
        card["poster_src"] = local_poster

    return card


def build_candidate_readonly_detail_entry(candidate: dict) -> tuple:
    """Build WatchedDetailCard entry tuple for read-only Candidates tab preview."""
    identity = candidate_detail_identity(candidate)
    card = build_candidate_readonly_card(candidate)
    movie_stub = {
        "main_info": {
            "title": card.get("title") or identity,
            "year": card.get("year"),
        }
    }
    return (f"__candidate__{identity}", movie_stub, card)


def build_candidate_detail_entry(candidate: dict) -> tuple:
    """Build WatchedDetailCard entry tuple from pool candidate (transfer flow)."""
    bundle = service.build_candidate_transfer_bundle(candidate)
    identity = candidate_detail_identity(candidate)
    return (f"__candidate__{identity}", bundle.preview_movie, bundle.preview_card)
