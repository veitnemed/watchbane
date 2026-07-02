"""Human-readable delete preview/report formatters."""


def format_watched_delete_preview(preview: dict) -> str:
    """Format delete preview for console output."""
    lines = [
        "Preview удаления:",
        f"  Название: {preview.get('title')}",
        f"  Год: {preview.get('year')}",
        f"  Моя оценка: {preview.get('user_score')}",
    ]

    tmdb_score = preview.get("tmdb_score")
    if tmdb_score not in (None, ""):
        lines.append(f"  TMDb: {tmdb_score}")

    lines.append(f"  Meta: {'да' if preview.get('has_meta') else 'нет'}")
    lines.append(f"  Poster-cache: {'да' if preview.get('has_poster_cache') else 'нет'}")
    if preview.get("poster_local_path"):
        lines.append(f"  Poster local_path: {preview.get('poster_local_path')}")
    return "\n".join(lines)


def format_watched_delete_report(result: dict) -> str:
    """Format delete result report for console output."""
    lines = [
        f"Удалено из dataset: {result.get('deleted_dataset', 0)}",
        f"Удалено из meta: {result.get('deleted_meta', 0)}",
        f"Удалено из poster-cache: {result.get('deleted_poster_cache', 0)}",
        f"Удалено локальных постеров: {result.get('deleted_poster_file', 0)}",
        f"Dataset теперь: {result.get('dataset_count', 0)} записей",
        "Backup:",
    ]
    backups = result.get("backups") or []
    if len(backups) == 0:
        lines.append("  —")
    else:
        for backup_path in backups:
            lines.append(f"  - {backup_path}")

    message = result.get("message")
    if message:
        lines.insert(0, str(message))
    return "\n".join(lines)
