"""Desktop helpers for safe watched-record deletion."""

from __future__ import annotations

from dataset import service
from desktop.shared.detail.presenters import format_user_score_display

DELETE_CONFIRMATION_TEXT = "DELETE"


def is_delete_confirmation_valid(text: str) -> bool:
    """Return True when confirmation text exactly matches DELETE."""
    return str(text or "").strip() == DELETE_CONFIRMATION_TEXT


def load_delete_preview(dataset_key: str, data: dict | None = None) -> dict | None:
    """Build read-only delete preview for a watched dataset key."""
    return service.build_watched_delete_preview(dataset_key, data=data)


def format_delete_preview_lines(preview: dict) -> list[str]:
    """Format delete preview fields for the desktop confirmation dialog."""
    lines = [
        f"Название: {preview.get('title') or '—'}",
        f"Год: {preview.get('year') if preview.get('year') not in (None, '') else '—'}",
        f"Моя оценка: {format_user_score_display(preview.get('user_score'))}",
    ]

    tmdb_score = preview.get("tmdb_score")
    if tmdb_score not in (None, ""):
        lines.append(f"TMDb: {tmdb_score}")

    lines.append(f"Meta: {'есть' if preview.get('has_meta') else 'нет'}")
    lines.append(f"Poster-cache: {'есть' if preview.get('has_poster_cache') else 'нет'}")

    poster_local_path = preview.get("poster_local_path")
    if poster_local_path not in (None, ""):
        lines.append(f"Локальный постер: {poster_local_path}")

    return lines


def execute_watched_delete(dataset_key: str) -> dict:
    """Delete one watched record through the existing safe delete service."""
    return service.delete_watched_record(dataset_key)


def format_delete_status_message(result: dict) -> str:
    """Short GUI status text after delete attempt."""
    if result.get("ok"):
        return "Запись удалена"
    message = result.get("message")
    if message:
        return str(message)
    return "Не удалось удалить запись"
