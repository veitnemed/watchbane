"""Genre label extraction from watched records (TMDb metadata)."""


def _clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text != "" else None


def genres_from_movie(movie: dict) -> list[str]:
    """Return display genre labels for one watched movie dict."""
    for field_name in ("genres_display", "genre_display", "genres", "genres_tmdb", "tmdb_genres"):
        value = movie.get(field_name)
        if isinstance(value, list):
            genres = [_clean_text(item) for item in value]
            genres = [genre for genre in genres if genre is not None]
            if genres:
                return genres
        text = _clean_text(value)
        if text is not None:
            return [text]
    return []
