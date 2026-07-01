"""Format pool stats and filter defaults for UI display."""

from __future__ import annotations


def _format_optional_filter_value(value) -> str:
    if value in (None, ""):
        return "не важно"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if len(value) > 0 else "не важно"
    return str(value)


def format_pool_stats_summary(stats: dict) -> str:
    """Формирует однострочную сводку pool stats для меню."""
    unique_total = stats.get("unique_total", stats.get("storage_total", 0))
    parts = [
        f"уникальных: {unique_total}",
        f"ready: {stats['ready_total']}",
        f"incomplete: {stats['incomplete_total']}",
    ]
    if stats.get("watched_total", 0) > 0:
        parts.append(f"watched: {stats['watched_total']}")
    duplicate_entries = int(stats.get("duplicate_entries") or 0)
    if duplicate_entries > 0:
        parts.append(f"в JSON: {stats['raw_total']} (+{duplicate_entries} дублей)")
    similar_duplicate_total = int(stats.get("similar_duplicate_total") or 0)
    if similar_duplicate_total > 0:
        parts.append(f"похожих: {similar_duplicate_total}")
    cross_year_duplicate_total = int(stats.get("cross_year_duplicate_total") or 0)
    if cross_year_duplicate_total > 0:
        parts.append(f"cross-year: {cross_year_duplicate_total}")
    return " | ".join(parts)


def format_pool_stats_lines(stats: dict) -> list[str]:
    """Формирует многострочную сводку pool stats для экранов pool/top."""
    unique_total = stats.get("unique_total", stats.get("storage_total", 0))
    lines = [
        f"Уникальных кандидатов: {unique_total}",
        f"Ready: {stats['ready_total']} | Incomplete: {stats['incomplete_total']}",
    ]
    if stats.get("watched_total", 0) > 0:
        lines.append(
            f"Watched in pool: {stats['watched_total']} "
            f"(после save active: {stats['active_total']})"
        )
    duplicate_entries = int(stats.get("duplicate_entries") or 0)
    if stats.get("criteria_name") is None and duplicate_entries > 0:
        lines.append(
            f"Записей в JSON: {stats['raw_total']} "
            f"(лишних exact-дублей: {duplicate_entries})"
        )
    similar_duplicate_total = int(stats.get("similar_duplicate_total") or 0)
    if stats.get("criteria_name") is None and similar_duplicate_total > 0:
        lines.append(f"Похожих дублей можно слить: {similar_duplicate_total}")
    cross_year_duplicate_total = int(stats.get("cross_year_duplicate_total") or 0)
    if stats.get("criteria_name") is None and cross_year_duplicate_total > 0:
        lines.append(f"Cross-year дублей можно слить: {cross_year_duplicate_total}")
    return lines


def format_search_filter_default_lines(defaults: dict) -> list[str]:
    """Формирует краткую сводку defaults для экрана поиска."""
    return [
        f"country: {_format_optional_filter_value(defaults.get('country'))}",
        (
            f"year: {_format_optional_filter_value(defaults.get('year_min'))}"
            f"..{_format_optional_filter_value(defaults.get('year_max'))}"
        ),
        f"include genres (saved pool / KP-IMDb-TMDb data): {_format_optional_filter_value(defaults.get('include_genres'))}",
        f"exclude genres (saved pool / KP-IMDb-TMDb data): {_format_optional_filter_value(defaults.get('exclude_genres'))}",
        f"min KP: {_format_optional_filter_value(defaults.get('min_kp_score'))}",
        f"min KP votes: {_format_optional_filter_value(defaults.get('min_kp_votes'))}",
        f"min IMDb: {_format_optional_filter_value(defaults.get('min_imdb_score'))}",
        f"min IMDb votes: {_format_optional_filter_value(defaults.get('min_imdb_votes'))}",
    ]


def format_candidate_description(candidate: dict, limit: int = 200) -> str:
    """Returns a short saved description without network requests."""
    for field_name in ("description", "overview", "tmdb_overview", "plot", "short_description"):
        text = str(candidate.get(field_name) or "").strip()
        if text:
            text = " ".join(text.split())
            if len(text) <= limit:
                return text
            return text[: max(0, limit - 3)].rstrip() + "..."
    return "нет данных"
