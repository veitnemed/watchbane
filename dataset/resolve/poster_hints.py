"""Poster hints from resolve results and candidate records."""


def build_poster_hints_from_resolve(resolve_result: dict, *, data_language: str | None = None) -> dict:
    """Returns poster fields from add-flow resolve result without API calls."""
    context: dict = {}
    tmdb_data = resolve_result.get("tmdb_data")
    if isinstance(tmdb_data, dict):
        context["tmdb_data"] = tmdb_data
        context["localized"] = tmdb_data.get("localized")
    from posters.cache import extract_existing_poster_info

    return extract_existing_poster_info(context, data_language=data_language)


def build_poster_hints_from_candidate(candidate: dict, *, data_language: str | None = None) -> dict:
    """Returns poster fields from one candidate record."""
    from posters.cache import extract_existing_poster_info

    return extract_existing_poster_info(candidate, data_language=data_language)
