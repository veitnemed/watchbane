"""Dark confirmation dialog for deleting a watched record."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from desktop.i18n import tr
from desktop.theme import build_delete_dialog_style
from desktop.theme.scaling import layout_px
from desktop.watched.delete import (
    DELETE_CONFIRMATION_TEXT,
    format_delete_preview_lines,
    is_delete_confirmation_valid,
)

DELETE_DIALOG_STYLE = build_delete_dialog_style()


class WatchedDeleteDialog(QDialog):
    """Confirmation dialog with preview and typed DELETE confirmation."""

    def __init__(self, preview: dict, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("deleteRecordDialog")
        self.setWindowTitle(tr("watched.delete.dialog.title"))
        self.setModal(True)
        self.setFixedWidth(layout_px(430))
        screen = QApplication.primaryScreen()
        available_height = (
            screen.availableGeometry().height()
            if screen is not None
            else layout_px(720)
        )
        dialog_height = max(1, available_height - layout_px(48))
        self.setMaximumHeight(dialog_height)
        self.setStyleSheet(DELETE_DIALOG_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            layout_px(14),
            layout_px(14),
            layout_px(14),
            layout_px(14),
        )
        root_layout.setSpacing(0)

        card_frame = QFrame()
        card_frame.setObjectName("deleteRecordCard")
        root_layout.addWidget(card_frame)

        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(
            layout_px(18),
            layout_px(18),
            layout_px(18),
            layout_px(18),
        )
        card_layout.setSpacing(layout_px(12))

        preview_scroll = QScrollArea()
        preview_scroll.setObjectName("deleteRecordPreviewScroll")
        preview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        preview_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_scroll.viewport().setAutoFillBackground(False)

        preview_content = QWidget()
        preview_content.setObjectName("deleteRecordPreviewContent")
        preview_content.setAutoFillBackground(False)
        preview_layout = QVBoxLayout(preview_content)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(layout_px(12))

        header = QLabel(tr("watched.delete.dialog.title"))
        header.setObjectName("deleteRecordTitle")
        header.setWordWrap(True)
        preview_layout.addWidget(header)

        warning = QLabel(tr("watched.delete.dialog.warning"))
        warning.setObjectName("deleteRecordWarning")
        warning.setWordWrap(True)
        preview_layout.addWidget(warning)

        for line in format_delete_preview_lines(preview):
            label = QLabel(line)
            label.setObjectName("deleteRecordPreviewLine")
            label.setWordWrap(True)
            preview_layout.addWidget(label)

        preview_scroll.setWidget(preview_content)
        preview_height = min(
            preview_content.sizeHint().height(),
            max(layout_px(140), dialog_height - layout_px(210)),
        )
        preview_scroll.setMinimumHeight(preview_height)
        card_layout.addWidget(preview_scroll, stretch=1)

        confirm_label = QLabel(
            tr("watched.delete.dialog.confirm_label", confirmation=DELETE_CONFIRMATION_TEXT)
        )
        confirm_label.setObjectName("deleteRecordFieldLabel")
        card_layout.addWidget(confirm_label)

        self._confirm_input = QLineEdit()
        self._confirm_input.setObjectName("deleteRecordConfirmInput")
        self._confirm_input.setPlaceholderText(DELETE_CONFIRMATION_TEXT)
        self._confirm_input.textChanged.connect(self._update_delete_button_state)
        card_layout.addWidget(self._confirm_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        delete_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if delete_button is not None:
            delete_button.setObjectName("deleteRecordConfirmButton")
            delete_button.setText(tr("watched.delete.dialog.delete"))
            delete_button.setEnabled(False)
            delete_button.setAutoDefault(False)
        if cancel_button is not None:
            cancel_button.setText(tr("common.cancel"))
            cancel_button.setAutoDefault(False)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        card_layout.addWidget(buttons)

        self._delete_button = delete_button
        self._confirm_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self.resize(self.width(), min(self.sizeHint().height(), dialog_height))

    def _update_delete_button_state(self, _text: str = "") -> None:
        if self._delete_button is not None:
            self._delete_button.setEnabled(is_delete_confirmation_valid(self._confirm_input.text()))

    def _on_accept(self) -> None:
        if is_delete_confirmation_valid(self._confirm_input.text()) is False:
            return
        self.accept()
