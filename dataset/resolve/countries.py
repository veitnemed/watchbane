"""Country extraction helpers for resolve and stats."""

from __future__ import annotations

from candidates.models import country_reference
from candidates.sources.tmdb import country_options as tmdb_country_options


def extract_country_value(source: dict | None) -> str:
    """Returns a display country string from API/SQL/candidate data."""
    if not isinstance(source, dict):
        return ""
    for field_name in (
        "country_display",
        "country",
        "countries",
        "title_region_countries",
        "tmdb_production_countries",
        "tmdb_origin_countries",
        "origin_country",
    ):
        value = source.get(field_name)
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, dict):
                    text = str(item.get("name") or item.get("iso_3166_1") or "").strip()
                else:
                    text = str(item or "").strip()
                if text and text not in parts:
                    parts.append(text)
            if parts:
                return ", ".join(parts)
            continue
        text = str(value or "").strip()
        if text:
            return text
    return ""


def country_value_to_iso2(value: str) -> str | None:
    """Map one raw country label/code to ISO-2 when alias is known."""
    return country_reference.country_value_to_iso2(value)


def country_labels_by_code() -> dict[str, str]:
    return tmdb_country_options.COUNTRY_NAMES_RU_BY_CODE
