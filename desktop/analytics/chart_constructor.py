"""Pure data builders for the analytics chart constructor."""

from __future__ import annotations

from collections import defaultdict
from math import floor

SOURCE_WATCHED = "watched"
SOURCE_CANDIDATE_POOL = "candidate_pool"

CHART_BAR = "bar"
CHART_FUNCTION = "function"

X_USER_SCORE = "user_score"
X_YEAR = "year"
X_GENRE = "genre"
X_COUNTRY = "country"
X_TMDB_SCORE = "tmdb_score"
X_TMDB_VOTES = "tmdb_votes"
X_TMDB_POPULARITY = "tmdb_popularity"

Y_COUNT = "count"
Y_AVG_USER_SCORE = "avg_user_score"
Y_AVG_TMDB_SCORE = "avg_tmdb_score"
Y_AVG_FINAL_SCORE = "avg_final_score"

SUPPORTED_STEPS = (1.0, 0.5)

X_LABELS = {
    X_USER_SCORE: "Оценка пользователя",
    X_YEAR: "Год",
    X_GENRE: "Жанр",
    X_COUNTRY: "Страна",
    X_TMDB_SCORE: "TMDb рейтинг",
    X_TMDB_VOTES: "TMDb голоса",
    X_TMDB_POPULARITY: "TMDb popularity",
}

Y_LABELS = {
    Y_COUNT: "Количество тайтлов",
    Y_AVG_USER_SCORE: "Средняя пользовательская оценка",
    Y_AVG_TMDB_SCORE: "Средний TMDb рейтинг",
    Y_AVG_FINAL_SCORE: "Средний итоговый score",
}

NUMERIC_SCORE_AXES = {X_USER_SCORE, X_TMDB_SCORE}

VOTE_BUCKETS = (
    (0, 0, "0"),
    (1, 9, "1-9"),
    (10, 49, "10-49"),
    (50, 99, "50-99"),
    (100, 499, "100-499"),
    (500, 999, "500-999"),
    (1000, None, "1000+"),
)

POPULARITY_BUCKETS = (
    (0, 4.999, "0-5"),
    (5, 9.999, "5-10"),
    (10, 24.999, "10-25"),
    (25, 49.999, "25-50"),
    (50, 99.999, "50-100"),
    (100, None, "100+"),
)


def _card_from_entry(entry) -> dict:
    if isinstance(entry, tuple) and len(entry) >= 3 and isinstance(entry[2], dict):
        return entry[2]
    if isinstance(entry, dict):
        return entry
    return {}


def _normalize_source_items(source: str, watched_entries=None, candidate_entries=None) -> list[dict]:
    raw_items = candidate_entries if source == SOURCE_CANDIDATE_POOL else watched_entries
    return [_card_from_entry(item) for item in (raw_items or [])]


def _to_float(value) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_score(value) -> float | None:
    score = _to_float(value)
    if score is None or score < 0 or score > 10:
        return None
    return score


def _coerce_year(value) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if year > 0 else None


def _normalize_step(step) -> float:
    try:
        normalized = float(step)
    except (TypeError, ValueError):
        return 1.0
    return normalized if normalized in SUPPORTED_STEPS else 1.0


def _bucket_label(value: float, step: float) -> str:
    if step == 1.0:
        return str(int(value))
    if value in (0.0, 10.0):
        return str(int(value))
    return f"{value:.1f}"


def _bucket_values(step: float) -> list[float]:
    count = int(round(10 / step))
    return [round(index * step, 1) for index in range(count + 1)]


def _bucket_score(score: float, step: float) -> float:
    if score == 10:
        return 10.0
    return round(floor(score / step) * step, 1)


def _text_values(value) -> list[str]:
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = []

    result: list[str] = []
    for item in values:
        if isinstance(item, dict):
            text = str(item.get("name") or item.get("label") or item.get("title") or "").strip()
        else:
            text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _first_text_item(item: dict, *field_names: str) -> str | None:
    for field_name in field_names:
        value = item.get(field_name)
        if isinstance(value, (list, tuple, set)):
            values = _text_values(value)
            if values:
                return values[0]
        text = str(value or "").strip()
        if text:
            return text
    return None


def _candidate_genres(item: dict) -> list[str]:
    for field_name in ("genres_display", "genres", "genre_keys", "genres_tmdb", "tmdb_genres"):
        values = _text_values(item.get(field_name))
        if values:
            return values
    return []


def _countries(item: dict) -> list[str]:
    display = _first_text_item(item, "country_display", "country")
    if display is not None:
        return [display]
    for field_name in ("countries", "country_codes", "origin_country", "production_countries"):
        values = _text_values(item.get(field_name))
        if values:
            return values
    return []


def _final_score_for_average(value) -> float | None:
    score = _to_float(value)
    if score is None:
        return None
    if score <= 1:
        score *= 100
    return max(0.0, min(100.0, score))


def _metric_value(item: dict, y_axis: str) -> float | None:
    if y_axis == Y_AVG_USER_SCORE:
        return _coerce_score(item.get("user_score"))
    if y_axis == Y_AVG_TMDB_SCORE:
        return _coerce_score(item.get("tmdb_score"))
    if y_axis == Y_AVG_FINAL_SCORE:
        return _final_score_for_average(item.get("final_score"))
    return None


def _bucket_from_ranges(value: float, ranges) -> tuple[int, str] | None:
    for index, (lower, upper, label) in enumerate(ranges):
        if value < lower:
            continue
        if upper is None or value <= upper:
            return index, label
    return None


def _x_groups_for_item(item: dict, x_axis: str, step: float) -> list[tuple[float | int | str, str]]:
    if x_axis == X_USER_SCORE:
        score = _coerce_score(item.get("user_score"))
        if score is None:
            return []
        bucket = _bucket_score(score, step)
        return [(bucket, _bucket_label(bucket, step))]

    if x_axis == X_TMDB_SCORE:
        score = _coerce_score(item.get("tmdb_score"))
        if score is None:
            return []
        bucket = _bucket_score(score, step)
        return [(bucket, _bucket_label(bucket, step))]

    if x_axis == X_YEAR:
        year = _coerce_year(item.get("year"))
        return [] if year is None else [(year, str(year))]

    if x_axis == X_GENRE:
        return [(genre.casefold(), genre) for genre in _candidate_genres(item)]

    if x_axis == X_COUNTRY:
        return [(country.casefold(), country) for country in _countries(item)]

    if x_axis == X_TMDB_VOTES:
        value = _to_float(item.get("tmdb_votes"))
        if value is None or value < 0:
            return []
        bucket = _bucket_from_ranges(value, VOTE_BUCKETS)
        return [] if bucket is None else [bucket]

    if x_axis == X_TMDB_POPULARITY:
        value = _to_float(item.get("tmdb_popularity"))
        if value is None or value < 0:
            return []
        bucket = _bucket_from_ranges(value, POPULARITY_BUCKETS)
        return [] if bucket is None else [bucket]

    return []


def _empty_score_rows(step: float) -> list[dict]:
    return [
        {
            "label": _bucket_label(value, step),
            "value": 0,
            "count": 0,
            "percent": 0.0,
            "example_titles": [],
            "extra_count": 0,
        }
        for value in _bucket_values(step)
    ]


def _sort_key(row: dict):
    key = row.get("sort_key")
    if isinstance(key, (int, float)):
        return (0, key)
    return (1, str(row.get("label") or "").casefold())


def build_user_score_distribution(entries, *, step=1.0) -> list[dict]:
    """Return 0..10 user_score count buckets for watched entries."""
    normalized_step = _normalize_step(step)
    rows = build_grouped_chart_rows(
        [_card_from_entry(entry) for entry in entries or []],
        x_axis=X_USER_SCORE,
        y_axis=Y_COUNT,
        step=normalized_step,
        include_empty_score_buckets=True,
    )
    return rows or _empty_score_rows(normalized_step)


def build_grouped_chart_rows(
    items: list[dict],
    *,
    x_axis: str,
    y_axis: str,
    step=1.0,
    include_empty_score_buckets: bool = False,
) -> list[dict]:
    """Group source items by X axis and aggregate the selected Y metric."""
    normalized_step = _normalize_step(step)
    groups: dict[float | int | str, dict] = {}

    if include_empty_score_buckets and x_axis in NUMERIC_SCORE_AXES:
        groups.update(
            {
                value: {
                    "sort_key": value,
                    "label": _bucket_label(value, normalized_step),
                    "count": 0,
                    "metric_values": [],
                    "example_titles": [],
                }
                for value in _bucket_values(normalized_step)
            }
        )

    for item in items:
        for group_key, label in _x_groups_for_item(item, x_axis, normalized_step):
            group = groups.setdefault(
                group_key,
                {
                    "sort_key": group_key,
                    "label": label,
                    "count": 0,
                    "metric_values": [],
                    "example_titles": [],
                },
            )
            group["count"] += 1
            metric = _metric_value(item, y_axis)
            if metric is not None:
                group["metric_values"].append(metric)
            title = str(item.get("title") or "").strip()
            if title and len(group["example_titles"]) < 3:
                group["example_titles"].append(title)

    total_count = sum(group["count"] for group in groups.values())
    rows: list[dict] = []
    for group in groups.values():
        metric_values = group["metric_values"]
        value = group["count"] if y_axis == Y_COUNT else None
        if y_axis != Y_COUNT and metric_values:
            value = round(sum(metric_values) / len(metric_values), 2)
        if y_axis != Y_COUNT and value is None:
            value = 0
        rows.append(
            {
                "label": group["label"],
                "value": value,
                "count": group["count"],
                "percent": 0.0 if total_count == 0 else round(group["count"] * 100 / total_count, 1),
                "example_titles": group["example_titles"],
                "extra_count": max(0, group["count"] - len(group["example_titles"])),
                "sort_key": group["sort_key"],
            }
        )

    return sorted(rows, key=_sort_key)


def _validate_combination(source: str, x_axis: str, y_axis: str) -> str | None:
    if source == SOURCE_CANDIDATE_POOL and (x_axis == X_USER_SCORE or y_axis == Y_AVG_USER_SCORE):
        return "В candidate pool нет пользовательских оценок"
    return None


def build_chart_constructor_data(
    *,
    source: str,
    x_axis: str,
    y_axis: str,
    chart_type: str = CHART_BAR,
    step=1.0,
    watched_entries=None,
    candidate_entries=None,
) -> dict:
    """Build chart rows or a user-facing unsupported-combination message."""
    message = _validate_combination(source, x_axis, y_axis)
    if message is not None:
        return {"ok": False, "message": message, "rows": []}

    items = _normalize_source_items(source, watched_entries=watched_entries, candidate_entries=candidate_entries)
    include_empty = x_axis == X_USER_SCORE and y_axis == Y_COUNT
    rows = build_grouped_chart_rows(
        items,
        x_axis=x_axis,
        y_axis=y_axis,
        step=step,
        include_empty_score_buckets=include_empty,
    )

    return {
        "ok": True,
        "message": "",
        "rows": rows,
        "chart_type": chart_type if chart_type in {CHART_BAR, CHART_FUNCTION} else CHART_BAR,
        "x_label": X_LABELS.get(x_axis, str(x_axis)),
        "y_label": Y_LABELS.get(y_axis, str(y_axis)),
    }
