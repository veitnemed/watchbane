from candidates.onboarding.autofill import OnboardingTasteProfile, build_country_plan
from candidates.onboarding.taste_presets import (
    ANIMATION_MODE_ANIMATION_ONLY,
    ANIMATION_MODE_ANY,
    ANIMATION_MODE_LIVE_ACTION_ONLY,
    MEDIA_TYPE_BOTH,
    MEDIA_TYPE_TV,
    PRESET_ANIME,
    PRESET_K_DRAMA,
    get_taste_preset,
    manual_taste_preset,
)


def test_anime_preset_contract_expresses_jp_animation() -> None:
    preset = get_taste_preset(PRESET_ANIME)

    assert preset is not None
    assert preset.countries == ("JP",)
    assert preset.animation_mode == ANIMATION_MODE_ANIMATION_ONLY
    assert preset.media_type == MEDIA_TYPE_BOTH
    assert preset.genre_groups == ("anime",)

    profile = OnboardingTasteProfile(**preset.to_profile_kwargs(ui_language="en")).normalized()
    assert profile.media_preference == "both"
    assert profile.country_selection.selected_countries == ("JP",)
    assert build_country_plan(profile.country_selection, 120) == {"JP": 120}


def test_k_drama_preset_contract_expresses_kr_live_action_tv() -> None:
    preset = get_taste_preset(PRESET_K_DRAMA)

    assert preset is not None
    assert preset.countries == ("KR",)
    assert preset.animation_mode == ANIMATION_MODE_LIVE_ACTION_ONLY
    assert preset.media_type == MEDIA_TYPE_TV
    assert preset.genre_groups == ("drama", "romance")

    profile = OnboardingTasteProfile(**preset.to_profile_kwargs(ui_language="en")).normalized()
    assert profile.media_preference == "tv"
    assert profile.country_selection.selected_countries == ("KR",)


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

