"""Preference compatibility checks before onboarding Discover planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_BLOCKING = "blocking"

PRESET_MANUAL = "manual"
PRESET_ANIME = "anime"
PRESET_FAMILY_ANIMATION = "family_animation"
PRESET_K_DRAMA = "k_drama"
PRESET_TURKISH_DRAMAS = "turkish_dramas"
PRESET_RUSSIAN_MAINSTREAM = "russian_mainstream"

ANIMATION_MODE_ANY = "any"
ANIMATION_MODE_ANIMATION_ONLY = "animation_only"
ANIMATION_MODE_LIVE_ACTION_ONLY = "live_action_only"


@dataclass(frozen=True)
class PreferenceCompatibilityIssue:
    severity: str
    code: str
    message: str
    suggested_fixes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreferenceCompatibilityDiagnostics:
    issues: tuple[PreferenceCompatibilityIssue, ...]
    auto_fix_applied: bool
    selected_preset_before: str
    selected_preset_after: str
    countries_before: tuple[str, ...]
    countries_after: tuple[str, ...]
    animation_mode_before: str
    animation_mode_after: str
    media_type_before: str
    media_type_after: str

    @property
    def preference_conflict_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == SEVERITY_BLOCKING)

    @property
    def preference_warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == SEVERITY_WARNING)

    @property
    def preference_conflict_codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues if issue.severity == SEVERITY_BLOCKING)

    def as_dict(self) -> dict[str, Any]:
        return {
            "preference_conflict_count": self.preference_conflict_count,
            "preference_warning_count": self.preference_warning_count,
            "preference_conflict_codes": list(self.preference_conflict_codes),
            "auto_fix_applied": self.auto_fix_applied,
            "selected_preset_before": self.selected_preset_before,
            "selected_preset_after": self.selected_preset_after,
            "countries_before": list(self.countries_before),
            "countries_after": list(self.countries_after),
            "animation_mode_before": self.animation_mode_before,
            "animation_mode_after": self.animation_mode_after,
            "media_type_before": self.media_type_before,
            "media_type_after": self.media_type_after,
            "issues": [issue.as_dict() for issue in self.issues],
        }


def _normalize_preset(value: Any) -> str:
    return str(value or PRESET_MANUAL).strip() or PRESET_MANUAL


def _normalize_animation(value: Any) -> str:
    text = str(value or ANIMATION_MODE_ANY).strip()
    if text in {ANIMATION_MODE_ANY, ANIMATION_MODE_ANIMATION_ONLY, ANIMATION_MODE_LIVE_ACTION_ONLY}:
        return text
    return ANIMATION_MODE_ANY


def _normalize_media(value: Any) -> str:
    text = str(value or "both").strip()
    if text in {"movie", "tv", "both"}:
        return text
    return "both"


def _normalize_countries(countries: Any) -> tuple[str, ...]:
    result: list[str] = []
    for value in countries or ():
        code = str(value or "").strip().upper()
        if len(code) == 2 and code.isascii() and code.isalpha() and code not in result:
            result.append(code)
    return tuple(result)


def _with_country_first(countries: tuple[str, ...], country: str) -> tuple[str, ...]:
    normalized = country.strip().upper()
    return (normalized, *tuple(code for code in countries if code != normalized))


def resolve_preference_compatibility(
    *,
    selected_preset: Any,
    countries: Any,
    media_type: Any,
    animation_mode: Any,
    animation_disliked: bool = False,
    auto_fix: bool = True,
) -> PreferenceCompatibilityDiagnostics:
    preset_before = _normalize_preset(selected_preset)
    countries_before = _normalize_countries(countries)
    media_before = _normalize_media(media_type)
    animation_before = _normalize_animation(animation_mode)
    preset_after = preset_before
    countries_after = countries_before
    media_after = media_before
    animation_after = animation_before
    issues: list[PreferenceCompatibilityIssue] = []

    def add_issue(severity: str, code: str, message: str, fixes: tuple[str, ...]) -> None:
        issues.append(PreferenceCompatibilityIssue(severity, code, message, fixes))

    if preset_before == PRESET_ANIME:
        if animation_before != ANIMATION_MODE_ANIMATION_ONLY:
            add_issue(
                SEVERITY_BLOCKING,
                "anime_requires_animation_only",
                "Anime preset requires animation-only Discover planning.",
                (
                    "Keep anime: set animation_mode=animation_only and include JP.",
                    "Switch to a live-action preset such as k_drama, russian_mainstream or manual.",
                ),
            )
            if auto_fix:
                animation_after = ANIMATION_MODE_ANIMATION_ONLY
        if "JP" not in countries_before:
            add_issue(
                SEVERITY_WARNING,
                "anime_origin_requires_jp",
                "Anime preset should include JP because countries are TMDb origin countries, not language.",
                ("Keep anime: add JP as an origin country.", "Use manual mode for advanced country mixes."),
            )
            if auto_fix:
                countries_after = _with_country_first(countries_after, "JP")
        if animation_disliked:
            add_issue(
                SEVERITY_BLOCKING,
                "animation_dislike_conflicts_with_anime",
                "Anime conflicts with the selected animation dislike signal.",
                ("Switch to a live-action preset.", "Use manual mode if this is intentional."),
            )

    if preset_before == PRESET_FAMILY_ANIMATION:
        if animation_before != ANIMATION_MODE_ANIMATION_ONLY:
            add_issue(
                SEVERITY_BLOCKING,
                "family_animation_requires_animation_only",
                "Family animation preset requires animation-only Discover planning.",
                ("Keep family animation: set animation_mode=animation_only.", "Switch to a live-action preset."),
            )
            if auto_fix:
                animation_after = ANIMATION_MODE_ANIMATION_ONLY
        if animation_disliked:
            add_issue(
                SEVERITY_BLOCKING,
                "animation_dislike_conflicts_with_family_animation",
                "Family animation conflicts with the selected animation dislike signal.",
                ("Switch to a live-action preset.", "Use manual mode if this is intentional."),
            )

    if preset_before in {PRESET_K_DRAMA, PRESET_TURKISH_DRAMAS} and animation_before == ANIMATION_MODE_ANIMATION_ONLY:
        add_issue(
            SEVERITY_BLOCKING,
            "live_action_preset_conflicts_with_animation_only",
            "This preset is a live-action starter preset and should not use animation-only Discover planning.",
            ("Keep this preset: set animation_mode=live_action_only.", "Switch to anime or family animation."),
        )
        if auto_fix:
            animation_after = ANIMATION_MODE_LIVE_ACTION_ONLY

    if preset_before == PRESET_RUSSIAN_MAINSTREAM and animation_before == ANIMATION_MODE_ANIMATION_ONLY:
        add_issue(
            SEVERITY_WARNING,
            "russian_animation_low_yield",
            "Russian mainstream with animation-only is allowed but may be narrow and low-yield.",
            ("Keep Russian mainstream live-action.", "Use manual mode for advanced animation-only RU searches."),
        )

    if preset_before == PRESET_MANUAL and animation_disliked and animation_before == ANIMATION_MODE_ANIMATION_ONLY:
        add_issue(
            SEVERITY_WARNING,
            "manual_animation_dislike",
            "Manual mode allows this combination, but animation-only conflicts with the animation dislike signal.",
            ("Switch animation_mode to live_action_only.", "Continue manually if intentional."),
        )

    auto_fix_applied = (
        preset_after != preset_before
        or countries_after != countries_before
        or animation_after != animation_before
        or media_after != media_before
    )
    return PreferenceCompatibilityDiagnostics(
        issues=tuple(issues),
        auto_fix_applied=auto_fix_applied,
        selected_preset_before=preset_before,
        selected_preset_after=preset_after,
        countries_before=countries_before,
        countries_after=countries_after,
        animation_mode_before=animation_before,
        animation_mode_after=animation_after,
        media_type_before=media_before,
        media_type_after=media_after,
    )
