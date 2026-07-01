"""Card-facing formatters for detail views (no Qt, no watched persistence)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from desktop.theme import COLOR_IMDB_ACCENT, COLOR_KP_ACCENT


def _round_one_decimal(value) -> str:
    """Round to one decimal place (half up), e.g. 8.25 -> 8.3."""
    rounded = Decimal(str(float(value))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded:.1f}"


def format_user_score_display(user_score) -> str:
    """Format user score for detail card display."""
    if user_score is None:
        return "—"
    try:
        return _round_one_decimal(user_score)
    except (TypeError, ValueError):
        return "—"


def format_rating_score_display(score) -> str | None:
    """Format external rating for pill badges."""
    if score is None:
        return None
    try:
        return _round_one_decimal(score)
    except (TypeError, ValueError):
        return None


def format_year_pill(year) -> str:
    return str(year)


def _rating_indicator_item(source: str, score: str, label: str) -> dict:
    return {
        "kind": "rating_indicator",
        "source": source,
        "label": label,
        "score": score,
        "accent": COLOR_IMDB_ACCENT if source == "imdb" else COLOR_KP_ACCENT,
    }


def format_imdb_pill(score: str) -> dict:
    return _rating_indicator_item("imdb", score, "IMDb")


def format_kp_pill(score: str) -> dict:
    return _rating_indicator_item("kp", score, "КП")


def build_meta_pill_items(card: dict) -> list[dict]:
    """Build IMDb/KP pill display items for the detail card."""
    items: list[dict] = []
    imdb = format_rating_score_display(card.get("imdb_score"))
    if imdb is not None:
        items.append(format_imdb_pill(imdb))

    kp = format_rating_score_display(card.get("kp_score"))
    if kp is not None:
        items.append(format_kp_pill(kp))

    return items


def build_meta_pill_labels(card: dict) -> list[str]:
    """Plain-text pill labels (legacy helper for tests)."""
    labels: list[str] = []
    year = card.get("year")
    if year not in (None, ""):
        labels.append(str(year))

    imdb = format_rating_score_display(card.get("imdb_score"))
    if imdb is not None:
        labels.append(f"IMDb {imdb}")

    kp = format_rating_score_display(card.get("kp_score"))
    if kp is not None:
        labels.append(f"КП {kp}")

    return labels


def format_genre_pill_label(genre: str) -> str:
    return str(genre).strip()


def build_genre_pill_labels(card: dict) -> list[str]:
    """Build genre pill labels for the detail card."""
    genres = card.get("genres") or []
    return [format_genre_pill_label(genre) for genre in genres if str(genre).strip()]


def get_country_display(card: dict) -> str | None:
    """Return country label for detail card or None when missing."""
    country = card.get("country")
    if country in (None, ""):
        return None
    text = str(country).strip()
    return text if text else None


def build_detail_info_pill_labels(card: dict) -> list[str]:
    """Build lower info pills shown near genres."""
    labels: list[str] = []
    year = card.get("year")
    if year not in (None, ""):
        labels.append(format_year_pill(year))
    labels.extend(build_genre_pill_labels(card))
    return labels


def has_overview_text(card: dict) -> bool:
    """Return True when the card has non-empty overview text."""
    overview = card.get("overview")
    if overview in (None, ""):
        return False
    return bool(str(overview).strip())


def get_overview_display(card: dict) -> str:
    """Return overview text for detail card."""
    return str(card.get("overview", "")).strip()
