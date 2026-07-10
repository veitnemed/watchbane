from candidates.replenish.compatibility import resolve_filter_replenish_compatibility
from candidates.replenish.filter_intent import FilterReplenishIntent


def _codes(issues: list[dict]) -> set[str]:
    return {issue["code"] for issue in issues}


def test_anime_ru_live_action_blocks_and_warns_about_origin() -> None:
    result = resolve_filter_replenish_compatibility(
        FilterReplenishIntent(
            preset_id="anime",
            countries=["RU"],
            animation_mode="live_action_only",
        )
    )

    assert result["can_run"] is False
    assert "anime_requires_animation_only" in _codes(result["blocking_conflicts"])
    assert "anime_origin_requires_jp" in _codes(result["warnings"])
    assert "anime_ru_without_jp_origin_warning" in _codes(result["warnings"])


def test_anime_jp_animation_can_run_with_mapping_warning() -> None:
    result = resolve_filter_replenish_compatibility(
        FilterReplenishIntent(
            preset_id="anime",
            countries=["JP"],
            animation_mode="animation_only",
        )
    )

    assert result["can_run"] is True
    assert result["blocking_conflicts"] == []
    assert "animation_only_maps_to_tmdb_animation_genre" in _codes(result["warnings"])


def test_k_drama_animation_only_blocks() -> None:
    result = resolve_filter_replenish_compatibility(
        FilterReplenishIntent(
            preset_id="k_drama",
            countries=["KR"],
            animation_mode="animation_only",
        )
    )

    assert result["can_run"] is False
    assert "live_action_preset_conflicts_with_animation_only" in _codes(result["blocking_conflicts"])


def test_family_animation_live_action_blocks() -> None:
    result = resolve_filter_replenish_compatibility(
        FilterReplenishIntent(
            preset_id="family_animation",
            countries=["US"],
            animation_mode="live_action_only",
        )
    )

    assert result["can_run"] is False
    assert "family_animation_conflicts_with_live_action_only" in _codes(result["blocking_conflicts"])


def test_russian_mainstream_animation_only_warns_not_blocks() -> None:
    result = resolve_filter_replenish_compatibility(
        FilterReplenishIntent(
            preset_id="russian_mainstream",
            countries=["RU"],
            animation_mode="animation_only",
        )
    )

    assert result["can_run"] is True
    assert result["blocking_conflicts"] == []
    assert "russian_animation_low_yield" in _codes(result["warnings"])


def test_manual_anime_live_action_requires_advanced_override() -> None:
    blocked = resolve_filter_replenish_compatibility(
        FilterReplenishIntent(
            preset_id="manual",
            countries=["RU"],
            genre_groups=["anime"],
            animation_mode="live_action_only",
            allow_advanced_override=False,
        )
    )
    override = resolve_filter_replenish_compatibility(
        FilterReplenishIntent(
            preset_id="manual",
            countries=["RU"],
            genre_groups=["anime"],
            animation_mode="live_action_only",
            allow_advanced_override=True,
        )
    )

    assert blocked["can_run"] is False
    assert "anime_requires_animation_only" in _codes(blocked["blocking_conflicts"])
    assert "manual_advanced_override_required" in _codes(blocked["warnings"])

    assert override["can_run"] is True
    assert override["blocking_conflicts"] == []
    assert "anime_requires_animation_only" in _codes(override["warnings"])


def test_result_is_serializable_dict_with_normalized_intent() -> None:
    result = resolve_filter_replenish_compatibility(
        {
            "preset_id": "anime",
            "countries": ["jp"],
            "animation_mode": "animation_only",
        }
    )

    assert result["intent"]["countries"] == ["JP"]
    assert set(result) == {
        "can_run",
        "blocking_conflicts",
        "warnings",
        "suggested_fixes",
        "intent",
    }
