from candidates.replenish.filter_intent import FilterReplenishIntent


def test_filter_replenish_intent_defaults_for_planning() -> None:
    intent = FilterReplenishIntent()

    assert intent.to_dict() == {
        "preset_id": None,
        "countries": [],
        "media_type": "both",
        "animation_mode": "any",
        "vibe": "mixed",
        "release_preference": "mixed",
        "origin_preference": None,
        "include_genres": [],
        "exclude_genres": [],
        "genre_groups": [],
        "year_min": None,
        "year_max": None,
        "target_add_count": 30,
        "ui_language": "ru",
        "data_language": "ru",
        "allow_advanced_override": False,
    }


def test_anime_intent_normalizes_countries_and_target() -> None:
    intent = FilterReplenishIntent(
        preset_id="anime",
        countries=["jp", "JP", "ru", "us", "gb", "kr", "tr"],
        media_type="",
        animation_mode="animation_only",
        vibe="",
        release_preference="",
        genre_groups=["fantasy", "fantasy", "drama"],
        target_add_count=90,
        ui_language="",
        data_language="en",
    )

    assert intent.preset_id == "anime"
    assert intent.countries == ["JP", "RU", "US", "GB", "KR"]
    assert intent.media_type == "both"
    assert intent.animation_mode == "animation_only"
    assert intent.vibe == "mixed"
    assert intent.release_preference == "mixed"
    assert intent.genre_groups == ["fantasy", "drama"]
    assert intent.target_add_count == 30
    assert intent.ui_language == "ru"
    assert intent.data_language == "en"


def test_ru_tv_intent_from_filters() -> None:
    intent = FilterReplenishIntent.from_filters(
        {
            "country": ["ru"],
            "media_type": "tv",
            "year_min": "2015",
            "year_max": "2024",
            "include_genres": ["Drama", "Crime", "Drama"],
            "exclude_genres": ["Animation"],
        },
        preset_id="russian_mainstream",
        animation_mode="live_action_only",
        release_preference="new",
        target_add_count=12,
    )

    assert intent.to_dict() | {"include_genres": intent.include_genres} == {
        "preset_id": "russian_mainstream",
        "countries": ["RU"],
        "media_type": "tv",
        "animation_mode": "live_action_only",
        "vibe": "mixed",
        "release_preference": "new",
        "origin_preference": None,
        "include_genres": ["Drama", "Crime"],
        "exclude_genres": ["Animation"],
        "genre_groups": [],
        "year_min": 2015,
        "year_max": 2024,
        "target_add_count": 12,
        "ui_language": "ru",
        "data_language": "ru",
        "allow_advanced_override": False,
    }


def test_manual_intent_round_trip_is_json_safe() -> None:
    intent = FilterReplenishIntent(
        preset_id="manual",
        countries=["US", "GB"],
        media_type="movie",
        animation_mode="any",
        vibe="dark",
        release_preference="classic",
        origin_preference="foreign",
        include_genres=["Mystery"],
        exclude_genres=["Comedy"],
        year_min=2025,
        year_max=2000,
        target_add_count=0,
        allow_advanced_override=True,
    )

    payload = intent.to_dict()
    restored = FilterReplenishIntent.from_dict(payload)

    assert payload["year_min"] == 2000
    assert payload["year_max"] == 2025
    assert payload["target_add_count"] == 1
    assert restored.to_dict() == payload


def test_invalid_choices_fall_back_to_safe_defaults() -> None:
    intent = FilterReplenishIntent(
        media_type="series",
        animation_mode="cartoon",
        vibe="serious",
        release_preference="fresh",
        origin_preference="global",
    )

    assert intent.media_type == "both"
    assert intent.animation_mode == "any"
    assert intent.vibe == "mixed"
    assert intent.release_preference == "mixed"
    assert intent.origin_preference is None
