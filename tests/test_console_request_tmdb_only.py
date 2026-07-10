from config import constant
from config import scheme
from ui.console import request


def _defaults(title: str = "Show") -> dict:
    return {
        scheme.MAIN_INFO: {
            "title": title,
            "user_score": None,
            "year": 2020,
            "country": "США",
        },
        scheme.RAW_SCORES: {
            "tmdb_score": 7.8,
            "tmdb_votes": 1200,
            "tmdb_popularity": 44.2,
        },
        scheme.GENRE: {feature: 0 for feature in constant.GENRE},
    }


def _resolved(found: bool = True) -> dict:
    defaults = _defaults("TMDb Show") if found else None
    return {
        "title": "Input Show",
        "country": "США",
        "found": found,
        "tmdb_data": {
            "title": "TMDb Show",
            "year": 2020,
            "tmdb_score": 7.8,
            "tmdb_votes": 1200,
            "tmdb_popularity": 44.2,
            "overview": "TMDb overview.",
            "imdb_id": "tt1234567",
        } if found else None,
        "tmdb_error": None if found else {"error": "not_found"},
        "defaults": defaults,
        "sources": {
            "tmdb_score": "tmdb_api",
            "tmdb_votes": "tmdb_api",
            "tmdb_popularity": "tmdb_api",
            "genres": "tmdb_api",
            "description": "tmdb_api",
        },
        "source_values": {
            "genres": ["Drama"],
            "description": "TMDb overview.",
        },
        "statuses": {"tmdb_api": "найдено" if found else "не найдено"},
    }


def test_format_source_is_tmdb_only() -> None:
    assert request.format_source("tmdb_api") == "TMDb API"
    assert request.format_source("input") == "ручной ввод"
    assert request.format_source("manual") == "ручной ввод"
    assert request.format_source("kp_api") == "не заполнено"
    assert request.format_source("imdb_sql") == "не заполнено"


def test_print_autofill_status_contains_only_tmdb_public_sources(capsys) -> None:
    request.print_autofill_status(
        _resolved(),
        manual_mode=False,
        poster_hints={"poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg"},
    )

    output = capsys.readouterr().out
    assert "TMDb API" in output
    assert "TMDb score" in output
    assert "TMDb votes" in output
    assert "TMDb popularity" in output
    assert "Постер: найден poster_url" in output
    assert "SQL" not in output
    assert "KP" not in output
    assert "IMDb" not in output


def test_resolve_title_for_add_tmdb_success(monkeypatch, capsys) -> None:
    resolved = _resolved()
    meta_payload = {"poster_path": "/poster.jpg"}
    poster_hints = {"poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg"}

    monkeypatch.setattr(request.service, "resolve_title_data_for_add", lambda *_args, **_kwargs: resolved)
    monkeypatch.setattr(request.service, "build_add_meta_payload", lambda _resolved: meta_payload)
    monkeypatch.setattr(request.service, "build_poster_hints_from_resolve", lambda _resolved: poster_hints)
    monkeypatch.setattr(request.title_presenters, "print_final_add_preview", lambda _defaults: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "yes")

    defaults, meta, posters = request.resolve_title_for_add("Input Show", "США")

    assert defaults == resolved["defaults"]
    assert meta == meta_payload
    assert posters == poster_hints
    output = capsys.readouterr().out
    assert "TMDb нашёл объект" in output
    assert "IMDb ID" not in output
    assert "KP" not in output
    assert "SQL" not in output


def test_resolve_title_for_add_passes_movie_media_type(monkeypatch) -> None:
    captured = {}
    resolved = _resolved()
    resolved["defaults"][scheme.MAIN_INFO]["media_type"] = "movie"

    def fake_resolve(title, country, **kwargs):
        captured.update(kwargs)
        return resolved

    monkeypatch.setattr(request.service, "resolve_title_data_for_add", fake_resolve)
    monkeypatch.setattr(request.service, "build_add_meta_payload", lambda _resolved: {})
    monkeypatch.setattr(request.service, "build_poster_hints_from_resolve", lambda _resolved: {})
    monkeypatch.setattr(request.title_presenters, "print_final_add_preview", lambda _defaults: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "yes")

    defaults, _meta, _posters = request.resolve_title_for_add("Input Movie", "US", media_type="movie")

    assert captured["media_type"] == "movie"
    assert defaults[scheme.MAIN_INFO]["media_type"] == "movie"


def test_resolve_title_for_add_manual_fallback(monkeypatch, capsys) -> None:
    resolved = _resolved(found=False)
    poster_hints = {}
    meta_payload = {}

    monkeypatch.setattr(request.service, "resolve_title_data_for_add", lambda *_args, **_kwargs: resolved)
    monkeypatch.setattr(request.service, "build_add_meta_payload", lambda _resolved: meta_payload)
    monkeypatch.setattr(request.service, "build_poster_hints_from_resolve", lambda _resolved: poster_hints)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")

    defaults, meta, posters = request.resolve_title_for_add("Input Show", "США")

    assert defaults[scheme.MAIN_INFO]["title"] == "Input Show"
    assert defaults[scheme.MAIN_INFO]["country"] == "США"
    assert meta == meta_payload
    assert posters == poster_hints
    output = capsys.readouterr().out
    assert "TMDb не нашёл объект" in output
    assert "ручная разметка" in output
    assert "KP" not in output
    assert "IMDb" not in output


def test_resolve_title_for_add_manual_fallback_preserves_movie_media_type(monkeypatch) -> None:
    resolved = _resolved(found=False)

    monkeypatch.setattr(request.service, "resolve_title_data_for_add", lambda *_args, **_kwargs: resolved)
    monkeypatch.setattr(request.service, "build_add_meta_payload", lambda _resolved: {})
    monkeypatch.setattr(request.service, "build_poster_hints_from_resolve", lambda _resolved: {})
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")

    defaults, _meta, _posters = request.resolve_title_for_add("Input Movie", "US", media_type="movie")

    assert defaults[scheme.MAIN_INFO]["media_type"] == "movie"
