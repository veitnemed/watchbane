from candidates.replenish.filter_intent import FilterReplenishIntent
from candidates.replenish.filter_plan import build_filter_replenish_plan


def test_one_country_tv_target_30_builds_one_bucket() -> None:
    plan = build_filter_replenish_plan(
        FilterReplenishIntent(
            preset_id="manual",
            countries=["RU"],
            media_type="tv",
            animation_mode="live_action_only",
            vibe="dark",
            include_genres=["Drama", "Crime"],
            target_add_count=30,
        )
    )

    assert plan["target_add_count"] == 30
    assert plan["broad_origin_allowed"] is False
    assert plan["country_plan"] == {"RU": 30}
    assert plan["media_plan"] == {"tv": 30}
    assert len(plan["buckets"]) == 1
    bucket = plan["buckets"][0]
    assert bucket["quota"] == 30
    assert bucket["with_origin_country"] == "RU"
    assert bucket["media_type"] == "tv"
    assert 18 in bucket["include_tmdb_genres"]
    assert 80 in bucket["include_tmdb_genres"]
    assert 16 not in bucket["include_tmdb_genres"]
    assert 16 in bucket["exclude_tmdb_genres"]
    assert 10764 in bucket["exclude_tmdb_genres"]


def test_two_countries_both_media_balances_to_target() -> None:
    plan = build_filter_replenish_plan(
        FilterReplenishIntent(
            countries=["US", "GB"],
            media_type="both",
            target_add_count=30,
        )
    )

    quotas = [bucket["quota"] for bucket in plan["buckets"]]

    assert len(plan["buckets"]) == 4
    assert sum(quotas) == 30
    assert min(quotas) >= 7
    assert max(quotas) <= 8
    assert plan["country_plan"]["US"] + plan["country_plan"]["GB"] == 30
    assert plan["media_plan"]["movie"] + plan["media_plan"]["tv"] == 30
    assert {bucket["with_origin_country"] for bucket in plan["buckets"]} == {"US", "GB"}


def test_anime_jp_forces_animation_genre() -> None:
    plan = build_filter_replenish_plan(
        FilterReplenishIntent(
            preset_id="anime",
            countries=["JP"],
            media_type="both",
            animation_mode="animation_only",
            genre_groups=["anime", "fantasy"],
            target_add_count=10,
        )
    )

    assert plan["can_run"] is True
    assert plan["country_plan"] == {"JP": 10}
    assert plan["media_plan"] == {"movie": 5, "tv": 5}
    for bucket in plan["buckets"]:
        assert bucket["include_tmdb_genres"][0] == 16
        assert 16 not in bucket["exclude_tmdb_genres"]


def test_k_drama_kr_tv_live_action_excludes_animation_and_preserves_tv_junk() -> None:
    plan = build_filter_replenish_plan(
        FilterReplenishIntent(
            preset_id="k_drama",
            countries=["KR"],
            media_type="tv",
            animation_mode="live_action_only",
            genre_groups=["drama", "romance"],
            target_add_count=18,
        )
    )

    bucket = plan["buckets"][0]

    assert plan["can_run"] is True
    assert bucket["with_origin_country"] == "KR"
    assert bucket["include_tmdb_genres"] == [18]
    assert 16 in bucket["exclude_tmdb_genres"]
    assert 10766 in bucket["exclude_tmdb_genres"]


def test_us_gb_new_movies_have_movie_only_buckets_and_years() -> None:
    plan = build_filter_replenish_plan(
        FilterReplenishIntent(
            countries=["US", "GB"],
            media_type="movie",
            release_preference="new",
            year_min=2022,
            year_max=2026,
            target_add_count=30,
        )
    )

    assert len(plan["buckets"]) == 2
    assert [bucket["quota"] for bucket in plan["buckets"]] == [15, 15]
    assert plan["media_plan"] == {"movie": 30}
    assert plan["country_plan"] == {"US": 15, "GB": 15}
    assert all(bucket["media_type"] == "movie" for bucket in plan["buckets"])
    assert all(bucket["year_min"] == 2022 and bucket["year_max"] == 2026 for bucket in plan["buckets"])


def test_plan_keeps_no_zero_quota_when_target_allows_all_pairs() -> None:
    plan = build_filter_replenish_plan(
        FilterReplenishIntent(
            countries=["US", "GB", "JP"],
            media_type="both",
            target_add_count=6,
        )
    )

    assert len(plan["buckets"]) == 6
    assert all(bucket["quota"] == 1 for bucket in plan["buckets"])
