"""Poster path resolution and shell open helpers (no Qt)."""

from __future__ import annotations

from pathlib import Path


def _local_path(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.startswith(("http://", "https://")):
        return None
    return text


def _nested_poster_value(record: dict, field: str) -> str | None:
    poster = record.get("poster")
    if isinstance(poster, dict):
        return poster.get(field)
    return None


def _first_existing_local_path(*candidates: str | None) -> str | None:
    for candidate in candidates:
        if candidate is None:
            continue
        path = Path(candidate)
        if path.is_file():
            return str(path)
    return None


def _cached_preview_path(poster_url) -> str | None:
    if poster_url in (None, ""):
        return None
    from posters.download_images import local_preview_poster_path_if_cached

    preview_path = local_preview_poster_path_if_cached(str(poster_url))
    if preview_path in (None, ""):
        return None
    path = Path(preview_path)
    if path.is_file():
        return str(path)
    return None


def resolve_local_poster_path_from_record(
    record: dict,
    *,
    card: dict | None = None,
    title: str | None = None,
    year=None,
) -> str | None:
    """Return a local filesystem poster path from generic record fields. Never uses network."""
    display_card = card or {}
    local = _first_existing_local_path(
        _local_path(display_card.get("poster_path")),
        _local_path(display_card.get("poster_src")),
        _local_path(record.get("poster_path")),
        _local_path(record.get("poster_src")),
        _local_path(_nested_poster_value(record, "path")),
        _local_path(_nested_poster_value(record, "poster_path")),
    )
    if local is not None:
        return local

    poster_url = display_card.get("poster_url") or record.get("poster_url")
    cached = _cached_preview_path(poster_url)
    if cached is not None:
        return cached

    if title in (None, ""):
        main_info = record.get("main_info") if isinstance(record.get("main_info"), dict) else {}
        title = main_info.get("title") or record.get("title") or display_card.get("title")
        if year is None:
            year = display_card.get("year", main_info.get("year", record.get("year")))
    if title not in (None, ""):
        from posters.cache import default_local_poster_path, lookup_poster_cache_entry

        cache_entry = lookup_poster_cache_entry(str(title), year)
        cache_url = cache_entry.get("poster_url") if isinstance(cache_entry, dict) else None
        if poster_url not in (None, "") and cache_url not in (None, "", poster_url):
            return None
        default_path = default_local_poster_path(str(title), year)
        if default_path not in (None, ""):
            return default_path
    return None


def resolve_local_poster_path(movie: dict, card: dict | None = None) -> str | None:
    """Return a local filesystem poster path for a watched movie record."""
    from dataset.read_models.watched import prepare_card_for_display

    display_card = card if card is not None else prepare_card_for_display(movie)
    main_info = movie.get("main_info") if isinstance(movie.get("main_info"), dict) else {}
    title = main_info.get("title") or movie.get("title") or display_card.get("title")
    year = display_card.get("year", main_info.get("year", movie.get("year")))
    return resolve_local_poster_path_from_record(
        movie,
        card=display_card,
        title=title,
        year=year,
    )


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
