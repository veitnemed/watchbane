"""Genre label extraction from watched records."""

from config import constant


def _clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text != "" else None


def genres_from_movie(movie: dict) -> list[str]:
    """Return display genre labels for one watched movie dict."""
    for field_name in ("genres_display", "genre_display", "genres", "imdb_genres", "genres_tmdb", "tmdb_genres"):
        value = movie.get(field_name)
        if isinstance(value, list):
            genres = [_clean_text(item) for item in value]
            genres = [genre for genre in genres if genre is not None]
            if genres:
                return genres
        text = _clean_text(value)
        if text is not None:
            return [text]

    genre_section = movie.get(constant.GENRE_SECTION)
    if not isinstance(genre_section, dict):
        genre_section = {}
    labels = constant.FIELD_LABELS
    result: list[str] = []
    for feature in constant.GENRE:
        if genre_section.get(feature) != 1:
            continue
        label = _clean_text(labels.get(feature))
        if label is None:
            label = feature.removeprefix("has_").replace("_", " ").title()
        if label not in result:
            result.append(label)
    return result
