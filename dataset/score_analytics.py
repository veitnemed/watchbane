"""Read-only helpers for user_score analytics."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from statistics import median


SCORE_BUCKETS: tuple[tuple[str, float | None, float | None], ...] = (
    ("10.0", 10.0, None),
    ("9.0-9.9", 9.0, 10.0),
    ("8.0-8.9", 8.0, 9.0),
    ("7.0-7.9", 7.0, 8.0),
    ("6.0-6.9", 6.0, 7.0),
    ("ниже 6.0", None, 6.0),
)


def normalize_score(score) -> float | None:
    """Return a one-decimal score or None when score is missing/invalid."""
    if score is None:
        return None
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    if value < 0 or value > 10:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def collect_user_scores(records) -> list[float]:
    """Collect valid user_score values from dataset dict or movie iterable."""
    return [item["score"] for item in collect_score_items(records)]


def collect_score_items(records) -> list[dict]:
    """Collect valid score items with display titles from dataset records."""
    if isinstance(records, dict):
        iterable = records.items()
    else:
        iterable = enumerate(records)

    items: list[dict] = []
    for key, movie in iterable:
        if isinstance(movie, dict) is False:
            continue
        main_info = movie.get("main_info", {})
        if isinstance(main_info, dict) is False:
            continue
        score = normalize_score(main_info.get("user_score"))
        if score is not None:
            title = str(main_info.get("title") or key).strip()
            items.append({"title": title, "score": score})
    return items


def build_score_summary(scores: list[float]) -> dict:
    """Build summary statistics for valid user scores."""
    if len(scores) == 0:
        return {
            "count": 0,
            "average": None,
            "median": None,
            "minimum": None,
            "maximum": None,
        }

    sorted_scores = sorted(scores)
    return {
        "count": len(sorted_scores),
        "average": normalize_score(sum(sorted_scores) / len(sorted_scores)),
        "median": normalize_score(median(sorted_scores)),
        "minimum": min(sorted_scores),
        "maximum": max(sorted_scores),
    }


def _score_in_bucket(score: float, lower: float | None, upper: float | None) -> bool:
    if lower is not None and upper is None:
        return score >= lower
    if lower is None and upper is not None:
        return score < upper
    if lower is not None and upper is not None:
        return lower <= score < upper
    return False


def build_score_distribution(scores: list[float]) -> list[dict]:
    """Build fixed bucket distribution for valid user scores."""
    total = len(scores)
    distribution: list[dict] = []
    for label, lower, upper in SCORE_BUCKETS:
        count = sum(1 for score in scores if _score_in_bucket(score, lower, upper))
        percent = 0.0 if total == 0 else round(count * 100 / total, 1)
        distribution.append(
            {
                "label": label,
                "count": count,
                "percent": percent,
            }
        )
    return distribution


def _coerce_score_items(items_or_scores) -> list[dict]:
    items: list[dict] = []
    for item in items_or_scores:
        if isinstance(item, dict):
            score = normalize_score(item.get("score"))
            if score is None:
                continue
            title = str(item.get("title") or "").strip()
            items.append({"title": title, "score": score})
            continue

        score = normalize_score(item)
        if score is not None:
            items.append({"title": "", "score": score})
    return items


def build_dense_score_rows(items_or_scores, limit: int = 5, title_limit: int = 5) -> list[dict]:
    """Return the most repeated one-decimal scores with example titles."""
    grouped: dict[float, list[str]] = defaultdict(list)
    for item in _coerce_score_items(items_or_scores):
        grouped[item["score"]].append(item["title"])

    rows = [
        {
            "score": score,
            "count": len(titles),
            "titles": [title for title in titles[:title_limit] if title],
            "extra_count": max(0, len(titles) - title_limit),
        }
        for score, titles in grouped.items()
    ]
    rows.sort(key=lambda row: (-row["count"], -row["score"]))
    return rows[:limit]


def build_score_insights(summary: dict, distribution: list[dict], dense_scores: list[dict]) -> list[str]:
    """Build short read-only insight lines from score analytics."""
    if summary["count"] == 0:
        return ["Пока нет оценок для аналитики."]

    insights: list[str] = []
    non_empty_buckets = [item for item in distribution if item["count"] > 0]
    if non_empty_buckets:
        dominant = max(non_empty_buckets, key=lambda item: (item["count"], item["percent"]))
        insights.append(
            f"Больше всего оценок в диапазоне {dominant['label']}: "
            f"{dominant['count']} · {dominant['percent']:.1f}%."
        )

    if dense_scores:
        top_dense = dense_scores[0]
        insights.append(
            f"Самая частая одинаковая оценка: {top_dense['score']:.1f} — "
            f"{top_dense['count']} тайтлов."
        )

    high_count = sum(item["count"] for item in distribution if item["label"] in ("10.0", "9.0-9.9"))
    insights.append(f"Очень высоких оценок 9.0+ сейчас: {high_count}.")
    return insights


def build_score_analytics(records) -> dict:
    """Build all read-only score analytics for watched records."""
    score_items = collect_score_items(records)
    scores = [item["score"] for item in score_items]
    summary = build_score_summary(scores)
    distribution = build_score_distribution(scores)
    dense_scores = build_dense_score_rows(score_items)
    return {
        "scores": scores,
        "score_items": score_items,
        "summary": summary,
        "distribution": distribution,
        "dense_scores": dense_scores,
        "insights": build_score_insights(summary, distribution, dense_scores),
    }
