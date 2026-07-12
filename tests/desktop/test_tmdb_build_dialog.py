from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDialogButtonBox, QDoubleSpinBox, QScrollArea, QSpinBox

from dataset.models.media_type import MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV
from desktop.settings.tmdb_build_dialog import (
    TMDB_BUILD_DEFAULT_DETAILS_LIMIT,
    TMDB_BUILD_DEFAULT_PAGES,
    TmdbBuildDialog,
)


def test_build_kwargs_maps_form_fields(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(
        "desktop.settings.tmdb_build_dialog.candidate_service.build_tmdb_criteria_name",
        lambda country, mode, **kwargs: f"{country}_{mode}_{kwargs.get('year_min')}",
    )
    dialog = TmdbBuildDialog()
    qtbot.addWidget(dialog)

    media_combo = dialog.findChild(QComboBox, "tmdbBuildMediaTypeCombo")
    country_combo = dialog.findChild(QComboBox, "tmdbBuildCountryCombo")
    mode_combo = dialog.findChild(QComboBox, "tmdbBuildModeCombo")
    year_spins = dialog.findChildren(QSpinBox, "tmdbBuildYearSpin")
    score_spin = dialog.findChild(QDoubleSpinBox, "tmdbBuildScoreSpin")
    votes_spin = dialog.findChild(QSpinBox, "tmdbBuildVotesSpin")

    media_combo.setCurrentIndex(media_combo.findData(MEDIA_TYPE_MOVIE))
    country_combo.setCurrentIndex(country_combo.findData("KR"))
    mode_combo.setCurrentIndex(mode_combo.findData("hidden_gems"))
    year_spins[0].setValue(2018)
    year_spins[1].setValue(2024)
    score_spin.setValue(7.5)
    votes_spin.setValue(500)

    kwargs = dialog.build_kwargs()

    assert kwargs == {
        "country": "KR",
        "media_type": MEDIA_TYPE_MOVIE,
        "mode": "hidden_gems",
        "pages": TMDB_BUILD_DEFAULT_PAGES,
        "details_limit": TMDB_BUILD_DEFAULT_DETAILS_LIMIT,
        "year_min": 2018,
        "year_max": 2024,
        "min_tmdb_score": 7.5,
        "min_tmdb_votes": 500,
        "criteria_name": "KR_hidden_gems_2018",
    }


def test_build_kwargs_leaves_optional_filters_empty(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(
        "desktop.settings.tmdb_build_dialog.candidate_service.build_tmdb_criteria_name",
        lambda country, mode, **kwargs: f"{country}_{mode}",
    )
    dialog = TmdbBuildDialog()
    qtbot.addWidget(dialog)

    kwargs = dialog.build_kwargs()

    assert kwargs["country"] == "RU"
    assert kwargs["media_type"] == MEDIA_TYPE_TV
    assert kwargs["mode"] == "quality"
    assert kwargs["year_min"] is None
    assert kwargs["year_max"] is None
    assert kwargs["min_tmdb_score"] is None
    assert kwargs["min_tmdb_votes"] is None


def test_build_dialog_keeps_actions_outside_scroll(qtbot) -> None:
    dialog = TmdbBuildDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    form_scroll = dialog.findChild(QScrollArea, "tmdbBuildScroll")
    buttons = dialog.findChild(QDialogButtonBox)

    assert form_scroll is not None
    assert buttons is not None
    assert form_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert form_scroll.isAncestorOf(buttons) is False
    assert dialog.height() <= dialog.maximumHeight()
