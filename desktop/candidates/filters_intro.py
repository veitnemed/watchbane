"""Intro copy and pool stats text for the candidate Filters tab."""

from __future__ import annotations

from desktop.candidates.session import CandidateSearchSession


def series_count_phrase(count: int) -> str:
    """Return a short Russian phrase like «42 сериала»."""
    value = max(0, int(count))
    remainder_100 = value % 100
    remainder_10 = value % 10
    if 11 <= remainder_100 <= 14:
        suffix = "сериалов"
    elif remainder_10 == 1:
        suffix = "сериал"
    elif 2 <= remainder_10 <= 4:
        suffix = "сериала"
    else:
        suffix = "сериалов"
    return f"{value} {suffix}"


def format_pool_stats_user(stats: dict) -> str:
    unique_total = int(stats.get("unique_total", stats.get("storage_total", 0)) or 0)
    ready_total = int(stats.get("ready_total", 0) or 0)
    incomplete_total = int(stats.get("incomplete_total", 0) or 0)
    return (
        f"В базе {series_count_phrase(unique_total)}"
        f" · {ready_total} с полной TMDb metadata"
        f" · {incomplete_total} требуют metadata диагностики"
    )


def build_intro_copy(
    session: CandidateSearchSession,
    overview: dict,
    *,
    result_count: int | None = None,
    result_ok: bool | None = None,
) -> tuple[str, str, bool]:
    """Return lead text, stats text and whether apply button should be enabled."""
    if overview.get("is_empty"):
        return (
            "Список кандидатов пока пуст.",
            "Сначала добавьте сериалы через консоль: сбор кандидатов или импорт.",
            False,
        )

    lead = (
        "Настройте условия ниже и нажмите «Применить фильтры». "
        "Список откроется на вкладке «Кандидаты»."
    )
    stats = overview.get("stats") or {}
    unique_total = int(stats.get("unique_total", stats.get("storage_total", 0)) or 0)

    if result_ok is False and result_count == 0:
        return (
            lead,
            "По выбранным условиям ничего не найдено. "
            "Ослабьте фильтры или разрешите неполные карточки.",
            True,
        )

    if result_count is not None and result_count > 0:
        return (
            lead,
            f"Подходит {series_count_phrase(result_count)} из {unique_total}.",
            True,
        )

    if session.has_results and result_count is None:
        filtered = int(session.filtered_count or 0)
        if filtered > 0:
            return (
                lead,
                f"Подходит {series_count_phrase(filtered)} из {unique_total}.",
                True,
            )
        return (
            lead,
            "По выбранным условиям ничего не найдено. "
            "Ослабьте фильтры или разрешите неполные карточки.",
            True,
        )

    return lead, format_pool_stats_user(stats), True
