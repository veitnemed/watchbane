"""Merge watched popularity rows with candidate pool filter options."""

from candidates.models import country_schema


def merge_genre_popularity_with_pool(
    dataset_rows: list[dict],
    pool_labels: list[str],
) -> list[dict]:
    """Keep dataset order (popular first), append pool-only genres with count=0."""
    merged = list(dataset_rows)
    seen = {str(row.get("label") or "").casefold() for row in merged}
    extras: list[dict] = []
    for label in pool_labels:
        text = str(label or "").strip()
        if text == "" or text.casefold() in seen:
            continue
        seen.add(text.casefold())
        extras.append({"label": text, "count": 0})
    extras.sort(key=lambda row: str(row.get("label") or "").casefold())
    merged.extend(extras)
    return merged


def merge_country_popularity_with_pool(
    dataset_rows: list[dict],
    pool_rows: list[dict],
) -> list[dict]:
    """Keep dataset order (popular first), append pool-only countries with count=0."""
    merged = list(dataset_rows)
    seen = {str(row.get("code") or "").strip().upper() for row in merged if str(row.get("code") or "").strip()}
    extras: list[dict] = []
    for row in pool_rows:
        code = str(row.get("code") or "").strip().upper()
        if code == "" or code in seen:
            continue
        label = str(row.get("label") or "").strip()
        if label == "" or label.upper() == code:
            label = country_schema.build_country_display([code]) or ""
        if label == "":
            continue
        seen.add(code)
        extras.append({"code": code, "label": label, "count": 0})
    extras.sort(key=lambda row: str(row.get("label") or "").casefold())
    merged.extend(extras)
    return merged
