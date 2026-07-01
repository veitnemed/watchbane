"""Read-only popularity aggregates from watched dataset."""

from __future__ import annotations

from collections import Counter

from dataset.genres.extract import genres_from_movie
from dataset.resolve.countries import (
    country_labels_by_code,
    country_value_to_iso2,
    extract_country_value,
)


def _sort_popularity_rows(rows: list[dict], *, label_key: str = "label") -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (-int(row.get("count") or 0), str(row.get(label_key) or "").casefold()),
    )


def build_dataset_genre_popularity(data: dict) -> list[dict]:
    """Count watched titles per genre label; most popular first."""
    counter: Counter[str] = Counter()
    if not isinstance(data, dict):
        return []

    for movie in data.values():
        if not isinstance(movie, dict):
            continue
        seen_in_title: set[str] = set()
        for genre in genres_from_movie(movie):
            label = str(genre or "").strip()
            if label == "" or label in seen_in_title:
                continue
            seen_in_title.add(label)
            counter[label] += 1

    rows = [{"label": label, "count": count} for label, count in counter.items()]
    return _sort_popularity_rows(rows)


def _country_parts(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if text == "":
        return []
    parts = [part.strip() for part in text.replace(";", ",").split(",")]
    return [part for part in parts if part]


def build_dataset_country_popularity(data: dict) -> list[dict]:
    """Count watched titles per ISO country; most popular first."""
    labels_by_code = country_labels_by_code()
    counter: Counter[str] = Counter()

    if not isinstance(data, dict):
        return []

    for movie in data.values():
        if not isinstance(movie, dict):
            continue
        merged = dict(movie)
        main_info = movie.get("main_info")
        if isinstance(main_info, dict):
            merged.update(main_info)
        raw = extract_country_value(merged)
        parts = _country_parts(raw)
        if not parts:
            continue

        seen_in_title: set[str] = set()
        for part in parts:
            iso2 = country_value_to_iso2(part)
            if iso2 is None or iso2 in seen_in_title:
                continue
            seen_in_title.add(iso2)
            counter[iso2] += 1

    rows = [
        {
            "code": code,
            "label": labels_by_code.get(code, code),
            "count": count,
        }
        for code, count in counter.items()
    ]
    return _sort_popularity_rows(rows)
