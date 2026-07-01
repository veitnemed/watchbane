"""Read-only formatters for the Settings/Tools tab."""

from __future__ import annotations

KP_RETRY_BATCH_SIZE = 10


def format_pool_stats_block(stats_view: dict) -> list[str]:
    lines = list(stats_view.get("lines") or [])
    summary = str(stats_view.get("summary") or "").strip()
    if summary and summary not in lines:
        lines.append(summary)
    return lines


def format_dedupe_preview_lines(title_view: dict, suspicious_view: dict) -> list[str]:
    lines: list[str] = []
    summary = title_view.get("summary") or {}
    group_count = int(summary.get("group_count") or 0)
    extra_entries = int(summary.get("extra_entries") or 0)
    if group_count > 0:
        lines.append(f"Групп дублей по названию: {group_count} · лишних записей: {extra_entries}")
    else:
        lines.append("Групп дублей по названию не найдено.")

    suspicious_count = int(suspicious_view.get("count") or 0)
    if suspicious_count > 0:
        lines.append(f"Подозрительных пар: {suspicious_count}")
    return lines


def format_retry_kp_preview_line(retry_view: dict) -> str:
    count = int(retry_view.get("incomplete_count") or 0)
    if count <= 0:
        return "Неполных карточек для KP retry нет."
    batch = min(KP_RETRY_BATCH_SIZE, count)
    return f"Неполных карточек: {count}. Следующий запуск обработает до {batch}."


def format_clean_duplicates_status(result: dict) -> str:
    if not result.get("changed"):
        return "Дубли в pool не найдены, изменений нет."
    removed_exact = int(result.get("removed_exact") or 0)
    removed_similar = int(result.get("removed_similar") or 0)
    removed_cross = int(result.get("removed_cross_year") or 0)
    unique_total = int(result.get("unique_total") or 0)
    return (
        f"Pool обновлён: уникальных {unique_total}. "
        f"Удалено exact {removed_exact}, похожих {removed_similar}, cross-year {removed_cross}."
    )


def format_retry_kp_status(result: dict) -> str:
    stats = result.get("stats") or {}
    attempted = int(stats.get("attempted") or result.get("attempted") or 0)
    if attempted <= 0:
        return "KP retry: нечего обрабатывать."
    kp_found = int(stats.get("kp_found") or 0)
    became_complete = int(stats.get("became_complete") or 0)
    remaining = int(stats.get("remaining_incomplete") or 0)
    return (
        f"KP retry: обработано {attempted}, найдено KP {kp_found}, "
        f"стало complete {became_complete}, осталось incomplete {remaining}."
    )


def format_clear_pool_status(result: dict) -> str:
    cleared = int(result.get("cleared") or 0)
    if cleared <= 0:
        return "Pool уже был пуст."
    return f"Pool очищен: удалено {cleared} записей."


def format_tmdb_files_empty_hint() -> str:
    return "TMDb result JSON в data/exports/candidate_pool не найдены."


def format_tmdb_import_preview(preview: dict) -> str:
    if preview.get("ok") is False:
        error = preview.get("error") or "неизвестная ошибка"
        return f"Не удалось прочитать файл: {error}"

    path = preview.get("result_path")
    file_name = path.name if hasattr(path, "name") else str(path)
    count = int(preview.get("candidate_count") or 0)
    criteria = str(preview.get("default_criteria_name") or "—")
    return (
        f"Файл: {file_name}\n"
        f"Кандидатов в файле: {count}\n"
        f"criteria_name: {criteria}\n"
        "Будет добавлено/обновлено в общий pool после дедупликации."
    )


def format_tmdb_import_status(import_result: dict) -> str:
    if import_result.get("ok") is False:
        return f"Импорт не выполнен: {import_result.get('error') or 'неизвестная ошибка'}"

    stats = import_result.get("stats") or {}
    skipped_watched = stats.get("skipped_watched", stats.get("watched_skipped", 0))
    skipped_duplicates = stats.get("skipped_duplicates", stats.get("duplicates", 0))
    pool_after = stats.get("pool_size_after", stats.get("pool_size", 0))
    return (
        f"Импорт завершён: прочитано {stats.get('read', 0)}, "
        f"добавлено {stats.get('added', 0)}, обновлено {stats.get('updated', 0)}, "
        f"пропущено watched {skipped_watched}, дублей {skipped_duplicates}, "
        f"ошибок {stats.get('errors', 0)}. Pool: {pool_after}."
    )
