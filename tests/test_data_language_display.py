"""C3-08: consistent RU metadata selection and fallback (QA-DEFECT-02)."""

from __future__ import annotations

import copy

from dataset.language import (
    build_localized_block_from_legacy,
    choose_display_overview,
    choose_display_title,
)
from desktop.candidates.presenters import build_candidate_readonly_card


def test_ru_complete_fixture_displays_russian() -> None:
    record = {
        "title": "Breaking Bad",
        "overview": "English leftover",
        "original_title": "Breaking Bad",
        "localized": {
            "ru": {
                "title": "Во все тяжкие",
                "overview": "Учитель химии начинает варить мет.",
            },
            "en": {
                "title": "Breaking Bad",
                "overview": "A chemistry teacher starts cooking meth.",
            },
        },
    }
    assert choose_display_title(record, "ru") == "Во все тяжкие"
    assert choose_display_overview(record, "ru") == "Учитель химии начинает варить мет."
    card = build_candidate_readonly_card(record, data_language="ru")
    assert card["title"] == "Во все тяжкие"
    assert "Учитель химии" in (card.get("overview") or card.get("description") or "")


def test_ru_title_missing_ru_overview_uses_en_overview() -> None:
    record = {
        "title": "Breaking Bad",
        "overview": "",
        "localized": {
            "ru": {"title": "Во все тяжкие", "overview": ""},
            "en": {
                "title": "Breaking Bad",
                "overview": "A chemistry teacher starts cooking meth.",
            },
        },
    }
    assert choose_display_title(record, "ru") == "Во все тяжкие"
    assert choose_display_overview(record, "ru") == "A chemistry teacher starts cooking meth."


def test_missing_ru_complete_en_uses_english_fallback() -> None:
    record = {
        "title": "",
        "overview": "",
        "localized": {
            "en": {
                "title": "Better Call Saul",
                "overview": "English overview only.",
            }
        },
    }
    assert choose_display_title(record, "ru") == "Better Call Saul"
    assert choose_display_overview(record, "ru") == "English overview only."


def test_missing_ru_and_en_uses_original() -> None:
    record = {
        "title": "",
        "overview": "",
        "original_title": "進撃の巨人",
        "original_name": "進撃の巨人",
        "description": "オリジナルあらすじ",
    }
    assert choose_display_title(record, "ru") == "進撃の巨人"
    assert choose_display_overview(record, "ru") == "オリジナルあらすじ"


def test_empty_ru_overview_does_not_blank_en_fallback() -> None:
    record = {
        "localized": {
            "ru": {"title": "Во все тяжкие", "overview": "   "},
            "en": {"title": "Breaking Bad", "overview": "English overview"},
        },
        "overview": "",
        "description": "",
    }
    assert choose_display_overview(record, "ru") == "English overview"


def test_stale_en_top_level_with_ru_localized_prefers_ru() -> None:
    record = {
        "title": "Breaking Bad",
        "overview": "English cached overview",
        "localized": {
            "ru": {
                "title": "Во все тяжкие",
                "overview": "Русское описание из TMDb.",
            },
            "en": {
                "title": "Breaking Bad",
                "overview": "English cached overview",
            },
        },
    }
    assert choose_display_title(record, "ru") == "Во все тяжкие"
    assert choose_display_overview(record, "ru") == "Русское описание из TMDb."


def test_stale_en_top_level_prefers_en_block_when_ru_missing() -> None:
    """Stale EN primary with only localized.en: RU data language still shows EN (not blank)."""
    record = {
        "title": "Breaking Bad",
        "overview": "English cached overview",
        "localized": {
            "en": {
                "title": "Breaking Bad",
                "overview": "English cached overview",
            }
        },
    }
    assert choose_display_title(record, "ru") == "Breaking Bad"
    assert choose_display_overview(record, "ru") == "English cached overview"


def test_unicode_title_preserved() -> None:
    record = {
        "localized": {"ru": {"title": "Игра престолов — 龍"}},
        "title": "Game of Thrones",
    }
    assert choose_display_title(record, "ru") == "Игра престолов — 龍"


def test_legacy_builder_does_not_mislable_latin_as_ru() -> None:
    record = {
        "title": "Breaking Bad",
        "overview": "A high school chemistry teacher.",
        "original_title": "Breaking Bad",
    }
    localized = build_localized_block_from_legacy(record, default_language="ru")
    assert "ru" not in localized or localized.get("ru", {}).get("title") is None
    assert localized["en"]["title"] == "Breaking Bad"
    assert localized["en"]["overview"] == "A high school chemistry teacher."


def test_enrichment_merges_ru_text_without_language_poster(monkeypatch) -> None:
    from candidates.pool import localized_posters

    pool = {
        "breaking bad|2008": {
            "pool_entry_key": "breaking bad|2008",
            "title": "Breaking Bad",
            "year": 2008,
            "tmdb_id": 1396,
            "media_type": "tv",
            "overview": "English discover overview",
        }
    }
    saved: dict = {}

    monkeypatch.setattr(
        localized_posters.pool_repository,
        "load_candidate_pool",
        lambda: copy.deepcopy(pool),
    )
    monkeypatch.setattr(
        localized_posters.pool_repository,
        "save_candidate_pool",
        lambda data: saved.update(data),
    )

    def fake_details(tmdb_id, *, language=None, append_to_response=None):
        assert (tmdb_id, language) == (1396, "ru-RU")
        return {
            "id": 1396,
            "name": "Breaking Bad",
            "original_name": "Breaking Bad",
            "overview": "English details overview",
            "translations": {
                "translations": [
                    {
                        "iso_639_1": "ru",
                        "iso_3166_1": "RU",
                        "data": {
                            "name": "Во все тяжкие",
                            "overview": "Учитель химии оказывается в тяжёлой ситуации.",
                        },
                    },
                    {
                        "iso_639_1": "en",
                        "iso_3166_1": "US",
                        "data": {
                            "name": "Breaking Bad",
                            "overview": "A chemistry teacher diagnosed with cancer.",
                        },
                    },
                ]
            },
            "images": {"posters": []},
        }

    updated, changed = localized_posters.ensure_candidate_localized_poster(
        pool["breaking bad|2008"],
        data_language="ru",
        details_func=fake_details,
    )

    assert changed is True
    assert updated["localized"]["ru"]["title"] == "Во все тяжкие"
    assert "Учитель химии" in updated["localized"]["ru"]["overview"]
    assert updated["localized"]["en"]["title"] == "Breaking Bad"
    assert updated.get(localized_posters.TMDB_LOCALIZED_CHECKED_AT)
    assert choose_display_title(updated, "ru") == "Во все тяжкие"
    assert "Учитель химии" in choose_display_overview(updated, "ru")
    assert saved["breaking bad|2008"]["localized"]["ru"]["title"] == "Во все тяжкие"
    # No refetch loop once checked.
    assert (
        localized_posters.candidate_needs_tmdb_detail_enrichment(updated, "ru") is False
    )


def test_display_model_breaking_bad_fixture() -> None:
    record = {
        "tmdb_id": 1396,
        "title": "Breaking Bad",
        "overview": "English",
        "localized": {
            "ru": {
                "title": "Во все тяжкие",
                "overview": "Русский синопсис Breaking Bad.",
            },
            "en": {
                "title": "Breaking Bad",
                "overview": "English synopsis.",
            },
        },
    }
    card = build_candidate_readonly_card(record, data_language="ru")
    assert card["title"] == "Во все тяжкие"
    overview = card.get("overview") or card.get("description") or ""
    assert "Русский синопсис" in overview
