"""Genre extraction for title resolve (TMDb metadata only)."""

from dataset.resolve.helpers import unique_preserve_order


def extract_api_genres(series: dict) -> list:
    """Извлекает список жанров из ответа API или плоского кандидата."""
    genres = []
    for item in series.get("genres", []) or []:
        if isinstance(item, dict) and item.get("name"):
            genres.append(str(item["name"]).strip())
        elif isinstance(item, str):
            genres.append(item.strip())
    return genres


def extract_candidate_fallback_genres(candidate: dict) -> list:
    """Собирает raw-жанры для fallback переноса из genres и genres_tmdb."""
    merged: list[str] = []
    for field_name in ("genres", "genres_tmdb"):
        if field_name == "genres":
            merged.extend(extract_api_genres(candidate))
            continue
        values = candidate.get(field_name) or []
        if isinstance(values, list) is False:
            continue
        for item in values:
            if isinstance(item, dict) and item.get("name"):
                text = str(item["name"]).strip()
            elif isinstance(item, str):
                text = item.strip()
            else:
                continue
            if text != "":
                merged.append(text)
    return unique_preserve_order(merged)


def split_known_genres(genres: list) -> tuple[list, list]:
    """Разделяет жанры на известные и неизвестные подсказки (TMDb labels)."""
    known = []
    for genre in unique_preserve_order(genres):
        text = str(genre or "").strip()
        if text != "":
            known.append(text)
    return known, []


def extract_tmdb_genres(series: dict | None) -> list:
    """Достаёт список жанров из нормализованного TMDb-объекта."""
    if not isinstance(series, dict):
        return []
    for field_name in ("genres_tmdb", "genres"):
        values = series.get(field_name, []) or []
        if values:
            return unique_preserve_order(values)
    return []
