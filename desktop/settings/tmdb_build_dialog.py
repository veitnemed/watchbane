"""Simplified TMDb discover dialog for desktop pool build."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from candidates import service as candidate_service
from candidates.sources.tmdb import country_options as tmdb_country_options
from dataset.models.media_type import MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV
from desktop.i18n import tr
from desktop.theme.scaling import layout_px

TMDB_BUILD_DEFAULT_PAGES = 3
TMDB_BUILD_DEFAULT_DETAILS_LIMIT = 50
TMDB_YEAR_MIN = 1900
TMDB_YEAR_MAX = 2100


def _optional_spin_value(spin: QSpinBox) -> int | None:
    if spin.specialValueText() and spin.value() == spin.minimum():
        return None
    return int(spin.value())


def _optional_double_value(spin: QDoubleSpinBox) -> float | None:
    if spin.specialValueText() and spin.value() <= spin.minimum():
        return None
    return float(spin.value())


class TmdbBuildDialog(QDialog):
    """Minimal discover form mapped to build_and_save_tmdb_candidate_pool kwargs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tmdbBuildDialog")
        self.setWindowTitle(tr("settings.pool.ops.build.dialog.title"))
        self.setModal(True)
        self.setMinimumWidth(layout_px(420))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            layout_px(16),
            layout_px(16),
            layout_px(16),
            layout_px(16),
        )
        root_layout.setSpacing(layout_px(12))

        card = QFrame()
        card.setObjectName("settingsInterfaceSection")
        root_layout.addWidget(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            layout_px(16),
            layout_px(14),
            layout_px(16),
            layout_px(14),
        )
        card_layout.setSpacing(layout_px(10))

        title = QLabel(tr("settings.pool.ops.build.dialog.title"))
        title.setObjectName("settingsSectionTitle")
        card_layout.addWidget(title)

        hint = QLabel(tr("settings.pool.ops.build.dialog.hint"))
        hint.setObjectName("poolOpsBuildHint")
        hint.setWordWrap(True)
        card_layout.addWidget(hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(layout_px(12))
        form.setVerticalSpacing(layout_px(8))

        self._media_type_combo = QComboBox()
        self._media_type_combo.setObjectName("tmdbBuildMediaTypeCombo")
        self._media_type_combo.addItem(tr("settings.pool.ops.build.media_type.tv"), MEDIA_TYPE_TV)
        self._media_type_combo.addItem(tr("settings.pool.ops.build.media_type.movie"), MEDIA_TYPE_MOVIE)
        form.addRow(tr("settings.pool.ops.build.media_type.label"), self._media_type_combo)

        self._country_combo = QComboBox()
        self._country_combo.setObjectName("tmdbBuildCountryCombo")
        for option in tmdb_country_options.country_options():
            self._country_combo.addItem(option["label"], option["code"])
        form.addRow(tr("settings.pool.ops.build.country.label"), self._country_combo)

        self._mode_combo = QComboBox()
        self._mode_combo.setObjectName("tmdbBuildModeCombo")
        self._mode_combo.addItem(tr("settings.pool.ops.build.mode.quality"), "quality")
        self._mode_combo.addItem(tr("settings.pool.ops.build.mode.hidden_gems"), "hidden_gems")
        form.addRow(tr("settings.pool.ops.build.mode.label"), self._mode_combo)

        self._year_min_spin = self._build_optional_year_spin(tr("settings.pool.ops.build.year_min.empty"))
        self._year_max_spin = self._build_optional_year_spin(tr("settings.pool.ops.build.year_max.empty"))
        form.addRow(tr("settings.pool.ops.build.year_min.label"), self._year_min_spin)
        form.addRow(tr("settings.pool.ops.build.year_max.label"), self._year_max_spin)

        self._min_score_spin = self._build_optional_score_spin()
        self._min_votes_spin = self._build_optional_votes_spin()
        form.addRow(tr("settings.pool.ops.build.min_score.label"), self._min_score_spin)
        form.addRow(tr("settings.pool.ops.build.min_votes.label"), self._min_votes_spin)

        card_layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        start_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if start_button is not None:
            start_button.setText(tr("settings.pool.ops.build.start"))
        if cancel_button is not None:
            cancel_button.setText(tr("common.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        card_layout.addWidget(buttons)

    def _build_optional_year_spin(self, empty_label: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setObjectName("tmdbBuildYearSpin")
        spin.setRange(TMDB_YEAR_MIN - 1, TMDB_YEAR_MAX)
        spin.setSpecialValueText(empty_label)
        spin.setValue(spin.minimum())
        return spin

    def _build_optional_score_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setObjectName("tmdbBuildScoreSpin")
        spin.setRange(0.0, 10.0)
        spin.setSingleStep(0.1)
        spin.setDecimals(1)
        spin.setSpecialValueText(tr("settings.pool.ops.build.optional.empty"))
        spin.setValue(0.0)
        return spin

    def _build_optional_votes_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setObjectName("tmdbBuildVotesSpin")
        spin.setRange(0, 1_000_000)
        spin.setSingleStep(100)
        spin.setSpecialValueText(tr("settings.pool.ops.build.optional.empty"))
        spin.setValue(0)
        return spin

    def build_kwargs(self) -> dict:
        """Map form values to candidates.service build kwargs."""
        country = str(self._country_combo.currentData() or "RU")
        media_type = str(self._media_type_combo.currentData() or MEDIA_TYPE_TV)
        mode = str(self._mode_combo.currentData() or "quality")
        year_min = _optional_spin_value(self._year_min_spin)
        year_max = _optional_spin_value(self._year_max_spin)
        min_tmdb_score = _optional_double_value(self._min_score_spin)
        min_tmdb_votes = _optional_spin_value(self._min_votes_spin)
        criteria_name = candidate_service.build_tmdb_criteria_name(
            country,
            mode,
            year_min=year_min,
            min_tmdb_score=min_tmdb_score,
        )
        return {
            "country": country,
            "media_type": media_type,
            "mode": mode,
            "pages": TMDB_BUILD_DEFAULT_PAGES,
            "details_limit": TMDB_BUILD_DEFAULT_DETAILS_LIMIT,
            "year_min": year_min,
            "year_max": year_max,
            "min_tmdb_score": min_tmdb_score,
            "min_tmdb_votes": min_tmdb_votes,
            "criteria_name": criteria_name,
        }
