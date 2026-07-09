from __future__ import annotations

from candidates.search.document import DOCUMENT_VERSION, build_search_document


def _candidate(**overrides):
    base = {
        "title": "Бригада",
        "original_title": "Brigada",
        "localized": {
            "ru": {"title": "Бригада", "overview": "<p>Криминальная драма о банде.</p>"},
            "en": {"title": "Brigada", "overview": "Crime drama about a gang."},
        },
        "genres_tmdb": ["Crime", "Drama"],
        "genre_keys": ["crime", "drama"],
        "country_codes": ["RU"],
        "countries": ["Россия"],
        "actors_top": [
            {"name": "Сергей Безруков"},
            {"name": "Владимир Вдовиченков"},
            {"name": "Андрей Панин"},
            {"name": "Лишний актёр"},
        ],
    }
    base.update(overrides)
    return base


def test_build_search_document_includes_titles_genres_countries_cast() -> None:
    document = build_search_document(_candidate(), data_language="ru")

    assert "бригада" in document
    assert "brigada" in document
    assert "криминал" in document or "драма" in document
    assert "ru" in document
    assert "россия" in document
    assert "сергей безруков" in document
    assert "лишний актёр" not in document


def test_build_search_document_truncates_overview_and_strips_html() -> None:
    long_overview = "А" * 300
    document = build_search_document(
        _candidate(localized={"ru": {"overview": f"<b>{long_overview}</b>"}}),
        data_language="ru",
    )

    assert "<" not in document
    assert "а" * 201 not in document


def test_build_search_document_dedupes_tokens() -> None:
    document = build_search_document(
        _candidate(title="Метод", localized={"ru": {"title": "Метод"}}),
        data_language="ru",
    )

    assert document.count("метод") == 1


def test_document_version_is_stable() -> None:
    assert DOCUMENT_VERSION == 1
