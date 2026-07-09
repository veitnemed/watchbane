from candidates import service
from candidates.onboarding.autofill import OnboardingTasteProfile, build_country_plan
from candidates.onboarding.compatibility import resolve_preference_compatibility
from candidates.onboarding.taste_presets import (
    ANIMATION_MODE_ANIMATION_ONLY,
    ANIMATION_MODE_ANY,
    ANIMATION_MODE_LIVE_ACTION_ONLY,
    MEDIA_TYPE_BOTH,
    MEDIA_TYPE_TV,
    PRESET_DARK_THRILLER_CRIME,
    PRESET_ANIME,
    PRESET_FAMILY_ANIMATION,
    PRESET_K_DRAMA,
    PRESET_TURKISH_DRAMAS,
    get_taste_preset,
    manual_taste_preset,
    taste_preset_to_profile_payload,
)


def test_anime_preset_contract_expresses_jp_animation() -> None:
    preset = get_taste_preset(PRESET_ANIME)

    assert preset is not None
    assert preset.countries == ("JP",)
    assert preset.animation_mode == ANIMATION_MODE_ANIMATION_ONLY
    assert preset.media_type == MEDIA_TYPE_BOTH
    assert preset.genre_groups == ("action_adventure", "fantasy", "drama", "romance", "comedy")

    profile = OnboardingTasteProfile(**preset.to_profile_kwargs(ui_language="en")).normalized()
    assert profile.media_preference == "both"
    assert profile.country_selection.selected_countries == ("JP",)
    assert build_country_plan(profile.country_selection, 120) == {"JP": 120}
    assert profile.taste_preset == PRESET_ANIME


def test_preference_compatibility_repairs_anime_live_action_without_broad_origin() -> None:
    profile = OnboardingTasteProfile(
        taste_preset=PRESET_ANIME,
        ui_language="ru",
        media_preference="both",
        animation_mode=ANIMATION_MODE_LIVE_ACTION_ONLY,
        release_preference="mixed",
        vibe_preference="mixed",
        origin_preference="foreign",
        country_selection={"selected_countries": ["RU"], "home_country": "RU"},
    ).normalized()

    assert profile.animation_mode == ANIMATION_MODE_ANIMATION_ONLY
    assert "JP" in profile.country_selection.selected_countries
    assert profile.preference_compatibility["auto_fix_applied"] is True
    assert "anime_requires_animation_only" in profile.preference_compatibility["preference_conflict_codes"]


def test_preference_compatibility_warns_for_manual_but_does_not_autofix() -> None:
    diagnostics = resolve_preference_compatibility(
        selected_preset="manual",
        countries=["RU"],
        media_type="both",
        animation_mode=ANIMATION_MODE_ANIMATION_ONLY,
        animation_disliked=True,
    )

    assert diagnostics.preference_conflict_count == 0
    assert diagnostics.preference_warning_count == 1
    assert diagnostics.auto_fix_applied is False
    assert diagnostics.countries_after == ("RU",)
    assert diagnostics.animation_mode_after == ANIMATION_MODE_ANIMATION_ONLY


def test_k_drama_preset_contract_expresses_kr_live_action_tv() -> None:
    preset = get_taste_preset(PRESET_K_DRAMA)

    assert preset is not None
    assert preset.countries == ("KR",)
    assert preset.animation_mode == ANIMATION_MODE_LIVE_ACTION_ONLY
    assert preset.media_type == MEDIA_TYPE_TV
    assert preset.genre_groups == ("drama", "romance", "comedy", "crime", "thriller")

    profile = OnboardingTasteProfile(**preset.to_profile_kwargs(ui_language="en")).normalized()
    assert profile.media_preference == "tv"
    assert profile.country_selection.selected_countries == ("KR",)


def test_required_starter_presets_have_exact_contract_axes() -> None:
    expected = {
        PRESET_TURKISH_DRAMAS: (
            ("TR",),
            ANIMATION_MODE_LIVE_ACTION_ONLY,
            MEDIA_TYPE_TV,
            ("drama", "romance", "family"),
        ),
        PRESET_FAMILY_ANIMATION: (
            ("US", "JP", "RU"),
            ANIMATION_MODE_ANIMATION_ONLY,
            MEDIA_TYPE_BOTH,
            ("family", "comedy", "adventure", "fantasy"),
        ),
        PRESET_DARK_THRILLER_CRIME: (
            ("US", "GB", "KR", "JP", "RU"),
            ANIMATION_MODE_ANY,
            MEDIA_TYPE_BOTH,
            ("crime", "mystery", "thriller", "horror", "drama"),
        ),
    }

    for key, (countries, animation_mode, media_type, genre_groups) in expected.items():
        preset = get_taste_preset(key)
        assert preset is not None
        assert preset.countries == countries
        assert preset.animation_mode == animation_mode
        assert preset.media_type == media_type
        assert preset.genre_groups == genre_groups


def test_manual_taste_preset_allows_up_to_five_countries() -> None:
    preset = manual_taste_preset(
        ["US", "RU", "GB", "KR", "JP", "FR"],
        animation_mode=ANIMATION_MODE_ANY,
    )

    assert preset.countries == ("US", "RU", "GB", "KR", "JP")
    profile = OnboardingTasteProfile(**preset.to_profile_kwargs(ui_language="en")).normalized()
    assert profile.country_selection.selected_countries == ("US", "RU", "GB", "KR", "JP")
    assert build_country_plan(profile.country_selection, 120) == {
        "US": 24,
        "RU": 24,
        "GB": 24,
        "KR": 24,
        "JP": 24,
    }


def test_manual_taste_preset_normalizes_invalid_country_counts() -> None:
    empty = manual_taste_preset([], home_country="US")
    invalid = manual_taste_preset(["", "USA", "1", "kr"], home_country="US")

    assert empty.countries == ("US",)
    assert invalid.countries == ("KR",)


def test_manual_payload_keeps_country_limit() -> None:
    payload = taste_preset_to_profile_payload(
        "manual",
        overrides={"countries": ["US", "RU", "GB", "KR", "JP", "TR"], "ui_language": "en"},
    )
    profile = OnboardingTasteProfile(**payload).normalized()

    assert profile.country_selection.selected_countries == ("US", "RU", "GB", "KR", "JP")


def test_preset_payload_can_build_plan_without_api_calls() -> None:
    payload = taste_preset_to_profile_payload(PRESET_TURKISH_DRAMAS, ui_language="en")
    plan = service.get_onboarding_autofill_plan_view(payload)

    assert plan["target"] == 120
    assert plan["quotas"]["country"] == {"TR": 120}
    assert plan["quotas"]["media_type"] == {"tv": 120}
