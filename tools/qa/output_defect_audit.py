"""QA-only checks for onboarding preset output contracts and synthetic deck metadata."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from candidates.onboarding.autofill import OnboardingTasteProfile, build_discover_request, build_fetch_buckets
from candidates.onboarding.taste_presets import PRESETS, TastePreset, taste_preset_to_profile_payload
from candidates.safety.explicit_content import evaluate_explicit_sexual_content


PLACEHOLDER_TITLES = frozenset({"", "unknown", "untitled", "n/a", "none", "null", "tbd"})
MOJIBAKE_MARKERS = ("Ð", "Ñ", "�")
SEXUAL_TEXT_MARKERS = (
    "hentai",
    "хентай",
    "porn",
    "порно",
    "pornograph",
    "порнограф",
    "explicit sex",
    "явный секс",
)
def _has_readable_character(value: str) -> bool:
    return any(character.isalnum() for character in value)


def audit_title(value: Any) -> list[str]:
    """Return visible-title defects without correcting or replacing title text."""
    title = " ".join(str(value or "").split()).strip()
    defects: list[str] = []
    if title.casefold() in PLACEHOLDER_TITLES:
        defects.append("missing_or_placeholder_title")
    if any(marker in title for marker in MOJIBAKE_MARKERS):
        defects.append("mojibake_title")
    if title and not _has_readable_character(title):
        defects.append("unreadable_title")
    return defects


def _text_markers(candidate: dict[str, Any]) -> list[str]:
    parts = [
        str(candidate.get(field) or "")
        for field in ("title", "original_title", "overview")
    ]
    parts.extend(str(item or "") for item in (candidate.get("keywords") or []))
    corpus = "\n".join(parts).casefold()
    return [marker for marker in SEXUAL_TEXT_MARKERS if marker.casefold() in corpus]


def audit_deck_cards(cards: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Audit displayed deck fields; use the existing safety gate for explicit content."""
    findings: list[dict[str, Any]] = []
    for card in cards:
        title = str(card.get("title") or card.get("original_title") or "").strip()
        defects = audit_title(title)
        for field in ("tmdb_id", "media_type", "year"):
            if card.get(field) in (None, ""):
                defects.append(f"missing_{field}")
        for field in ("genres", "countries"):
            if not list(card.get(field) or []):
                defects.append(f"missing_{field}")
        safety = evaluate_explicit_sexual_content(card).to_dict()
        if safety["blocked"]:
            defects.append("explicit_content_returned")
        markers = _text_markers(card)
        if markers:
            defects.append("sexual_text_marker")
        findings.append(
            {
                "tmdb_id": card.get("tmdb_id"),
                "title": title,
                "passed": not defects,
                "defects": defects,
                "sexual_text_markers": markers,
                "explicit_content_decision": safety,
            }
        )
    return {
        "cards": findings,
        "passed": all(item["passed"] for item in findings),
        "defect_count": sum(len(item["defects"]) for item in findings),
    }


def _preset_entry(preset: TastePreset) -> dict[str, Any]:
    payload = taste_preset_to_profile_payload(preset.preset_id, ui_language="en")
    profile = OnboardingTasteProfile(**payload).normalized()
    buckets = build_fetch_buckets(profile)
    bucket_rows: list[dict[str, Any]] = []
    defects: list[str] = []
    for index, bucket in enumerate(buckets):
        endpoint, params = build_discover_request(
            bucket,
            profile=profile,
            fallback="base",
            request_index=index,
            current_year=2026,
        )
        if params.get("include_adult") is not False:
            defects.append(f"bucket_{index}_adult_not_disabled")
        if bucket.target_country not in preset.countries:
            defects.append(f"bucket_{index}_unexpected_country")
        bucket_rows.append(
            {
                "media_type": bucket.media_type,
                "target_country": bucket.target_country,
                "quota": bucket.quota,
                "endpoint": endpoint,
                "include_adult": params.get("include_adult"),
                "language": params.get("language"),
            }
        )
    expected_media = {"movie", "tv"} if preset.media_type == "both" else {preset.media_type}
    actual_media = {str(row["media_type"]) for row in bucket_rows}
    if actual_media != expected_media:
        defects.append("unexpected_media_bucket_set")
    if not bucket_rows or sum(int(row["quota"] or 0) for row in bucket_rows) <= 0:
        defects.append("empty_preset_fetch_plan")
    return {
        "preset_id": preset.preset_id,
        "countries": list(preset.countries),
        "media_type": preset.media_type,
        "animation_mode": preset.animation_mode,
        "genre_groups": list(preset.genre_groups),
        "buckets": bucket_rows,
        "passed": not defects,
        "defects": defects,
    }


def build_output_defect_audit(profile_reports: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build a deterministic QA report. It does not fetch or rerank candidates."""
    presets = [_preset_entry(preset) for _, preset in sorted(PRESETS.items())]
    deck_reports = [
        {
            "profile_id": report.get("profile_id"),
            "deck_output": audit_deck_cards(report.get("top_10") or []),
        }
        for report in profile_reports
    ]
    return {
        "scope": {
            "onboarding_presets": "All current PRESETS are checked through the existing fetch/discover builders; no network call is made.",
            "deck_output": "Synthetic top-10 reports are checked for visible metadata and safety signals using the existing explicit-content gate.",
            "limitation": "This audit does not prove live TMDb availability or subjective usefulness, and it does not alter product ranking, filtering, safety, or UI.",
        },
        "preset_contracts": presets,
        "synthetic_decks": deck_reports,
        "passed": all(item["passed"] for item in presets)
        and all(item["deck_output"]["passed"] for item in deck_reports),
    }
