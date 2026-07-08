"""Build meta payloads for watched add and candidate transfer."""

from copy import deepcopy


def build_candidate_meta_payload(candidate: dict) -> dict:
    """Собирает дополнительный meta-payload для переноса кандидата в dataset."""
    payload = {}
    for key in (
        "tmdb_id",
        "imdb_id",
        "description",
        "source",
        "tmdb_score",
        "tmdb_votes",
        "tmdb_popularity",
        "media_type",
        "status",
        "release_date",
        "runtime",
        "type",
        "in_production",
        "number_of_seasons",
        "number_of_episodes",
        "episode_run_time",
        "first_air_date",
        "last_air_date",
        "last_episode_to_air",
        "watch_providers",
    ):
        if key not in candidate:
            continue
        value = candidate.get(key)
        if value is None or value == "":
            continue
        payload[key] = value

    if "description" not in payload:
        overview = candidate.get("overview")
        if overview not in (None, ""):
            payload["description"] = overview

    for key in ("poster_path", "poster_url"):
        value = candidate.get(key)
        if value not in (None, ""):
            payload[key] = value

    raw_scores = {
        key: candidate.get(key)
        for key in ("tmdb_score", "tmdb_votes", "tmdb_popularity")
        if candidate.get(key) not in (None, "")
    }
    if raw_scores:
        payload["raw_scores"] = raw_scores

    return payload


def build_add_meta_payload(resolve_result: dict) -> dict:
    """Собирает meta-payload для ручного добавления записи."""
    payload = {}
    source_values = resolve_result.get("source_values") or {}
    tmdb_data = resolve_result.get("tmdb_data") or {}

    description = source_values.get("description")
    if description not in (None, ""):
        payload["description"] = description

    for key in ("tmdb_id", "imdb_id"):
        value = tmdb_data.get(key) if isinstance(tmdb_data, dict) else None
        if value not in (None, ""):
            payload[key] = value

    if isinstance(tmdb_data, dict):
        localized = tmdb_data.get("localized")
        if isinstance(localized, dict):
            payload["localized"] = deepcopy(localized)

        for key in (
            "poster_path",
            "poster_url",
            "tmdb_score",
            "tmdb_votes",
            "tmdb_popularity",
            "media_type",
            "status",
            "release_date",
            "runtime",
            "type",
            "in_production",
            "number_of_seasons",
            "number_of_episodes",
            "episode_run_time",
            "first_air_date",
            "last_air_date",
            "last_episode_to_air",
            "watch_providers",
        ):
            value = tmdb_data.get(key)
            if value not in (None, ""):
                payload[key] = value

        raw_scores = {
            key: tmdb_data.get(key)
            for key in ("tmdb_score", "tmdb_votes", "tmdb_popularity")
            if tmdb_data.get(key) not in (None, "")
        }
        if raw_scores:
            payload["raw_scores"] = raw_scores

    if payload:
        payload["source"] = "tmdb"

    return payload
