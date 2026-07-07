"""Add-title and candidate-transfer flow orchestration."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog

from dataset import service
from diagnostics.gui_event_log import log_event
from desktop.settings.app_settings import get_persisted_data_language
from desktop.watched.add_title.preview_dialog import AddTitlePreviewDialog
from desktop.watched.add_title.search_dialog import AddTitleSearchDialog


def run_candidate_transfer_flow(parent, candidate: dict):
    """Open preview dialog for pool candidate transfer; returns save result or None."""
    if not isinstance(candidate, dict):
        return None
    bundle = service.build_candidate_transfer_bundle(
        candidate,
        data_language=get_persisted_data_language(),
    )
    preview_dialog = AddTitlePreviewDialog(bundle, parent, transfer_mode=True)
    if preview_dialog.exec() == QDialog.DialogCode.Accepted:
        return preview_dialog.save_result
    return None


def run_add_title_flow(parent=None):
    """Open search dialog, then preview dialog; loop back on «Искать другой»."""
    log_event("add_title.flow.open")
    initial_title = ""
    initial_country = ""

    while True:
        search_dialog = AddTitleSearchDialog(
            parent,
            initial_title=initial_title,
            initial_country=initial_country,
        )
        if search_dialog.exec() != QDialog.DialogCode.Accepted:
            log_event("add_title.flow.search_rejected")
            return None

        bundle = search_dialog.resolve_bundle
        if bundle is None:
            log_event("add_title.flow.no_bundle")
            return None

        log_event("add_title.flow.preview_open", found=bundle.found, statuses=bundle.statuses)
        preview_dialog = AddTitlePreviewDialog(bundle, parent)
        if preview_dialog.exec() == QDialog.DialogCode.Accepted:
            log_event("add_title.flow.saved")
            return preview_dialog.save_result

        if preview_dialog.search_again is False:
            log_event("add_title.flow.preview_rejected")
            return None

        log_event("add_title.flow.search_again")
        initial_title = search_dialog.last_title
        initial_country = search_dialog.last_country


class AddTitleDialog:
    """Backward-compatible entry: runs the two-dialog flow."""

    def __init__(self, parent=None) -> None:
        self._parent = parent
        self._save_result = None

    @property
    def save_result(self):
        return self._save_result

    def exec(self) -> int:
        result = run_add_title_flow(self._parent)
        if result is None:
            return QDialog.DialogCode.Rejected
        self._save_result = result
        return QDialog.DialogCode.Accepted
