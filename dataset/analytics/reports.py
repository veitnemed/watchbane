"""Genre, year, and rating-gap analytics reports."""

from __future__ import annotations

from collections import defaultdict

from dataset.analytics.helpers import collect_analytics_entry_items
from dataset.analytics.scores import normalize_score

RATING_STRONG_GAP = 1.5
GENRE_COUNT_CHART_LIMIT = 15
TMDB_DELTA_LIST_PREVIEW_LIMIT = 10
TMDB_DELTA_LIST_LIMIT = 20
TMDB_DELTA_CHART_LIMIT = TMDB_DELTA_LIST_LIMIT
ANALYTICS_LIST_LIMIT = 12
GENRE_COUNT_TITLE_LIMIT = 3

SUSPICIOUS_HIGH_PUBLIC = 7.5
SUSPICIOUS_LOW_USER = 5.5
SUSPICIOUS_LOW_PUBLIC = 5.5
SUSPICIOUS_HIGH_USER = 8.0


def build_genre_count_rows(
    entries: list[tuple[str, dict, dict]],
    *,
    limit: int = GENRE_COUNT_CHART_LIMIT,
    title_limit: int = GENRE_COUNT_TITLE_LIMIT,
) -> list[dict]:
    """Count watched titles per genre label."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in collect_analytics_entry_items(entries):
        for genre in item["genres"]:
            grouped[genre].append(item["title"])

    rows = [
        {
            "label": genre,
            "count": len(titles),
            "example_titles": titles[:title_limit],
            "extra_count": max(0, len(titles) - title_limit),
        }
        for genre, titles in grouped.items()
    ]
    rows.sort(key=lambda row: (-int(row["count"]), str(row["label"]).casefold()))
    return rows[:limit]


def build_year_average_points(entries: list[tuple[str, dict, dict]]) -> list[dict]:
    """Average user_score grouped by release year."""
    grouped: dict[int, list[float]] = defaultdict(list)
    for item in collect_analytics_entry_items(entries):
        user_score = item.get("user_score")
        if user_score is None:
            continue
        try:
            year = int(item.get("year"))
        except (TypeError, ValueError):
            continue
        if year <= 0:
            continue
        grouped[year].append(float(user_score))

    points: list[dict] = []
    for year in sorted(grouped):
        scores = grouped[year]
        average = normalize_score(sum(scores) / len(scores))
        points.append({"year": year, "average": average, "count": len(scores)})
    return points


def _format_rating_gap_delta(delta: float) -> str:
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta:.1f}"


def format_rating_gap_line(row: dict) -> str:
    """Format one public-rating gap row for analytics lists."""
    year = row.get("year")
    year_text = f" ({year})" if year not in (None, "") else ""
    return (
        f"{row['title']}{year_text} · моя {float(row['user_score']):.1f} · "
        f"{row['source_label']} {float(row['external_score']):.1f} · "
        f"{_format_rating_gap_delta(float(row['delta']))}"
    )


def build_rating_gap_lists(
    entries: list[tuple[str, dict, dict]],
    *,
    gap: float = RATING_STRONG_GAP,
    limit: int = ANALYTICS_LIST_LIMIT,
) -> dict:
    """Split titles where user score differs strongly from TMDb."""
    higher: list[dict] = []
    lower: list[dict] = []
    for item in collect_analytics_entry_items(entries):
        user_score = item.get("user_score")
        if user_score is None:
            continue
        external_score = item.get("tmdb_score")
        if external_score is None:
            continue
        delta = round(float(user_score) - float(external_score), 1)
        row = {
            "title": item["title"],
            "year": item.get("year"),
            "user_score": user_score,
            "source": "tmdb",
            "source_label": "TMDb",
            "external_score": external_score,
            "delta": delta,
        }
        if delta >= gap:
            higher.append(row)
        elif delta <= -gap:
            lower.append(row)

    higher.sort(key=lambda row: (-float(row["delta"]), str(row["title"]).casefold()))
    lower.sort(key=lambda row: (float(row["delta"]), str(row["title"]).casefold()))
    return {
        "higher_than_public": higher[:limit],
        "lower_than_public": lower[:limit],
        "higher_extra_count": max(0, len(higher) - limit),
        "lower_extra_count": max(0, len(lower) - limit),
    }


def build_tmdb_delta_chart_rows(
    entries: list[tuple[str, dict, dict]],
    *,
    limit: int = TMDB_DELTA_LIST_LIMIT,
) -> dict:
    """Build ranked rows for user_score minus TMDb per watched title."""
    rows: list[dict] = []
    for item in collect_analytics_entry_items(entries):
        user_score = item.get("user_score")
        tmdb_score = item.get("tmdb_score")
        if user_score is None or tmdb_score is None:
            continue
        delta = round(float(user_score) - float(tmdb_score), 1)
        rows.append(
            {
                "title": item["title"],
                "year": item.get("year"),
                "user_score": user_score,
                "tmdb_score": tmdb_score,
                "delta": delta,
            }
        )

    rows.sort(
        key=lambda row: (
            -abs(float(row["delta"])),
            -float(row["delta"]),
            str(row["title"]).casefold(),
        )
    )
    return {
        "rows": rows[:limit],
        "extra_count": max(0, len(rows) - limit),
    }


def format_tmdb_delta_line(row: dict) -> str:
    """Format one TMDb delta row for analytics text lists."""
    year = row.get("year")
    year_text = f" ({year})" if year not in (None, "") else ""
    delta = float(row["delta"])
    sign = "+" if delta > 0 else ""
    return (
        f"{row['title']}{year_text} · моя {float(row['user_score']):.1f} · "
        f"TMDb {float(row['tmdb_score']):.1f} · {sign}{delta:.1f}"
    )


def format_suspicious_rating_line(row: dict) -> str:
    """Format one suspicious rating row for analytics lists."""
    year = row.get("year")
    year_text = f" ({year})" if year not in (None, "") else ""
    user_score = row.get("user_score")
    score_text = f" · моя {float(user_score):.1f}" if user_score is not None else ""
    return f"{row['title']}{year_text}{score_text} · {row['reason']}"


def build_suspicious_ratings(
    entries: list[tuple[str, dict, dict]],
    *,
    limit: int = ANALYTICS_LIST_LIMIT,
) -> dict:
    """Find watched titles with suspicious user/public rating patterns."""
    rows: list[dict] = []
    for item in collect_analytics_entry_items(entries):
        user_score = item.get("user_score")
        if user_score is None:
            continue

        reasons: list[str] = []
        external_score = item.get("tmdb_score")
        if external_score is not None:
            if float(external_score) >= SUSPICIOUS_HIGH_PUBLIC and float(user_score) <= SUSPICIOUS_LOW_USER:
                reasons.append("TMDb высокий, моя низкая")
            if float(external_score) <= SUSPICIOUS_LOW_PUBLIC and float(user_score) >= SUSPICIOUS_HIGH_USER:
                reasons.append("TMDb низкий, моя высокая")

        if item.get("has_overview") is False:
            reasons.append("нет описания")

        if len(reasons) == 0:
            continue

        rows.append(
            {
                "title": item["title"],
                "year": item.get("year"),
                "user_score": user_score,
                "reason": reasons[0],
                "reasons": reasons,
            }
        )

    rows.sort(key=lambda row: str(row["title"]).casefold())
    return {
        "items": rows[:limit],
        "extra_count": max(0, len(rows) - limit),
    }
