from itertools import product

import pytest

from candidates.replenish.filter_discover import (
    build_filter_discover_params,
    discover_params_have_broad_origin_fallback,
    discover_params_have_vote_rating_filters,
)
from candidates.replenish.filter_intent import FilterReplenishIntent
from candidates.replenish.filter_plan import build_filter_replenish_plan


FORBIDDEN_KEYS = {
    "vote_count.gte",
    "vote_average.gte",
    "vote_count_gte",
    "vote_average_gte",
    "fallback",
    "broad_origin",
    "broad_origin_fallback",
    "without_origin_country",
}


def _params_for(intent: FilterReplenishIntent, *, bucket_index: int = 0, page: int = 1) -> dict:
    plan = build_filter_replenish_plan(intent)
    return build_filter_discover_params(
        plan["buckets"][bucket_index],
        page,
        intent=plan["intent"],
    )


def test_discover_params_are_country_first_and_have_no_vote_rating_filters() -> None:
    params = _params_for(
        FilterReplenishIntent(
            countries=["RU"],
            media_type="tv",
            animation_mode="live_action_only",
            include_genres=["Drama", "Crime"],
            target_add_count=30,
            data_language="en",
        ),
        page=2,
    )

    assert params["include_adult"] is False
    assert params["sort_by"] == "popularity.desc"
    assert params["language"] == "en-US"
    assert params["page"] == 2
    assert params["with_origin_country"] == "RU"
    assert params["with_genres"] == "18|80"
    assert "16" in params["without_genres"].split(",")
    assert FORBIDDEN_KEYS.isdisjoint(params)
    assert discover_params_have_vote_rating_filters(params) is False
    assert discover_params_have_broad_origin_fallback(params) is False


def test_tv_uses_first_air_date_and_movie_uses_primary_release_date() -> None:
    tv_params = _params_for(
        FilterReplenishIntent(countries=["KR"], media_type="tv", year_min=2018, year_max=2024)
    )
    movie_params = _params_for(
        FilterReplenishIntent(countries=["US"], media_type="movie", year_min=2020, year_max=2026)
    )

    assert tv_params["first_air_date.gte"] == "2018-01-01"
    assert tv_params["first_air_date.lte"] == "2024-12-31"
    assert "primary_release_date.gte" not in tv_params

    assert movie_params["primary_release_date.gte"] == "2020-01-01"
    assert movie_params["primary_release_date.lte"] == "2026-12-31"
    assert "first_air_date.gte" not in movie_params


def test_release_preference_adds_date_constraints_without_vote_filters() -> None:
    classic = _params_for(
        FilterReplenishIntent(countries=["GB"], media_type="movie", release_preference="classic")
    )
    new = _params_for(
        FilterReplenishIntent(countries=["US"], media_type="movie", release_preference="new")
    )

    assert classic["primary_release_date.gte"] == "2005-01-01"
    assert classic["primary_release_date.lte"] == "2021-12-31"
    assert new["primary_release_date.gte"] == "2022-01-01"
    assert FORBIDDEN_KEYS.isdisjoint(classic)
    assert FORBIDDEN_KEYS.isdisjoint(new)


@pytest.mark.parametrize("country_count", [1, 2, 3, 4, 5])
def test_selected_countries_always_become_with_origin_country(country_count: int) -> None:
    countries = ["US", "GB", "JP", "KR", "RU"][:country_count]
    plan = build_filter_replenish_plan(
        FilterReplenishIntent(
            countries=countries,
            media_type="movie",
            target_add_count=30,
        )
    )

    for bucket in plan["buckets"]:
        params = build_filter_discover_params(bucket, 1, intent=plan["intent"])
        assert params["with_origin_country"] == bucket["country"]
        assert FORBIDDEN_KEYS.isdisjoint(params)


@pytest.mark.parametrize(
    ("media_type", "release_preference", "vibe", "animation_mode"),
    list(product(
        ["movie", "tv", "both"],
        ["new", "classic", "mixed"],
        ["light", "dark", "mixed"],
        ["any", "animation_only", "live_action_only"],
    )),
)
def test_combinatorial_guardrails(media_type, release_preference, vibe, animation_mode) -> None:
    plan = build_filter_replenish_plan(
        FilterReplenishIntent(
            countries=["US", "GB"],
            media_type=media_type,
            release_preference=release_preference,
            vibe=vibe,
            animation_mode=animation_mode,
            target_add_count=8,
        )
    )

    assert plan["buckets"]
    for bucket in plan["buckets"]:
        params = build_filter_discover_params(bucket, 1, intent=plan["intent"])
        assert FORBIDDEN_KEYS.isdisjoint(params)
        assert params["with_origin_country"] in {"US", "GB"}
        if animation_mode == "animation_only":
            assert params.get("with_genres", "").split("|")[0] == "16"
        if animation_mode == "live_action_only":
            assert "16" in params.get("without_genres", "").split(",")
