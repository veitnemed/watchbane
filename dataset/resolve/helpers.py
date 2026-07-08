"""Small shared helpers for title resolve."""


def unique_preserve_order(values: list) -> list:
    """Убирает дубли, сохраняя исходный порядок элементов."""
    result = []
    for value in values:
        text = str(value or "").strip()
        if text == "" or text in result:
            continue
        result.append(text)
    return result


def add_title_value(values: list, value) -> None:
    text = str(value or "").strip()
    if text and text not in values:
        values.append(text)


def extract_candidate_imdb_id(candidate: dict | None) -> str | None:
    """Достаёт IMDb id из SQL/KP/TMDb кандидата в едином виде."""
    if not isinstance(candidate, dict):
        return None

    for key in ("imdb_id", "imdbId", "imdbID", "tconst"):
        value = str(candidate.get(key) or "").strip()
        if value:
            return value.casefold()

    for nested_key in ("externalId", "external_ids"):
        nested = candidate.get(nested_key)
        if not isinstance(nested, dict):
            continue
        for key in ("imdb", "imdb_id", "imdbId", "imdbID"):
            value = str(nested.get(key) or "").strip()
            if value:
                return value.casefold()

    return None


def extract_candidate_year(candidate: dict | None) -> int | None:
    """Достаёт год из кандидата, если он представлен числом."""
    if not isinstance(candidate, dict):
        return None

    for key in ("year", "startYear"):
        value = candidate.get(key)
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    for key in ("first_air_date", "release_date"):
        value = str(candidate.get(key) or "").strip()
        if len(value) >= 4 and value[:4].isdigit():
            return int(value[:4])
    return None
