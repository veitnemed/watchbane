"""Compact dialog for editing a watched title user_score."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QVBoxLayout,
)

from desktop.i18n import tr
from desktop.theme import build_score_edit_dialog_style
from desktop.theme.scaling import layout_px
from desktop.shared.detail.presenters import format_user_score_display
from desktop.watched.model import (
    USER_SCORE_MAX,
    USER_SCORE_MIN,
    USER_SCORE_STEP,
    WatchedEntry,
    get_user_score_spin_value,
)

SCORE_EDIT_DIALOG_STYLE = build_score_edit_dialog_style()


class ScoreEditDialog(QDialog):
    """Compact dark dialog for editing a watched title score."""

    def __init__(self, entry: WatchedEntry, parent=None) -> None:
        super().__init__(parent)
        dataset_key, _movie, card = entry
        title = card.get("title") or dataset_key
        year = card.get("year")
        title_text = f"{title} ({year})" if year not in (None, "") else str(title)

        self.setObjectName("scoreEditDialog")
        self.setWindowTitle(tr("watched.score.dialog.title"))
        self.setModal(True)
        self.setFixedWidth(layout_px(390))
        self.setStyleSheet(SCORE_EDIT_DIALOG_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            layout_px(14),
            layout_px(14),
            layout_px(14),
            layout_px(14),
        )
        root_layout.setSpacing(0)

        card_frame = QFrame()
        card_frame.setObjectName("scoreEditCard")
        root_layout.addWidget(card_frame)

        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(
            layout_px(18),
            layout_px(18),
            layout_px(18),
            layout_px(18),
        )
        card_layout.setSpacing(layout_px(12))

        header = QLabel(tr("watched.score.dialog.title"))
        header.setObjectName("scoreEditTitle")
        card_layout.addWidget(header)

        title_label = QLabel(title_text)
        title_label.setObjectName("scoreEditMovieTitle")
        title_label.setWordWrap(True)
        card_layout.addWidget(title_label)

        current_label = QLabel(
            tr("watched.score.dialog.current", score=format_user_score_display(card.get("user_score")))
        )
        current_label.setObjectName("scoreEditCurrent")
        card_layout.addWidget(current_label)

        form = QFormLayout()
        form.setContentsMargins(0, layout_px(4), 0, 0)
        form.setSpacing(layout_px(8))
        field_label = QLabel(tr("watched.score.dialog.field"))
        field_label.setObjectName("scoreEditFieldLabel")
        self._score_input = QDoubleSpinBox()
        self._score_input.setObjectName("scoreEditSpin")
        self._score_input.setRange(USER_SCORE_MIN, USER_SCORE_MAX)
        self._score_input.setSingleStep(USER_SCORE_STEP)
        self._score_input.setDecimals(1)
        self._score_input.setValue(get_user_score_spin_value(card))
        self._score_input.selectAll()
        form.addRow(field_label, self._score_input)
        card_layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setObjectName("scoreEditSaveButton")
            save_button.setText(tr("settings.save"))
            save_button.setDefault(True)
            save_button.setAutoDefault(True)
        if cancel_button is not None:
            cancel_button.setText(tr("common.cancel"))
            cancel_button.setAutoDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        card_layout.addWidget(buttons)

        self._score_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def score_value(self) -> float:
        return self._score_input.value()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            return
        super().keyPressEvent(event)
