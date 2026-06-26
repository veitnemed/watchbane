"""Read-only helpers for user_score analytics."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import median

from config import constant


SCORE_BUCKETS: tuple[tuple[str, float | None, float | None], ...] = (
    ("10.0", 10.0, None),
    ("9.0-9.9", 9.0, 10.0),
    ("8.0-8.9", 8.0, 9.0),
    ("7.0-7.9", 7.0, 8.0),
    ("6.0-6.9", 6.0, 7.0),
    ("ниже 6.0", None, 6.0),
)


PLOTLY_SCORE_BUCKETS: tuple[tuple[str, float | None, float | None], ...] = (
    ("ниже 6.0", None, 6.0),
    ("6.0-6.9", 6.0, 7.0),
    ("7.0-7.9", 7.0, 8.0),
    ("8.0-8.9", 8.0, 9.0),
    ("9.0-9.9", 9.0, 10.0),
    ("10.0", 10.0, None),
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


def build_score_distribution_chart_rows(records, title_limit: int = 5) -> list[dict]:
    """Build low-to-high score buckets with title examples for interactive charts."""
    items = collect_score_items(records)
    total = len(items)
    rows: list[dict] = []

    for label, lower, upper in PLOTLY_SCORE_BUCKETS:
        bucket_items = [item for item in items if _score_in_bucket(item["score"], lower, upper)]
        titles = [item["title"] for item in bucket_items if item["title"]]
        count = len(bucket_items)
        rows.append(
            {
                "label": label,
                "count": count,
                "percent": 0.0 if total == 0 else round(count * 100 / total, 1),
                "example_titles": titles[:title_limit],
                "extra_count": max(0, len(titles) - title_limit),
            }
        )

    return rows


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


def build_score_count_points(items_or_scores, title_limit: int = 5) -> list[dict]:
    """Build exact user_score frequency points for a scatter/line chart."""
    grouped: dict[float, list[str]] = defaultdict(list)
    for item in _coerce_score_items(items_or_scores):
        grouped[item["score"]].append(item["title"])

    points: list[dict] = []
    for score, titles in grouped.items():
        display_titles = [title for title in titles if title]
        points.append(
            {
                "score": score,
                "count": len(titles),
                "example_titles": display_titles[:title_limit],
                "extra_count": max(0, len(display_titles) - title_limit),
            }
        )

    points.sort(key=lambda point: point["score"])
    return points


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


DATASET_COMPLETENESS_FIELDS: tuple[tuple[str, str], ...] = (
    ("user_score", "Мои оценки"),
    ("year", "Годы"),
    ("genres", "Жанры"),
    ("imdb", "IMDb"),
    ("kp", "КП"),
    ("description", "Описания"),
    ("poster", "Постеры"),
)

DATASET_COMPLETENESS_DISPLAY_KEYS: tuple[str, ...] = (
    "poster",
    "description",
    "imdb",
    "kp",
    "genres",
    "year",
)


def _movie_section(movie: dict, key: str) -> dict:
    section = movie.get(key)
    return section if isinstance(section, dict) else {}


def _clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text != "" else None


def _has_rating_value(value) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _genres_from_movie(movie: dict) -> list[str]:
    for field_name in ("genres_display", "genre_display", "genres", "imdb_genres", "genres_tmdb", "tmdb_genres"):
        value = movie.get(field_name)
        if isinstance(value, list):
            genres = [_clean_text(item) for item in value]
            genres = [genre for genre in genres if genre is not None]
            if genres:
                return genres
        text = _clean_text(value)
        if text is not None:
            return [text]

    genre_section = _movie_section(movie, constant.GENRE_SECTION)
    labels = constant.FIELD_LABELS
    result: list[str] = []
    for feature in constant.GENRE:
        if genre_section.get(feature) != 1:
            continue
        label = _clean_text(labels.get(feature))
        if label is None:
            label = feature.removeprefix("has_").replace("_", " ").title()
        if label not in result:
            result.append(label)
    return result


def _overview_from_movie(movie: dict) -> str | None:
    for field_name in ("overview", "description", "short_description", "shortDescription", "plot"):
        for section in (movie, _movie_section(movie, "main_info")):
            text = _clean_text(section.get(field_name))
            if text is not None:
                return text
    return None


def _poster_fields_from_movie(movie: dict) -> dict:
    poster = _movie_section(movie, "poster")
    poster_url = _clean_text(movie.get("poster_url") or movie.get("posterUrl") or poster.get("url"))
    poster_path = _clean_text(movie.get("poster_path") or movie.get("posterPath") or poster.get("path"))
    poster_src = poster_path or poster_url
    return {
        "poster_url": poster_url,
        "poster_path": poster_path,
        "poster_src": poster_src,
    }


def _completeness_card_from_movie(movie: dict) -> dict:
    main_info = _movie_section(movie, "main_info")
    raw_scores = _movie_section(movie, "raw_scores")
    poster_fields = _poster_fields_from_movie(movie)
    return {
        "user_score": main_info.get("user_score", movie.get("user_score")),
        "year": main_info.get("year", movie.get("year")),
        "genres": _genres_from_movie(movie),
        "imdb_score": raw_scores.get("imdb_score", movie.get("imdb_score")),
        "kp_score": raw_scores.get("kp_score", movie.get("kp_score")),
        "overview": _overview_from_movie(movie),
        **poster_fields,
    }


def _entry_has_user_score(movie: dict, card: dict) -> bool:
    score = card.get("user_score", _movie_section(movie, "main_info").get("user_score", movie.get("user_score")))
    return normalize_score(score) is not None


def _entry_has_year(movie: dict, card: dict) -> bool:
    year = card.get("year", _movie_section(movie, "main_info").get("year", movie.get("year")))
    if year in (None, ""):
        return False
    try:
        return int(year) > 0
    except (TypeError, ValueError):
        return False


def _entry_has_genres(movie: dict, card: dict) -> bool:
    genres = card.get("genres")
    if genres is None:
        genres = _genres_from_movie(movie)
    if isinstance(genres, str):
        return bool(genres.strip())
    if isinstance(genres, list):
        return any(_clean_text(genre) is not None for genre in genres)
    return False


def _entry_has_imdb(movie: dict, card: dict) -> bool:
    value = card.get("imdb_score", _movie_section(movie, "raw_scores").get("imdb_score", movie.get("imdb_score")))
    return _has_rating_value(value)


def _entry_has_kp(movie: dict, card: dict) -> bool:
    value = card.get("kp_score", _movie_section(movie, "raw_scores").get("kp_score", movie.get("kp_score")))
    return _has_rating_value(value)


def _entry_has_description(movie: dict, card: dict) -> bool:
    overview = card.get("overview", _overview_from_movie(movie))
    return overview not in (None, "") and bool(str(overview).strip())


def _entry_has_poster(movie: dict, card: dict) -> bool:
    fields = {
        "poster_url": card.get("poster_url"),
        "poster_path": card.get("poster_path"),
        "poster_src": card.get("poster_src"),
    }
    if all(value in (None, "") for value in fields.values()):
        fields = _poster_fields_from_movie(movie)

    poster_url = _clean_text(fields.get("poster_url"))
    if poster_url is not None:
        return True

    for field_name in ("poster_src", "poster_path"):
        value = _clean_text(fields.get(field_name))
        if value is None:
            continue
        if value.startswith(("http://", "https://")):
            return True
        if Path(value).is_file():
            return True
    return False


_DATASET_COMPLETENESS_CHECKS = {
    "user_score": _entry_has_user_score,
    "year": _entry_has_year,
    "genres": _entry_has_genres,
    "imdb": _entry_has_imdb,
    "kp": _entry_has_kp,
    "description": _entry_has_description,
    "poster": _entry_has_poster,
}


def _build_dataset_completeness_payload(entries: list[tuple[str, dict, dict]]) -> dict:
    total = len(entries)
    counts = {key: 0 for key, _label in DATASET_COMPLETENESS_FIELDS}
    for _key, movie, card in entries:
        if isinstance(movie, dict) is False:
            continue
        display_card = card if isinstance(card, dict) else _completeness_card_from_movie(movie)
        for field_key, checker in _DATASET_COMPLETENESS_CHECKS.items():
            if checker(movie, display_card):
                counts[field_key] += 1

    items: list[dict] = []
    percents: list[float] = []
    for field_key, label in DATASET_COMPLETENESS_FIELDS:
        count = counts[field_key]
        percent = 0.0 if total == 0 else round(count * 100 / total, 1)
        percents.append(percent)
        items.append(
            {
                "key": field_key,
                "label": label,
                "count": count,
                "total": total,
                "percent": percent,
            }
        )

    overall_percent = 0.0 if len(percents) == 0 else round(sum(percents) / len(percents), 1)
    return {
        "total": total,
        "overall_percent": overall_percent,
        "items": items,
    }


def build_dataset_completeness_from_entries(entries: list[tuple[str, dict, dict]]) -> dict:
    """Build watched dataset completeness stats from GUI entries."""
    normalized: list[tuple[str, dict, dict]] = []
    for entry in entries:
        if isinstance(entry, tuple) and len(entry) == 3:
            key, movie, card = entry
            if isinstance(movie, dict):
                normalized.append((str(key), movie, card if isinstance(card, dict) else {}))
    return _build_dataset_completeness_payload(normalized)


def build_dataset_completeness(records) -> dict:
    """Build watched dataset completeness stats from raw dataset records."""
    if isinstance(records, dict):
        iterable = records.items()
    else:
        iterable = enumerate(records)

    entries: list[tuple[str, dict, dict]] = []
    for key, movie in iterable:
        if isinstance(movie, dict) is False:
            continue
        entries.append((str(key), movie, _completeness_card_from_movie(movie)))
    return _build_dataset_completeness_payload(entries)


def summarize_dataset_completeness(completeness: dict) -> dict:
    """Build compact GUI status for dataset completeness indicator."""
    total = int(completeness.get("total") or 0)
    overall_percent = float(completeness.get("overall_percent") or 0.0)
    items = [item for item in completeness.get("items", []) if isinstance(item, dict)]
    issues = [item for item in items if float(item.get("percent") or 0) < 100.0]

    if total == 0:
        return {
            "is_ok": False,
            "overall_percent": 0.0,
            "issues": issues,
            "status_text": "Нет записей в watched-базе",
        }

    is_ok = len(issues) == 0
    if is_ok:
        status_text = "Dataset заполнен полностью"
    else:
        status_text = f"Полнота dataset — {overall_percent:.0f}%"

    return {
        "is_ok": is_ok,
        "overall_percent": overall_percent,
        "issues": issues,
        "status_text": status_text,
    }


def build_score_analytics(records, entries=None) -> dict:
    """Build all read-only score analytics for watched records."""
    score_items = collect_score_items(records)
    scores = [item["score"] for item in score_items]
    summary = build_score_summary(scores)
    distribution = build_score_distribution(scores)
    chart_distribution = build_score_distribution_chart_rows(records)
    score_count_points = build_score_count_points(score_items)
    dense_scores = build_dense_score_rows(score_items)
    dataset_completeness = (
        build_dataset_completeness_from_entries(entries)
        if entries is not None
        else build_dataset_completeness(records)
    )
    return {
        "scores": scores,
        "score_items": score_items,
        "summary": summary,
        "distribution": distribution,
        "chart_distribution": chart_distribution,
        "score_count_points": score_count_points,
        "dense_scores": dense_scores,
        "insights": build_score_insights(summary, distribution, dense_scores),
        "dataset_completeness": dataset_completeness,
    }
