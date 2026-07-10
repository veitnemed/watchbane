"""Intro copy and pool stats text for the candidate Filters tab."""

from __future__ import annotations

from desktop.i18n import tr
from desktop.candidates.session import CandidateSearchSession


def series_count_phrase(count: int) -> str:
    """Return a short Russian phrase like «42 сериала»."""
    value = max(0, int(count))
    remainder_100 = value % 100
    remainder_10 = value % 10
    if 11 <= remainder_100 <= 14:
        key = "candidates.filters.series.many"
    elif remainder_10 == 1:
        key = "candidates.filters.series.one"
    elif 2 <= remainder_10 <= 4:
        key = "candidates.filters.series.some"
    else:
        key = "candidates.filters.series.many"
    return tr(key, count=value)


def format_pool_stats_user(stats: dict) -> str:
    unique_total = int(stats.get("unique_total", stats.get("storage_total", 0)) or 0)
    ready_total = int(stats.get("ready_total", 0) or 0)
    incomplete_total = int(stats.get("incomplete_total", 0) or 0)
    incomplete_phrase = (
        tr("candidates.filters.pool.incomplete.none")
        if incomplete_total == 0
        else tr("candidates.filters.pool.incomplete.some", count=incomplete_total)
    )
    return tr(
        "candidates.filters.pool.stats",
        count_phrase=series_count_phrase(unique_total),
        ready_total=ready_total,
        incomplete_phrase=incomplete_phrase,
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
            tr("candidates.filters.empty.lead"),
            tr("candidates.filters.empty.stats"),
            False,
        )

    lead = tr("candidates.filters.intro.lead")
    stats = overview.get("stats") or {}
    unique_total = int(stats.get("unique_total", stats.get("storage_total", 0)) or 0)

    if result_ok is False and result_count == 0:
        return (
            lead,
            tr("candidates.filters.no_results.stats"),
            True,
        )

    if result_count is not None and result_count > 0:
        return (
            lead,
            tr(
                "candidates.filters.matched.stats",
                count_phrase=series_count_phrase(result_count),
                total=unique_total,
            ),
            True,
        )

    if session.has_results and result_count is None:
        filtered = int(session.filtered_count or 0)
        if filtered > 0:
            return (
                lead,
                tr(
                    "candidates.filters.matched.stats",
                    count_phrase=series_count_phrase(filtered),
                    total=unique_total,
                ),
                True,
            )
        return (
            lead,
            tr("candidates.filters.no_results.stats"),
            True,
        )

    return lead, format_pool_stats_user(stats), True
