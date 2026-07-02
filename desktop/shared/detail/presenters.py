"""Card-facing formatters for detail views (no Qt, no watched persistence)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from desktop.theme import COLOR_ACCENT

SCORE_RING_RED = "#ef4444"
SCORE_RING_AMBER = "#f59e0b"
SCORE_RING_GREEN = "#22c55e"


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


def normalize_final_score(value) -> float:
    """Normalize final score to 0..1 for radial progress display."""
    if value in (None, ""):
        return 0.0
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score > 1:
        score = score / 100.0
    return max(0.0, min(1.0, score))


def format_final_score(value) -> str:
    """Format final score as a compact 0..100 UI label."""
    if value in (None, ""):
        return "Итог —"
    try:
        normalized = normalize_final_score(value)
    except (TypeError, ValueError):
        return "Итог —"
    rounded = Decimal(str(normalized * 100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"Итог {int(rounded)}"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    text = str(color).lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _blend_color(start: str, end: str, amount: float) -> str:
    start_rgb = _hex_to_rgb(start)
    end_rgb = _hex_to_rgb(end)
    clamped = max(0.0, min(1.0, amount))
    return _rgb_to_hex(
        tuple(
            int(round(start_rgb[index] + (end_rgb[index] - start_rgb[index]) * clamped))
            for index in range(3)
        )
    )


def score_ring_color_for_final_score(value) -> str:
    """Return red-to-green ring color for final score quality."""
    progress = normalize_final_score(value)
    if progress <= 0.5:
        return _blend_color(SCORE_RING_RED, SCORE_RING_AMBER, progress / 0.5)
    return _blend_color(SCORE_RING_AMBER, SCORE_RING_GREEN, (progress - 0.5) / 0.5)


def format_year_pill(year) -> str:
    return str(year)


def build_score_ring_item(card: dict) -> dict | None:
    """Build the TMDb-only score ring item for the detail card."""
    has_tmdb_score = card.get("tmdb_score") not in (None, "")
    has_final_score = card.get("final_score") not in (None, "")
    if has_tmdb_score is False and has_final_score is False:
        return None

    display_value = format_rating_score_display(card.get("tmdb_score")) if has_tmdb_score else None
    return {
        "kind": "score_ring",
        "source": "tmdb",
        "display_value": display_value or "—",
        "display_label": "TMDb",
        "ring_progress": normalize_final_score(card.get("final_score")),
        "footer_label": format_final_score(card.get("final_score")),
        "accent": score_ring_color_for_final_score(card.get("final_score")),
    }


def format_imdb_pill(score: str) -> dict:
    return {
        "kind": "rating_indicator",
        "source": "imdb",
        "label": "IMDb",
        "score": score,
        "accent": COLOR_ACCENT,
    }


def format_kp_pill(score: str) -> dict:
    return {
        "kind": "rating_indicator",
        "source": "kp",
        "label": "КП",
        "score": score,
        "accent": COLOR_ACCENT,
    }


def format_tmdb_pill(score: str) -> dict:
    return {
        "kind": "score_ring",
        "source": "tmdb",
        "display_value": score,
        "display_label": "TMDb",
        "ring_progress": 0.0,
        "footer_label": "Итог —",
        "accent": COLOR_ACCENT,
    }


def build_meta_pill_items(card: dict) -> list[dict]:
    """Build TMDb-only score ring display items for the detail card."""
    items: list[dict] = []
    score_ring = build_score_ring_item(card)
    if score_ring is not None:
        items.append(score_ring)
    return items


def build_meta_pill_labels(card: dict) -> list[str]:
    """Plain-text pill labels (legacy helper for tests)."""
    labels: list[str] = []
    year = card.get("year")
    if year not in (None, ""):
        labels.append(str(year))

    tmdb = format_rating_score_display(card.get("tmdb_score"))
    if tmdb is not None:
        labels.append(f"TMDb {tmdb}")

    if card.get("final_score") not in (None, ""):
        labels.append(format_final_score(card.get("final_score")))

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
