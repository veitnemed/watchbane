"""Card-facing formatters for detail views (no Qt, no watched persistence)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from desktop.theme import COLOR_ACCENT, COLOR_ACCENT_HOVER
from candidates.scoring.rating_confidence import candidate_rating_confidence, has_unknown_rating
from candidates.scoring.recommendation_strength import resolve_recommendation_strength
from dataset.models.user_rating import UserRating, normalize_user_rating
from desktop.i18n import tr


def _round_one_decimal(value) -> str:
    """Round to one decimal place (half up), e.g. 8.25 -> 8.3."""
    rounded = Decimal(str(float(value))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded:.1f}"


def format_user_score_display(user_score) -> str:
    """Format user reaction as a localized label."""
    rating = normalize_user_rating(user_score)
    keys = {
        int(UserRating.NOT_FOR_ME): "user_rating.not_for_me",
        int(UserRating.OK): "user_rating.ok",
        int(UserRating.TOP): "user_rating.top",
    }
    return tr(keys[rating]) if rating in keys else "—"


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
    if 1 < score <= 10:
        score = score / 10.0
    elif score > 10:
        score = score / 100.0
    return round(max(0.0, min(1.0, score)), 4)


def normalize_tmdb_score(value) -> float:
    """Normalize TMDb rating from 0..10 to 0..1 for the visible TMDb ring."""
    if value in (None, ""):
        return 0.0
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(1.0, score / 10.0)), 4)


def format_final_score(value) -> str:
    key = resolve_recommendation_strength(value)
    return f"{tr('recommendation.strength.label')}: {tr(f'recommendation.strength.{key}')}"


def format_final_score_quality_label(value, rating_confidence: str = "known") -> str:
    key = resolve_recommendation_strength(value, rating_confidence=rating_confidence)
    return tr(f"recommendation.strength.{key}")


def final_score_to_stars(value) -> float | None:
    """Convert final score to a compact 0..5 star value in 0.5 steps."""
    if value in (None, ""):
        return None
    normalized = normalize_final_score(value)
    if normalized <= 0:
        return 0.0
    rounded_tens = (
        (Decimal(str(normalized * 100)) / Decimal("10"))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        * Decimal("10")
    )
    stars = float(rounded_tens / Decimal("20"))
    return max(0.0, min(5.0, stars))


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


def _score_ring_color_for_progress(progress: float) -> str:
    """Return a cyan-to-teal ring color for normalized 0..1 progress."""
    return _blend_color(COLOR_ACCENT, COLOR_ACCENT_HOVER, progress)


def score_ring_color_for_final_score(value) -> str:
    """Return theme ring color for final score quality."""
    return _score_ring_color_for_progress(normalize_final_score(value))


def score_ring_color_for_tmdb_score(value) -> str:
    """Return theme ring color for TMDb rating."""
    return _score_ring_color_for_progress(normalize_tmdb_score(value))


def format_year_pill(year) -> str:
    return format_year_display(year)


def format_year_display(year) -> str:
    """Format UI year without leaking float artifacts like 2015.0."""
    if year in (None, "") or isinstance(year, bool):
        return ""
    try:
        value = float(year)
    except (TypeError, ValueError):
        return str(year).strip()
    if value.is_integer():
        return str(int(value))
    return str(year).strip()


def build_score_ring_item(card: dict) -> dict | None:
    """Build the TMDb-only score ring item for the detail card."""
    if has_unknown_rating(card):
        return None
    has_tmdb_score = card.get("tmdb_score") not in (None, "")
    if has_tmdb_score is False:
        return None

    display_value = format_rating_score_display(card.get("tmdb_score"))
    ring_progress = normalize_tmdb_score(card.get("tmdb_score"))
    return {
        "kind": "score_ring",
        "source": "tmdb",
        "display_value": display_value or "—",
        "display_label": "TMDb",
        "ring_progress": ring_progress,
        "accent": score_ring_color_for_tmdb_score(card.get("tmdb_score")),
    }


def build_final_score_star_item(card: dict) -> dict | None:
    """Build qualitative recommendation strength for the detail card."""
    if card.get("final_score") in (None, ""):
        return None
    confidence = card.get("rating_confidence") or candidate_rating_confidence(card)
    quality_label = format_final_score_quality_label(card.get("final_score"), confidence)
    return {
        "kind": "recommendation_strength",
        "label": f"{tr('recommendation.strength.label')}: {quality_label}",
        "tooltip": quality_label,
    }


def build_user_score_badge_item(card: dict) -> dict | None:
    """Build watched-only user score badge payload for the poster overlay."""
    if card.get("runtime_status") != "watched":
        return None
    display_value = format_user_score_display(card.get("user_score"))
    if display_value == "—":
        return None
    rating = normalize_user_rating(card.get("user_score"))
    return {
        "kind": "user_score_badge",
        "value": rating,
        "text": str(rating),
        "heart": True,
    }


def format_tmdb_pill(score: str) -> dict:
    return {
        "kind": "score_ring",
        "source": "tmdb",
        "display_value": score,
        "display_label": "TMDb",
        "ring_progress": normalize_tmdb_score(score),
        "accent": score_ring_color_for_tmdb_score(score),
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
        labels.append(format_year_display(year))

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
    return build_genre_pill_labels(card)


def has_overview_text(card: dict) -> bool:
    """Return True when the card has non-empty overview text."""
    overview = card.get("overview")
    if overview in (None, ""):
        return False
    return bool(str(overview).strip())


def get_overview_display(card: dict) -> str:
    """Return overview text for detail card."""
    return str(card.get("overview", "")).strip()
