"""Canonical country codes and display labels for candidate-pool records."""

from __future__ import annotations

from typing import Any

from candidates.models import country_reference


_COUNTRY_SOURCE_FIELDS = (
    "tmdb_country_codes",
    "tmdb_origin_countries",
    "countries",
    "tmdb_production_countries",
    "kp_country",
)


def _iter_raw_countries(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        text = values.strip()
        return [text] if text else []
    if isinstance(values, (list, tuple, set)):
        result: list[str] = []
        for item in values:
            text = str(item or "").strip()
            if text != "":
                result.append(text)
        return result
    text = str(values).strip()
    return [text] if text != "" else []


def country_value_to_iso2(value: str) -> str | None:
    """Maps one raw country label/code to ISO-2 when alias is known."""
    return country_reference.country_value_to_iso2(value)


def normalize_country_filter(value: str | None) -> str | None:
    """Normalizes user/runtime country filter to ISO-2 when alias is known."""
    text = str(value or "").strip()
    if text == "":
        return None
    return country_value_to_iso2(text)


def normalize_country_filter_list(values) -> list[str]:
    """Normalizes user/runtime country filters to ordered unique ISO-2 codes."""
    codes: list[str] = []
    seen: set[str] = set()

    def add_raw(raw_value: str) -> None:
        text = str(raw_value or "").strip()
        if text == "":
            return
        iso2 = country_value_to_iso2(text)
        if iso2 is None or iso2 in seen:
            return
        seen.add(iso2)
        codes.append(iso2)

    if values is None:
        return []
    if isinstance(values, str):
        text = values.strip()
        if text == "":
            return []
        if "," in text:
            for part in text.split(","):
                add_raw(part)
        else:
            add_raw(text)
        return codes
    if isinstance(values, (list, tuple, set)):
        for item in values:
            if isinstance(item, str) and "," in item:
                for part in item.split(","):
                    add_raw(part)
            else:
                add_raw(str(item or ""))
        return codes
    add_raw(str(values))
    return codes


def country_codes_match_any(candidate_codes: list[str], required_codes: list[str]) -> bool:
    """True when candidate country_codes intersect required ISO-2 filters."""
    if len(required_codes) == 0:
        return True
    return len(set(candidate_codes) & set(required_codes)) > 0


def build_country_codes(candidate: dict) -> list[str]:
    """Builds ordered unique ISO-2 country codes from available candidate fields."""
    codes: list[str] = []
    seen: set[str] = set()
    for field_name in _COUNTRY_SOURCE_FIELDS:
        for raw_value in _iter_raw_countries(candidate.get(field_name)):
            iso2 = country_value_to_iso2(raw_value)
            if iso2 is None or iso2 in seen:
                continue
            seen.add(iso2)
            codes.append(iso2)
    return codes


def build_country_display(country_codes: list[str], language: str = "ru") -> str | None:
    """Maps primary ISO-2 country code to a display label."""
    labels = (
        country_reference.ENGLISH_COUNTRY_NAME_BY_ISO2
        if str(language or "").strip().casefold() == "en"
        else country_reference.COUNTRY_NAME_BY_ISO2
    )
    for iso2 in country_codes:
        label = labels.get(iso2)
        if label:
            return label
    return None


def candidate_country_for_display(candidate: dict, language: str = "ru") -> str:
    """Returns UI country label, preferring country_display with legacy fallback."""
    display = str(candidate.get("country_display") or "").strip()
    if display != "":
        codes = normalize_country_filter_list(display)
        return build_country_display(codes, language=language) or display

    codes = build_country_codes(candidate)
    normalized_display = build_country_display(codes, language=language)
    if normalized_display is not None:
        return normalized_display

    raw_values = _iter_raw_countries(candidate.get("countries"))
    if len(raw_values) == 0:
        raw_values = _iter_raw_countries(candidate.get("country"))
    if len(raw_values) == 0:
        return ""
    codes = normalize_country_filter_list(raw_values)
    normalized_display = build_country_display(codes, language=language)
    if normalized_display is not None:
        return normalized_display
    return ", ".join(raw_values)
