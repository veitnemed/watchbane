"""Compatibility checks for filter-driven candidate replenish intent."""

from __future__ import annotations

from typing import Any

from candidates.replenish.filter_intent import (
    ANIMATION_MODE_ANIMATION_ONLY,
    ANIMATION_MODE_LIVE_ACTION_ONLY,
    FilterReplenishIntent,
)

PRESET_MANUAL = "manual"
PRESET_ANIME = "anime"
PRESET_FAMILY_ANIMATION = "family_animation"
PRESET_K_DRAMA = "k_drama"
PRESET_TURKISH_DRAMAS = "turkish_dramas"
PRESET_RUSSIAN_MAINSTREAM = "russian_mainstream"


def _as_intent(intent: FilterReplenishIntent | dict[str, Any]) -> FilterReplenishIntent:
    if isinstance(intent, FilterReplenishIntent):
        return intent
    return FilterReplenishIntent.from_dict(intent)


def _issue(code: str, message: str, fixes: tuple[str, ...]) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "suggested_fixes": list(fixes),
    }


def _add_issue(
    target: list[dict[str, Any]],
    suggested_fixes: list[str],
    *,
    code: str,
    message: str,
    fixes: tuple[str, ...],
) -> None:
    target.append(_issue(code, message, fixes))
    for fix in fixes:
        if fix not in suggested_fixes:
            suggested_fixes.append(fix)


def _anime_requested(intent: FilterReplenishIntent) -> bool:
    return intent.preset_id == PRESET_ANIME or "anime" in {item.casefold() for item in intent.genre_groups}


def _manual_override_allows_warning(intent: FilterReplenishIntent) -> bool:
    return (intent.preset_id in (None, PRESET_MANUAL)) and intent.allow_advanced_override


def _add_block_or_manual_warning(
    blocking_conflicts: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    suggested_fixes: list[str],
    intent: FilterReplenishIntent,
    *,
    code: str,
    message: str,
    fixes: tuple[str, ...],
) -> None:
    target = warnings if _manual_override_allows_warning(intent) else blocking_conflicts
    _add_issue(target, suggested_fixes, code=code, message=message, fixes=fixes)


def resolve_filter_replenish_compatibility(intent: FilterReplenishIntent | dict[str, Any]) -> dict[str, Any]:
    """Return serializable warnings/blockers for a replenish filter intent."""
    normalized = _as_intent(intent)
    preset_id = normalized.preset_id or PRESET_MANUAL
    blocking_conflicts: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    suggested_fixes: list[str] = []

    if _anime_requested(normalized):
        if normalized.animation_mode != ANIMATION_MODE_ANIMATION_ONLY:
            _add_block_or_manual_warning(
                blocking_conflicts,
                warnings,
                suggested_fixes,
                normalized,
                code="anime_requires_animation_only",
                message="Anime replenish should run with animation_mode=animation_only.",
                fixes=(
                    "Set animation_mode=animation_only.",
                    "Switch to manual advanced override if this live-action search is intentional.",
                ),
            )
        if "JP" not in normalized.countries:
            _add_issue(
                warnings,
                suggested_fixes,
                code="anime_origin_requires_jp",
                message="Anime should include JP because countries are TMDb origin countries, not language.",
                fixes=("Add JP as an origin country.", "Use manual mode for advanced country mixes."),
            )
        if normalized.countries == ["RU"]:
            _add_issue(
                warnings,
                suggested_fixes,
                code="anime_ru_without_jp_origin_warning",
                message="Anime + RU without JP is likely low-yield because countries are origin countries.",
                fixes=("Add JP to origin countries.", "Use RU only in manual mode if intentional."),
            )

    if preset_id == PRESET_FAMILY_ANIMATION and normalized.animation_mode == ANIMATION_MODE_LIVE_ACTION_ONLY:
        _add_issue(
            blocking_conflicts,
            suggested_fixes,
            code="family_animation_conflicts_with_live_action_only",
            message="Family animation cannot run with live_action_only.",
            fixes=("Set animation_mode=animation_only.", "Choose a live-action preset."),
        )

    if preset_id in {PRESET_K_DRAMA, PRESET_TURKISH_DRAMAS} and normalized.animation_mode == ANIMATION_MODE_ANIMATION_ONLY:
        _add_issue(
            blocking_conflicts,
            suggested_fixes,
            code="live_action_preset_conflicts_with_animation_only",
            message="This live-action preset should not run as animation_only.",
            fixes=("Set animation_mode=live_action_only.", "Choose anime or family_animation."),
        )

    if preset_id == PRESET_RUSSIAN_MAINSTREAM and normalized.animation_mode == ANIMATION_MODE_ANIMATION_ONLY:
        _add_issue(
            warnings,
            suggested_fixes,
            code="russian_animation_low_yield",
            message="Russian mainstream with animation_only is allowed but likely narrow and low-yield.",
            fixes=("Switch to live_action_only for mainstream results.", "Use manual mode if this is intentional."),
        )

    if normalized.animation_mode == ANIMATION_MODE_ANIMATION_ONLY:
        _add_issue(
            warnings,
            suggested_fixes,
            code="animation_only_maps_to_tmdb_animation_genre",
            message="animation_only will map to including TMDb Animation genre 16 in request planning.",
            fixes=("Keep animation_only for animation searches.",),
        )

    if normalized.animation_mode == ANIMATION_MODE_LIVE_ACTION_ONLY:
        _add_issue(
            warnings,
            suggested_fixes,
            code="live_action_only_maps_to_excluding_tmdb_animation_genre",
            message="live_action_only will map to excluding TMDb Animation genre 16 in request planning.",
            fixes=("Keep live_action_only for non-animation searches.",),
        )

    if preset_id == PRESET_MANUAL and blocking_conflicts and normalized.allow_advanced_override is False:
        _add_issue(
            warnings,
            suggested_fixes,
            code="manual_advanced_override_required",
            message="Manual incompatible replenish combinations require allow_advanced_override=true.",
            fixes=("Enable advanced override only for intentional manual searches.",),
        )

    return {
        "can_run": len(blocking_conflicts) == 0,
        "blocking_conflicts": blocking_conflicts,
        "warnings": warnings,
        "suggested_fixes": suggested_fixes,
        "intent": normalized.to_dict(),
    }
