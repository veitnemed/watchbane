"""Map runtime candidate filters to indexed SQLite columns on candidate_records."""

from __future__ import annotations

from dataset.models.media_type import normalize_media_type


def _criteria_value(criteria: dict, *names, default=None):
    for name in names:
        if name in criteria:
            return criteria.get(name)
    return default


def _coerce_number(value):
    if value in (None, ""):
        return None
    try:
        return float(value) if "." in str(value) else int(value)
    except (TypeError, ValueError):
        return None


def build_structural_sql_filters(filters: dict | None) -> tuple[list[str], list[object]]:
    """Return SQL WHERE fragments and params for indexed candidate_records columns."""
    criteria = dict(filters or {})
    clauses: list[str] = []
    params: list[object] = []

    media_type = _criteria_value(criteria, "media_type", "type")
    if media_type not in (None, ""):
        clauses.append("cr.media_type = ?")
        params.append(normalize_media_type(media_type))

    min_year = _coerce_number(
        _criteria_value(criteria, "year_from", "min_year", "year_min")
    )
    if min_year is not None:
        clauses.append("cr.year >= ?")
        params.append(int(min_year))

    max_year = _coerce_number(
        _criteria_value(criteria, "year_to", "max_year", "year_max")
    )
    if max_year is not None:
        clauses.append("cr.year <= ?")
        params.append(int(max_year))

    min_tmdb_score = _coerce_number(
        _criteria_value(criteria, "min_tmdb_score", "min_tmdb")
    )
    if min_tmdb_score is not None:
        clauses.append("cr.tmdb_score >= ?")
        params.append(float(min_tmdb_score))

    min_final_score = _coerce_number(_criteria_value(criteria, "min_final_score"))
    if min_final_score is not None:
        clauses.append("cr.final_score >= ?")
        params.append(float(min_final_score))

    criteria_name = _criteria_value(criteria, "criteria_name")
    if criteria_name not in (None, ""):
        clauses.append("cr.criteria_name = ?")
        params.append(str(criteria_name))

    source = _criteria_value(criteria, "source")
    if source not in (None, ""):
        clauses.append("cr.source = ?")
        params.append(str(source))

    return clauses, params
