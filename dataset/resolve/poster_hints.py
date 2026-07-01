"""Poster hints from resolve results and candidate records."""


def build_poster_hints_from_resolve(resolve_result: dict) -> dict:
    """Returns poster fields from add-flow resolve result without API calls."""
    context: dict = {}
    tmdb_data = resolve_result.get("tmdb_data")
    api_data = resolve_result.get("api_data")
    if isinstance(tmdb_data, dict):
        context["tmdb_data"] = tmdb_data
    if isinstance(api_data, dict):
        context["api"] = api_data
    from posters.cache import extract_existing_poster_info

    return extract_existing_poster_info(context)


def build_poster_hints_from_candidate(candidate: dict) -> dict:
    """Returns poster fields from one candidate record."""
    from posters.cache import extract_existing_poster_info

    return extract_existing_poster_info(candidate)
