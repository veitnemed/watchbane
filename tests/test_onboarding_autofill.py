from __future__ import annotations

from collections import Counter
from itertools import combinations
from datetime import date

from candidates.onboarding import autofill
from candidates.onboarding.autofill import (
    MEDIA_MOVIE,
    MEDIA_TV,
    OnboardingTasteProfile,
    build_country_plan,
    build_discover_request,
    build_fetch_buckets,
    country_selection_for_foreign_ru,
    country_selection_for_manual,
    country_selection_for_mixed_ru,
    media_weights,
    origin_weights,
    release_weights,
    resolve_tmdb_genre_ids,
    run_onboarding_autofill,
    vibe_weights,
)
from storage.sqlite.connection import connect
from storage.sqlite.onboarding_repository import load_autofill_request_audits


MOVIE_GENRES = [
    {"id": 35, "name": "Comedy"},
    {"id": 10749, "name": "Romance"},
    {"id": 14, "name": "Fantasy"},
    {"id": 10751, "name": "Family"},
    {"id": 12, "name": "Adventure"},
    {"id": 18, "name": "Drama"},
    {"id": 53, "name": "Thriller"},
    {"id": 28, "name": "Action"},
    {"id": 80, "name": "Crime"},
    {"id": 9648, "name": "Mystery"},
]
TV_GENRES = [
    {"id": 35, "name": "Comedy"},
    {"id": 10751, "name": "Family"},
    {"id": 16, "name": "Animation"},
    {"id": 10765, "name": "Sci-Fi & Fantasy"},
    {"id": 18, "name": "Drama"},
    {"id": 80, "name": "Crime"},
    {"id": 9648, "name": "Mystery"},
    {"id": 10759, "name": "Action & Adventure"},
    {"id": 10768, "name": "War & Politics"},
]


class FakeTmdbClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def movie_genres(self, language: str = "en") -> list[dict]:
        assert language == "en"
        return list(MOVIE_GENRES)

    def tv_genres(self, language: str = "en") -> list[dict]:
        assert language == "en"
        return list(TV_GENRES)

    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        media = MEDIA_MOVIE if endpoint == "/discover/movie" else MEDIA_TV
        call_index = len(self.calls)
        genre_text = str(params.get("with_genres") or "")
        genre_ids = [int(item) for item in genre_text.split("|") if item.isdigit()]
        if not genre_ids:
            genre_ids = [35] if media == MEDIA_MOVIE else [18]
        country = params.get("with_origin_country") or "US"
        results = []
        for index in range(20):
            tmdb_id = call_index * 1000 + index
            year = int(params.get("primary_release_year") or params.get("first_air_date_year") or 2024)
            if media == MEDIA_MOVIE:
                results.append(
                    {
                        "id": tmdb_id,
                        "title": f"Movie {tmdb_id}",
                        "original_title": f"Movie {tmdb_id}",
                        "release_date": f"{year}-01-01",
                        "poster_path": f"/m{tmdb_id}.jpg",
                        "overview": "Overview",
                        "genre_ids": genre_ids,
                        "origin_country": [country],
                        "vote_average": 7.2,
                        "vote_count": 1200,
                        "popularity": 50,
                        "original_language": params.get("with_original_language") or "en",
                    }
                )
            else:
                results.append(
                    {
                        "id": tmdb_id,
                        "name": f"Series {tmdb_id}",
                        "original_name": f"Series {tmdb_id}",
                        "first_air_date": f"{year}-01-01",
                        "origin_country": [country],
                        "poster_path": f"/t{tmdb_id}.jpg",
                        "overview": "Overview",
                        "genre_ids": genre_ids,
                        "vote_average": 7.1,
                        "vote_count": 500,
                        "popularity": 40,
                        "original_language": params.get("with_original_language") or "en",
                    }
                )
        return {"results": results, "total_pages": 1}


class EmptyTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        return {"results": [], "total_pages": 1}


class ScarceTvTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        if endpoint == "/discover/tv":
            self.calls.append((endpoint, dict(params)))
            return {"results": [], "total_pages": 1}
        return super().discover(endpoint, params)


class FutureTmdbClient(FakeTmdbClient):
    def discover(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        media = MEDIA_MOVIE if endpoint == "/discover/movie" else MEDIA_TV
        date_key = "release_date" if media == MEDIA_MOVIE else "first_air_date"
        title_key = "title" if media == MEDIA_MOVIE else "name"
        original_title_key = "original_title" if media == MEDIA_MOVIE else "original_name"
        results = []
        for index in range(20):
            tmdb_id = len(self.calls) * 1000 + index
            results.append(
                {
                    "id": tmdb_id,
                    title_key: f"Future {tmdb_id}",
                    original_title_key: f"Future {tmdb_id}",
                    date_key: "2027-01-01",
                    "poster_path": f"/f{tmdb_id}.jpg",
                    "overview": "Overview",
                    "genre_ids": [35],
                    "vote_average": 7.2,
                    "vote_count": 1200,
                    "popularity": 50,
                    "original_language": params.get("with_original_language") or "en",
                    "origin_country": ["RU"] if params.get("with_origin_country") == "RU" else ["US"],
                }
            )
        return {"results": results, "total_pages": 1}


def _profile(**overrides) -> OnboardingTasteProfile:
    data = {
        "media_preference": "both",
        "release_preference": "mixed",
        "vibe_preference": "mixed",
        "origin_preference": None,
        "ui_language": "en",
    }
    data.update(overrides)
    return OnboardingTasteProfile(**data)


def _quota_by(buckets, field: str) -> Counter:
    result = Counter()
    for bucket in buckets:
        result[getattr(bucket, field)] += bucket.quota
    return result


def test_media_preference_quota_weights_are_fixed_70_30_and_50_50() -> None:
    assert media_weights("movie") == {MEDIA_MOVIE: 0.70, MEDIA_TV: 0.30}
    assert media_weights("tv") == {MEDIA_MOVIE: 0.30, MEDIA_TV: 0.70}
    assert media_weights("both") == {MEDIA_MOVIE: 0.50, MEDIA_TV: 0.50}
    assert _quota_by(build_fetch_buckets(_profile(media_preference="movie")), "media_type") == {MEDIA_MOVIE: 84, MEDIA_TV: 36}
    assert _quota_by(build_fetch_buckets(_profile(media_preference="tv")), "media_type") == {MEDIA_MOVIE: 36, MEDIA_TV: 84}
    assert _quota_by(build_fetch_buckets(_profile(media_preference="both")), "media_type") == {MEDIA_MOVIE: 60, MEDIA_TV: 60}


def test_release_preferences_create_required_era_buckets_and_year_order() -> None:
    assert release_weights("classic") == {"top_all_time": 0.40, "classic_sweep": 0.60}
    assert release_weights("new") == {"top_all_time": 0.30, "new_sweep": 0.70}
    classic_buckets = build_fetch_buckets(_profile(release_preference="classic"))
    assert {bucket.era for bucket in classic_buckets} == {"top_all_time", "classic_sweep"}
    classic = next(bucket for bucket in classic_buckets if bucket.era == "classic_sweep")
    endpoint, params = build_discover_request(classic, profile=_profile(release_preference="classic"), fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert endpoint in {"/discover/movie", "/discover/tv"}
    assert (params.get("primary_release_year") or params.get("first_air_date_year")) == 2005
    new = next(bucket for bucket in build_fetch_buckets(_profile(release_preference="new")) if bucket.era == "new_sweep")
    _endpoint, params = build_discover_request(new, profile=_profile(release_preference="new"), fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert (params.get("primary_release_year") or params.get("first_air_date_year")) == 2026


def test_vibe_preference_quotas_are_70_30_and_50_50() -> None:
    assert vibe_weights("light") == {"light": 0.70, "dark": 0.30}
    assert vibe_weights("dark") == {"light": 0.30, "dark": 0.70}
    assert vibe_weights("mixed") == {"light": 0.50, "dark": 0.50}
    assert _quota_by(build_fetch_buckets(_profile(vibe_preference="light")), "vibe") == {"light": 84, "dark": 36}
    assert _quota_by(build_fetch_buckets(_profile(vibe_preference="dark")), "vibe") == {"light": 36, "dark": 84}


def test_country_selection_presets_create_contract_quotas() -> None:
    assert build_country_plan(country_selection_for_foreign_ru(), 120) == {"US": 108, "GB": 12}
    assert build_country_plan(country_selection_for_mixed_ru(), 120) == {"RU": 18, "US": 102}
    assert build_country_plan(country_selection_for_manual("RU", ["US", "KR"]), 120) == {"US": 84, "KR": 36}
    assert build_country_plan(country_selection_for_manual("RU", ["US", "KR"], ratio_preset="90/10"), 120) == {"US": 108, "KR": 12}
    assert build_country_plan(country_selection_for_manual("RU", ["US", "RU", "GB"]), 120) == {"US": 40, "RU": 40, "GB": 40}
    assert build_country_plan(country_selection_for_manual("RU", ["US", "RU", "GB", "KR", "JP"]), 120) == {
        "US": 24,
        "RU": 24,
        "GB": 24,
        "KR": 24,
        "JP": 24,
    }


def test_country_first_profile_replaces_broad_origin_defaults() -> None:
    assert origin_weights("foreign", ui_language="ru") == {"domestic": 0.30, "foreign": 0.70}
    assert origin_weights(None, ui_language="en") == {"any": 1.0}
    foreign_countries = _quota_by(build_fetch_buckets(_profile(ui_language="ru", origin_preference="foreign")), "target_country")
    mixed_countries = _quota_by(build_fetch_buckets(_profile(ui_language="ru", origin_preference="mixed")), "target_country")
    en_countries = _quota_by(build_fetch_buckets(_profile(ui_language="en")), "target_country")
    assert foreign_countries == {"US": 108, "GB": 12}
    assert mixed_countries == {"RU": 18, "US": 102}
    assert en_countries == {"US": 108, "GB": 12}


def test_bucket_quotas_sum_exactly_to_target() -> None:
    profile = _profile(media_preference="movie", release_preference="new", vibe_preference="dark", ui_language="ru", origin_preference="foreign")
    buckets = build_fetch_buckets(profile)
    assert sum(bucket.quota for bucket in buckets) == autofill.STARTER_POOL_TARGET


def test_tmdb_genre_ids_are_resolved_from_genre_lists_and_joined_with_pipe() -> None:
    client = FakeTmdbClient()
    genre_ids = resolve_tmdb_genre_ids(client)
    assert genre_ids[MEDIA_MOVIE]["light"] == (35, 10749, 14, 10751, 12)
    assert genre_ids[MEDIA_TV]["dark"] == (18, 80, 9648, 10759, 10768)
    bucket = next(bucket for bucket in build_fetch_buckets(_profile(vibe_preference="light"), genre_ids=genre_ids) if bucket.vibe == "light")
    _endpoint, params = build_discover_request(bucket, profile=_profile(vibe_preference="light"), fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert "," not in params["with_genres"]
    assert "|" in params["with_genres"]


def test_discover_params_use_media_specific_contract() -> None:
    movie = next(bucket for bucket in build_fetch_buckets(_profile(media_preference="movie", release_preference="new")) if bucket.media_type == MEDIA_MOVIE and bucket.era == "new_sweep")
    endpoint, params = build_discover_request(movie, profile=_profile(media_preference="movie", release_preference="new"), fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert endpoint == "/discover/movie"
    assert params["with_origin_country"] == movie.target_country
    assert params["primary_release_year"] == 2026
    assert params["primary_release_date.lte"] == "2026-07-08"
    assert params["include_adult"] is False
    tv = next(bucket for bucket in build_fetch_buckets(_profile(media_preference="tv", release_preference="new")) if bucket.media_type == MEDIA_TV and bucket.era == "new_sweep")
    endpoint, params = build_discover_request(tv, profile=_profile(media_preference="tv", release_preference="new"), fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert endpoint == "/discover/tv"
    assert params["with_origin_country"] == tv.target_country
    assert params["first_air_date_year"] == 2026
    assert params["first_air_date.lte"] == "2026-07-08"


def test_country_first_fallback_keeps_origin_country_before_genres_and_votes() -> None:
    assert autofill.FALLBACK_ORDER.index("relax_origin") < autofill.FALLBACK_ORDER.index("relax_genres")
    assert autofill.FALLBACK_ORDER.index("relax_genres") < autofill.FALLBACK_ORDER.index("relax_votes_mid")
    profile = _profile(ui_language="ru", origin_preference="domestic", vibe_preference="light")
    genre_ids = resolve_tmdb_genre_ids(FakeTmdbClient())
    bucket = next(bucket for bucket in build_fetch_buckets(profile, genre_ids=genre_ids) if bucket.target_country == "RU" and bucket.genre_ids)
    _endpoint, base = build_discover_request(bucket, profile=profile, fallback="base", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    _endpoint, relaxed_origin = build_discover_request(bucket, profile=profile, fallback="relax_origin", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    _endpoint, relaxed_genres = build_discover_request(bucket, profile=profile, fallback="relax_genres", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    _endpoint, relaxed_era = build_discover_request(bucket, profile=profile, fallback="relax_era", request_index=0, current_year=2026, current_date=date(2026, 7, 8))
    assert base["with_origin_country"] == "RU"
    assert relaxed_origin["with_origin_country"] == "RU"
    assert "with_genres" in relaxed_origin
    assert relaxed_genres["with_origin_country"] == "RU"
    assert "with_genres" not in relaxed_genres
    assert relaxed_era["with_origin_country"] == "RU"
    assert "with_original_language" not in relaxed_era


def test_onboarding_wizard_starts_with_country_question_for_all_languages(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    ru_dialog = OnboardingAutofillDialog(ui_language="ru")
    en_dialog = OnboardingAutofillDialog(ui_language="en")
    try:
        assert len(ru_dialog._active_questions()) == 4
        assert len(en_dialog._active_questions()) == 4
        assert ru_dialog._active_questions()[0].key == "country_selection"
        assert en_dialog._active_questions()[0].key == "country_selection"
    finally:
        ru_dialog.close()
        en_dialog.close()


def test_onboarding_wizard_profile_contains_explicit_country_selection(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        dialog._answers["country_selection"] = ["US", "GB"]
        profile = dialog._profile()
        assert profile["origin_preference"] == "foreign"
        assert profile["country_selection"]["selected_countries"] == ["US", "GB"]
        assert profile["country_selection"]["country_weights"] == {"US": 0.50, "GB": 0.50}
        assert profile["country_selection"]["exclude_home_country"] is False
        assert profile["country_selection"]["max_countries"] == 5
    finally:
        dialog.close()


def test_onboarding_wizard_country_buttons_use_localized_names(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    ru_dialog = OnboardingAutofillDialog(ui_language="ru")
    en_dialog = OnboardingAutofillDialog(ui_language="en")
    try:
        ru_labels = [button.text() for button in ru_dialog._question_pages[0][2].buttons()]
        en_labels = [button.text() for button in en_dialog._question_pages[0][2].buttons()]

        assert ru_labels == ["США", "Россия", "Великобритания", "Южная Корея", "Япония"]
        assert all(code not in " ".join(ru_labels) for code in ("RU", "US", "GB", "KR", "JP"))
        assert en_labels == [
            "United States",
            "Russia",
            "United Kingdom",
            "South Korea",
            "Japan",
        ]
        assert "US + GB" not in " ".join(en_labels)
        assert "RU" not in " ".join(en_labels)
    finally:
        ru_dialog.close()
        en_dialog.close()


def test_onboarding_wizard_country_buttons_are_multi_select(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        dialog._set_page(1)
        group = dialog._question_pages[0][2]
        buttons = {button.property("answer"): button for button in group.buttons()}

        assert group.exclusive() is False
        assert buttons["US"].isChecked() is True
        buttons["RU"].click()
        buttons["GB"].click()

        assert dialog._answers["country_selection"] == ["US", "RU", "GB"]
        assert dialog._selected_answer(dialog._question_pages[0][0], group) == ["US", "RU", "GB"]
    finally:
        dialog.close()


def test_onboarding_wizard_defaults_to_us_only_without_ru(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        profile = dialog._profile()

        assert profile["origin_preference"] == "foreign"
        assert profile["country_selection"]["selected_countries"] == ["US"]
        assert profile["country_selection"]["country_weights"] == {"US": 1.0}
        assert profile["country_selection"]["exclude_home_country"] is False
        assert profile["country_selection"]["primary_country"] == "US"
    finally:
        dialog.close()


def test_onboarding_wizard_supports_all_country_chip_combinations(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    codes = ("US", "RU", "GB", "KR", "JP")
    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        for size in range(1, len(codes) + 1):
            for combo in combinations(codes, size):
                dialog._answers["country_selection"] = list(combo)
                selection = dialog._country_selection_payload()
                plan = build_country_plan(autofill._coerce_country_selection(
                    selection,
                    ui_language="ru",
                    origin_preference=dialog._profile()["origin_preference"],
                ), 120)

                assert selection["selected_countries"] == list(combo)
                assert set(selection["country_weights"]) == set(combo)
                assert sum(plan.values()) == 120
                assert set(plan) == set(combo)
    finally:
        dialog.close()


def test_onboarding_wizard_scale_preview_has_sample_widgets(qapp) -> None:
    from PyQt6.QtWidgets import QFrame, QLabel, QPushButton

    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        preview = dialog.findChild(QFrame, "onboardingScalePreview")
        action = dialog.findChild(QPushButton, "onboardingScalePreviewAction")
        chips = dialog.findChildren(QLabel, "onboardingScalePreviewChip")

        assert preview is not None
        assert action is not None
        assert action.text() == "Кнопка"
        assert [chip.text() for chip in chips] == ["Страна", "Жанр", "Оценка"]
    finally:
        dialog.close()


def test_onboarding_wizard_plan_summary_localizes_country_counts(qapp) -> None:
    from desktop.onboarding import OnboardingAutofillDialog

    dialog = OnboardingAutofillDialog(ui_language="ru")
    try:
        dialog._answers["country_selection"] = ["US", "GB"]
        summary = dialog._format_plan_summary()

        assert "Страны: США: 60, Великобритания: 60" in summary
        assert "US:" not in summary
        assert "GB:" not in summary
    finally:
        dialog.close()


def test_run_autofill_uses_mocked_tmdb_and_persists_profile_audit_and_candidates(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    client = FakeTmdbClient()

    result = run_onboarding_autofill(_profile(media_preference="both"), client=client, path=db_path, current_year=2026)

    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert result.api_requests <= autofill.MAX_TMDB_REQUESTS
    assert client.calls
    conn = connect(db_path)
    try:
        profile_count = conn.execute("SELECT COUNT(*) AS count FROM onboarding_profiles").fetchone()["count"]
        request_count = conn.execute("SELECT COUNT(*) AS count FROM candidate_autofill_requests").fetchone()["count"]
        candidate_count = conn.execute("SELECT COUNT(*) AS count FROM candidate_records").fetchone()["count"]
        media_counts = {
            row["media_type"]: row["count"]
            for row in conn.execute("SELECT media_type, COUNT(*) AS count FROM candidate_records GROUP BY media_type")
        }
        assert profile_count == 1
        assert request_count == result.api_requests + result.duplicate_requests_skipped
        assert candidate_count == autofill.STARTER_POOL_TARGET
        assert media_counts[MEDIA_MOVIE] == 60
        assert media_counts[MEDIA_TV] == 60
        row = conn.execute("SELECT source, source_bucket_id, onboarding_profile_id, candidate_score, fetch_rank FROM candidate_records LIMIT 1").fetchone()
        assert row["source"] == "onboarding_autofill"
        assert row["source_bucket_id"]
        assert row["onboarding_profile_id"] == result.profile_id
        assert row["candidate_score"] > 0
        assert row["fetch_rank"] > 0
        assert len(client.calls) == result.api_requests
        assert len({autofill.canonical_discover_request_key(endpoint, params) for endpoint, params in client.calls}) == result.api_requests
    finally:
        conn.close()


def test_run_autofill_keeps_tv_quota_when_tv_is_preferred(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    result = run_onboarding_autofill(
        _profile(media_preference="tv"),
        client=FakeTmdbClient(),
        path=db_path,
        current_year=2026,
    )

    assert result.created_count == autofill.STARTER_POOL_TARGET
    assert result.planned_counts["media_type"] == {MEDIA_MOVIE: 36, MEDIA_TV: 84}
    assert result.actual_counts["media_type"] == {MEDIA_MOVIE: 36, MEDIA_TV: 84}
    assert result.warning is None


def test_run_autofill_underfills_scarce_tv_without_movie_overfill(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    result = run_onboarding_autofill(
        _profile(media_preference="tv"),
        client=ScarceTvTmdbClient(),
        path=db_path,
        current_year=2026,
    )

    assert result.planned_counts["media_type"] == {MEDIA_MOVIE: 36, MEDIA_TV: 84}
    assert result.actual_counts["media_type"].get(MEDIA_MOVIE) == 36
    assert result.actual_counts["media_type"].get(MEDIA_TV, 0) == 0
    assert result.created_count == 36
    assert "Media quota underfilled: tv planned 84, actual 0." in result.warnings


def test_future_or_unreleased_results_are_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    result = run_onboarding_autofill(
        _profile(media_preference="movie", release_preference="new"),
        client=FutureTmdbClient(),
        path=db_path,
        current_year=2026,
    )

    assert result.created_count == 0
    assert result.rejected_future_count > 0
    assert any(warning.startswith("Rejected future/unreleased titles:") for warning in result.warnings)


def test_onboarding_plan_view_has_target_quotas_without_api_calls() -> None:
    from candidates import service

    plan = service.get_onboarding_autofill_plan_view({
        "media_preference": "movie",
        "release_preference": "new",
        "vibe_preference": "dark",
        "origin_preference": "foreign",
        "ui_language": "ru",
    })

    assert plan["target"] == autofill.STARTER_POOL_TARGET
    assert plan["quotas"]["media_type"][MEDIA_MOVIE] == 84
    assert plan["quotas"]["media_type"][MEDIA_TV] == 36
    assert plan["quotas"]["country"] == {"US": 108, "GB": 12}
    assert plan["country_plan"] == {"US": 108, "GB": 12}
    assert plan["country_selection"]["exclude_home_country"] is True
    assert plan["quotas"]["origin"] == {"foreign": 120}


def test_candidate_identity_is_media_type_plus_tmdb_id() -> None:
    index = {"tmdb_identities": {(MEDIA_MOVIE, 7)}, "media_title_year_keys": set()}
    movie = {"id": 7, "title": "Seven", "release_date": "1995-01-01"}
    tv = {"id": 7, "name": "Seven", "first_air_date": "1995-01-01"}
    assert autofill.discover_item_existing_reason(movie, index, media_type=MEDIA_MOVIE) == "tmdb_id"
    assert autofill.discover_item_existing_reason(tv, index, media_type=MEDIA_TV) is None


def test_watched_existing_and_hidden_candidates_are_skipped(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    bucket = build_fetch_buckets(_profile(media_preference="movie"))[0]
    result = {
        "id": 42,
        "title": "Skip Me",
        "release_date": "2024-01-01",
        "poster_path": "/p.jpg",
        "vote_average": 7.0,
        "vote_count": 2000,
    }
    assert autofill.accept_candidate(
        result,
        bucket,
        existing_index={"tmdb_identities": {(bucket.media_type, 42)}, "media_title_year_keys": set()},
        accepted_identities=set(),
        hidden_or_rejected_identities=set(),
        watched_signatures=set(),
        dataset_title_keys=set(),
    ) is False

    assert autofill.accept_candidate(
        result,
        bucket,
        existing_index={"tmdb_identities": set(), "media_title_year_keys": set()},
        accepted_identities={(bucket.media_type, 42)},
        hidden_or_rejected_identities=set(),
        watched_signatures=set(),
        dataset_title_keys=set(),
    ) is False

    assert autofill.accept_candidate(
        result,
        bucket,
        existing_index={"tmdb_identities": set(), "media_title_year_keys": set()},
        accepted_identities=set(),
        hidden_or_rejected_identities={"skip me|2024"},
        watched_signatures=set(),
        dataset_title_keys=set(),
    ) is False


def test_autofill_can_be_cancelled_before_api_requests(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    client = FakeTmdbClient()

    result = run_onboarding_autofill(
        _profile(),
        client=client,
        path=tmp_path / "watchbane.sqlite3",
        cancel_checker=lambda: True,
    )

    assert result.cancelled is True
    assert result.created_count == 0
    assert result.api_requests == 0


def test_request_audit_rows_are_loadable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    db_path = tmp_path / "watchbane.sqlite3"
    result = run_onboarding_autofill(_profile(), client=EmptyTmdbClient(), path=db_path)

    audits = load_autofill_request_audits(result.profile_id, path=db_path)

    assert result.created_count == 0
    assert len(audits) == result.api_requests + result.duplicate_requests_skipped
    assert sum(1 for audit in audits if audit["status"] == "skipped_duplicate") == result.duplicate_requests_skipped
    assert audits[0]["endpoint"] in {"/discover/movie", "/discover/tv"}
    assert isinstance(audits[0]["params"], dict)
