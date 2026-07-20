from __future__ import annotations

from tools.qa.output_defect_audit import audit_deck_cards, audit_title, build_output_defect_audit


def _card(**overrides: object) -> dict[str, object]:
    candidate: dict[str, object] = {
        "tmdb_id": 101,
        "title": "Readable title",
        "original_title": "Readable title",
        "media_type": "movie",
        "year": 2024,
        "genres": ["drama"],
        "countries": ["RU"],
        "overview": "A serious drama.",
        "keywords": [],
        "adult": False,
        "content_rating": "TV-14",
    }
    candidate.update(overrides)
    return candidate


def test_title_audit_detects_placeholder_and_mojibake() -> None:
    assert audit_title("Untitled") == ["missing_or_placeholder_title"]
    assert audit_title("Ð¢ÐµÑÑ‚") == ["mojibake_title"]
    assert audit_title("Normal title") == []


def test_deck_audit_flags_explicit_description_and_hentai_keyword() -> None:
    report = audit_deck_cards(
        [
            _card(
                title="Hentai Academy",
                overview="A pornographic anime about students.",
                keywords=["hentai"],
            )
        ]
    )

    assert report["passed"] is False
    finding = report["cards"][0]
    assert "explicit_content_returned" in finding["defects"]
    assert "sexual_text_marker" in finding["defects"]
    assert "hentai" in finding["sexual_text_markers"]


def test_all_current_onboarding_presets_have_safe_nonempty_fetch_plans() -> None:
    report = build_output_defect_audit([])

    assert report["passed"] is True
    assert len(report["preset_contracts"]) == 8
    assert all(preset["passed"] for preset in report["preset_contracts"])
    assert all(
        bucket["include_adult"] is False
        for preset in report["preset_contracts"]
        for bucket in preset["buckets"]
    )
