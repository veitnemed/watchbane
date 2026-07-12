from dataset.add_title_service import (
    build_candidate_transfer_bundle,
    build_movie_record_from_defaults,
    build_preview_card_from_defaults,
    build_preview_movie_from_defaults,
    save_add_title_record,
)
from config import scheme


def test_build_api_defaults_uses_tmdb_scores_without_kp_imdb() -> None:
    from dataset.resolve.defaults import build_api_defaults

    defaults = build_api_defaults(
        {
            "title": "TMDb API Show",
            "year": 2021,
            "country": "США",
            "genres": ["Drama"],
            "tmdb_score": 8.0,
            "tmdb_votes": 2000,
            "tmdb_popularity": 33.3,
            "kp_score": 9.9,
            "imdb_score": 9.1,
        }
    )

    assert defaults[scheme.RAW_SCORES] == {
        "tmdb_score": 8.0,
        "tmdb_votes": 2000,
        "tmdb_popularity": 33.3,
    }
    assert "kp_score" not in defaults[scheme.RAW_SCORES]
    assert "imdb_score" not in defaults[scheme.RAW_SCORES]


def test_build_empty_add_defaults_does_not_create_external_rating_fields() -> None:
    from dataset.resolve.defaults import build_empty_add_defaults

    defaults = build_empty_add_defaults("Manual Title")

    assert defaults[scheme.RAW_SCORES] == {}


def test_build_movie_record_from_defaults_sets_score_from_defaults() -> None:
    defaults = {
        scheme.MAIN_INFO: {"title": "Test Show", "year": 2020, "user_score": None},
        scheme.RAW_SCORES: {
            "kp_score": 7.5,
            "kp_votes": 1000,
            "imdb_score": 8.0,
            "imdb_votes": 2000,
        },
        "genres_tmdb": ["Drama"],
    }

    movie = build_movie_record_from_defaults(defaults, 3)

    assert movie["main_info"]["title"] == "Test Show"
    assert movie["main_info"]["user_score"] == 3
    assert movie["main_info"]["year"] == 2020
    assert movie["raw_scores"]["imdb_score"] == 8.0


def test_build_preview_card_uses_genre_labels_ru() -> None:
    defaults = {
        scheme.MAIN_INFO: {"title": "Crime Show", "year": 2019, "user_score": None},
        scheme.RAW_SCORES: {},
        "genres_tmdb": ["Crime"],
    }
    resolved = {"source_values": {"description": "Test overview"}}
    card = build_preview_card_from_defaults(defaults, resolved=resolved)

    assert card["title"] == "Crime Show"
    assert card["year"] == 2019
    assert "Криминал" in (card.get("genres") or [])
    assert card.get("overview") == "Test overview"


def test_build_preview_card_downloads_poster_for_preview(monkeypatch) -> None:
    import tempfile
    from pathlib import Path

    defaults = {
        scheme.MAIN_INFO: {"title": "Poster Show", "year": 2020, "user_score": None},
        scheme.RAW_SCORES: {},
    }
    poster_hints = {
        "status": "found",
        "poster_url": "https://example.com/preview.jpg",
    }

    with tempfile.TemporaryDirectory() as temp_root:
        image_path = Path(temp_root) / "preview.jpg"

        def fake_download(url: str) -> str:
            image_path.write_bytes(b"poster")
            return str(image_path)

        monkeypatch.setattr(
            "posters.download_images.download_poster_url_for_preview",
            fake_download,
        )

        card = build_preview_card_from_defaults(defaults, poster_hints=poster_hints)

    assert card["poster_url"] == "https://example.com/preview.jpg"
    assert card["poster_src"] == str(image_path)
    assert card["poster_path"] == str(image_path)


def test_add_title_preview_card_profile_is_compact() -> None:
    import importlib

    import desktop.settings.app_settings  # noqa: F401
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(1.0)
    scaling._scale_tuning = {
        "ui": 1.0,
        "font": 1.0,
        "layout": 1.0,
        "control": 1.0,
        "list": 1.0,
        "detail": 1.0,
        "poster": 1.0,
    }
    profiles_module = importlib.reload(importlib.import_module("desktop.shared.detail.profiles"))
    profile = profiles_module.ADD_TITLE_PREVIEW_CARD_PROFILE
    detail_profile = profiles_module.DETAIL_CARD_LAYOUT_PROFILE

    assert profile.poster_width == profiles_module.POSTER_WIDTH // 2
    assert profile.poster_height == profiles_module.POSTER_HEIGHT // 2
    assert profile.show_user_score is False
    assert profile.include_bottom_stretch is False
    assert profile.rating_widget_size < detail_profile.rating_widget_size


def test_add_title_country_combo_has_any_default() -> None:
    from candidates.sources.tmdb.country_options import (
        ADD_TITLE_COUNTRY_ANY_LABEL,
        add_title_country_combo_options,
    )

    options = add_title_country_combo_options()
    assert options[0] == (ADD_TITLE_COUNTRY_ANY_LABEL, "")


def test_build_preview_movie_from_defaults() -> None:
    defaults = {
        scheme.MAIN_INFO: {"title": "Alpha", "year": 2020, "user_score": None},
        scheme.RAW_SCORES: {},
    }

    movie = build_preview_movie_from_defaults(defaults)

    assert movie["main_info"]["title"] == "Alpha"
    assert movie["main_info"]["user_score"] is None


def test_build_candidate_transfer_bundle_maps_candidate_fields() -> None:
    candidate = {
        "title": "Pool Show",
        "year": 2018,
        "country": "Россия",
        "tmdb_id": 123,
        "tmdb_score": 7.8,
        "tmdb_votes": 5000,
        "tmdb_popularity": 12.5,
        "overview": "Test overview",
        "genre_keys": ["drama"],
    }

    bundle = build_candidate_transfer_bundle(candidate)

    assert bundle.title == "Pool Show"
    assert bundle.pool_candidate == candidate
    assert bundle.defaults["main_info"]["year"] == 2018
    assert bundle.defaults["raw_scores"] == {
        "tmdb_score": 7.8,
        "tmdb_votes": 5000,
        "tmdb_popularity": 12.5,
    }
    assert "kp_score" not in bundle.defaults["raw_scores"]
    assert "imdb_score" not in bundle.defaults["raw_scores"]
    assert bundle.meta_payload.get("description") == "Test overview"
    assert bundle.meta_payload.get("tmdb_id") == 123
    assert bundle.preview_card["title"] == "Pool Show"


def test_build_candidate_transfer_bundle_keeps_pre_2000_year() -> None:
    candidate = {
        "title": "Friends",
        "year": 1994,
        "country_codes": ["US"],
        "tmdb_id": 1668,
        "tmdb_score": 8.4,
        "tmdb_votes": 8000,
        "tmdb_popularity": 80.0,
        "genre_keys": ["comedy"],
    }

    bundle = build_candidate_transfer_bundle(candidate)

    assert bundle.defaults["main_info"]["year"] == 1994
    assert bundle.preview_card["year"] == 1994


def test_save_add_title_record_passes_pool_candidate(monkeypatch) -> None:
    captured = {}

    def fake_add_movie(movie, **kwargs):
        captured["movie"] = movie
        captured["kwargs"] = kwargs

        class Result:
            ok = True
            message = "ok"
            title = movie["main_info"]["title"]

        return Result()

    monkeypatch.setattr("dataset.add_flow.save.add_movie", fake_add_movie)

    defaults = {
        scheme.MAIN_INFO: {"title": "From Pool", "year": 2020, "country": ""},
        scheme.RAW_SCORES: {},
    }
    pool_candidate = {"title": "From Pool", "year": 2020}

    save_add_title_record(defaults, 3, pool_candidate=pool_candidate)

    assert captured["kwargs"]["pool_candidate"] == pool_candidate


def test_save_add_title_record_accepts_friends_1994(monkeypatch) -> None:
    from dataset.records import add as records_add
    from candidates import title_state_service

    saved = {}
    meta = {}

    monkeypatch.setattr(records_add, "load_dataset", lambda: {})
    monkeypatch.setattr(records_add, "load_meta", lambda: meta)
    monkeypatch.setattr(
        records_add,
        "save_dataset_and_meta",
        lambda data, updated_meta: saved.update(data) or meta.update(updated_meta),
    )
    monkeypatch.setattr(
        title_state_service,
        "save_watched_dataset_transition",
        lambda data, updated_meta, _candidate: saved.update(data) or meta.update(updated_meta),
    )
    monkeypatch.setattr(records_add, "run_after_add_side_effects", lambda **_kwargs: [])

    defaults = {
        scheme.MAIN_INFO: {"title": "Friends", "year": 1994, "country": "US"},
        scheme.RAW_SCORES: {"tmdb_score": 8.4, "tmdb_votes": 8000},
    }

    result = save_add_title_record(defaults, 3, pool_candidate={"title": "Friends", "year": 1994})

    assert result.ok is True
    assert saved["Friends"]["main_info"]["year"] == 1994


def test_save_add_title_record_keeps_tmdb_scores_without_kp_imdb(monkeypatch) -> None:
    captured = {}

    def fake_add_movie(movie, **kwargs):
        captured["movie"] = movie
        captured["kwargs"] = kwargs

        class Result:
            ok = True
            message = "ok"
            title = movie["main_info"]["title"]

        return Result()

    monkeypatch.setattr("dataset.add_flow.save.add_movie", fake_add_movie)

    defaults = {
        scheme.MAIN_INFO: {"title": "TMDb Pool", "year": 2020, "country": "Россия"},
        scheme.RAW_SCORES: {"tmdb_score": 8.1, "tmdb_votes": 1200, "tmdb_popularity": 44.0},
    }

    save_add_title_record(defaults, 3, pool_candidate={"title": "TMDb Pool"})

    assert captured["movie"]["raw_scores"] == {
        "tmdb_score": 8.1,
        "tmdb_votes": 1200,
        "tmdb_popularity": 44.0,
    }
    assert "kp_score" not in captured["movie"]["raw_scores"]
    assert "imdb_score" not in captured["movie"]["raw_scores"]


def test_save_add_title_record_preserves_movie_media_type(monkeypatch) -> None:
    captured = {}

    def fake_add_movie(movie, **kwargs):
        captured["movie"] = movie
        captured["kwargs"] = kwargs

        class Result:
            ok = True
            message = "ok"
            title = movie["main_info"]["title"]

        return Result()

    monkeypatch.setattr("dataset.add_flow.save.add_movie", fake_add_movie)

    defaults = {
        scheme.MAIN_INFO: {
            "title": "Watchmen",
            "year": 2009,
            "country": "US",
            "media_type": "movie",
        },
        scheme.RAW_SCORES: {"tmdb_score": 7.3, "tmdb_votes": 9000},
    }

    save_add_title_record(defaults, 3)

    assert captured["movie"]["main_info"]["media_type"] == "movie"


def test_add_title_rejects_same_media_and_tmdb_id_under_localized_title(monkeypatch) -> None:
    from dataset.records import add as records_add

    existing = {
        "The Office": {
            "main_info": {
                "title": "The Office",
                "year": 2005,
                "country": "US",
                "media_type": "tv",
                "user_score": 3,
            }
        }
    }
    meta = {"The Office": {"tmdb_id": 2316}}
    saved = {"called": False}
    monkeypatch.setattr(records_add, "load_dataset", lambda: existing)
    monkeypatch.setattr(records_add, "load_meta", lambda: meta)
    monkeypatch.setattr(
        records_add,
        "save_dataset_and_meta",
        lambda *_args: saved.update(called=True),
    )

    defaults = {
        scheme.MAIN_INFO: {
            "title": "Офис",
            "year": 2005,
            "country": "US",
            "media_type": "tv",
        },
        scheme.RAW_SCORES: {"tmdb_score": 8.0},
    }
    result = save_add_title_record(defaults, 3, meta_payload={"tmdb_id": 2316})

    assert result.ok is False
    assert result.reason == "duplicate_tmdb_identity"
    assert saved["called"] is False


def test_add_title_keeps_movie_and_tv_with_same_tmdb_id_distinct(monkeypatch) -> None:
    from dataset.records import add as records_add

    existing = {
        "Shared": {
            "main_info": {
                "title": "Shared",
                "year": 2020,
                "country": "US",
                "media_type": "tv",
                "user_score": 2,
            }
        }
    }
    meta = {"Shared": {"tmdb_id": 42}}
    saved = {}
    monkeypatch.setattr(records_add, "load_dataset", lambda: existing)
    monkeypatch.setattr(records_add, "load_meta", lambda: meta)
    monkeypatch.setattr(
        records_add,
        "save_dataset_and_meta",
        lambda data, _meta: saved.update(data),
    )
    monkeypatch.setattr(records_add, "run_after_add_side_effects", lambda **_kwargs: [])

    defaults = {
        scheme.MAIN_INFO: {
            "title": "Shared",
            "year": 2020,
            "country": "US",
            "media_type": "movie",
        },
        scheme.RAW_SCORES: {"tmdb_score": 7.5},
    }
    result = save_add_title_record(defaults, 3, meta_payload={"tmdb_id": 42})

    assert result.ok is True
    assert any(
        record["main_info"]["media_type"] == "movie"
        for record in saved.values()
    )


def test_request_user_score_builds_payload_without_other_edits(monkeypatch) -> None:
    from ui.console import request as request_module

    defaults = {
        scheme.MAIN_INFO: {"title": "Console Show", "year": 2019, "country": "RU", "user_score": 2},
        scheme.RAW_SCORES: {"imdb_score": 8.1, "imdb_votes": 100},
        "genres_tmdb": ["Drama"],
    }

    monkeypatch.setattr(request_module, "loop_input_with_default", lambda **kwargs: "3")

    movie = request_module.request_user_score(defaults)

    assert movie["main_info"]["title"] == "Console Show"
    assert movie["main_info"]["year"] == 2019
    assert movie["main_info"]["country"] == "RU"
    assert movie["main_info"]["user_score"] == 3
    assert movie["raw_scores"]["imdb_score"] == 8.1
    assert movie.get("genres_tmdb") == ["Drama"]
