"""Build meta payloads for watched add and candidate transfer."""


def build_candidate_meta_payload(candidate: dict) -> dict:
    """Собирает дополнительный meta-payload для переноса кандидата в dataset."""
    payload = {}
    for key in ("tmdb_id", "imdb_id", "kp_id", "description", "source"):
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

    return payload


def build_add_meta_payload(resolve_result: dict) -> dict:
    """Собирает meta-payload для ручного добавления записи."""
    payload = {}
    source_values = resolve_result.get("source_values") or {}
    sources = resolve_result.get("sources") or {}
    tmdb_data = resolve_result.get("tmdb_data") or {}
    api_data = resolve_result.get("api_data") or {}

    description = source_values.get("description")
    if description not in (None, ""):
        payload["description"] = description

    for key in ("tmdb_id", "imdb_id", "kp_id"):
        value = tmdb_data.get(key) if isinstance(tmdb_data, dict) else None
        if value in (None, "") and isinstance(api_data, dict):
            value = api_data.get(key)
        if value not in (None, ""):
            payload[key] = value

    if isinstance(tmdb_data, dict):
        for key in ("poster_path", "poster_url"):
            value = tmdb_data.get(key)
            if value not in (None, ""):
                payload[key] = value

    source = sources.get("description")
    if source not in (None, ""):
        payload["source"] = source
    elif isinstance(tmdb_data, dict) and tmdb_data.get("source"):
        payload["source"] = tmdb_data.get("source")

    return payload
