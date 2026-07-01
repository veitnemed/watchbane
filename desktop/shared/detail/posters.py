"""Poster path resolution and shell open helpers (no Qt)."""

from __future__ import annotations

from pathlib import Path

from web.export import build_watched_movie_card


def _local_path(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.startswith(("http://", "https://")):
        return None
    return text


def _nested_poster_value(movie: dict, field: str) -> str | None:
    poster = movie.get("poster")
    if isinstance(poster, dict):
        return poster.get(field)
    return None


def resolve_local_poster_path(movie: dict, card: dict | None = None) -> str | None:
    """Return a local filesystem poster path when available. Never uses network."""
    display_card = card if card is not None else build_watched_movie_card(movie)
    candidates: list[str | None] = [
        display_card.get("poster_path"),
        _local_path(display_card.get("poster_src")),
        _local_path(movie.get("poster_src")),
        _local_path(movie.get("poster_path")),
        _local_path(_nested_poster_value(movie, "path")),
        _local_path(_nested_poster_value(movie, "poster_path")),
    ]

    for candidate in candidates:
        if candidate is None:
            continue
        path = Path(candidate)
        if path.is_file():
            return str(path)

    poster_url = display_card.get("poster_url") or movie.get("poster_url")
    if poster_url not in (None, ""):
        from posters.download_images import local_preview_poster_path_if_cached

        preview_path = local_preview_poster_path_if_cached(str(poster_url))
        if preview_path not in (None, ""):
            path = Path(preview_path)
            if path.is_file():
                return str(path)

    main_info = movie.get("main_info") if isinstance(movie.get("main_info"), dict) else {}
    title = display_card.get("title") or main_info.get("title") or movie.get("title")
    year = display_card.get("year", main_info.get("year", movie.get("year")))
    if title not in (None, ""):
        from posters.cache import default_local_poster_path

        default_path = default_local_poster_path(str(title), year)
        if default_path not in (None, ""):
            return default_path
    return None


def get_poster_cache_directory() -> str:
    """Return the default poster-cache directory path."""
    from posters.cache import DEFAULT_POSTER_CACHE_DIR

    return str(DEFAULT_POSTER_CACHE_DIR)


def format_poster_path_display(path: str | None, *, max_len: int = 44) -> str:
    """Build a compact read-only poster path line for the detail card."""
    if path is None:
        return "Локальный файл не найден"
    text = str(path)
    if len(text) <= max_len:
        return text
    head = max(8, max_len // 2 - 1)
    tail = max(8, max_len - head - 1)
    return f"{text[:head]}…{text[-tail:]}"


def open_path_in_shell(path: str) -> tuple[bool, str | None]:
    """Open a local file or folder with the OS default handler."""
    target = Path(path)
    if not target.exists():
        return False, f"Путь не найден: {path}"
    try:
        from storage.files import open_file

        open_file(str(target))
        return True, None
    except OSError as error:
        return False, str(error)
