"""Add-title search dialog: title, country and async resolve."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from candidates.models import country_schema
from candidates.sources.tmdb.country_options import add_title_country_combo_options
from common import valid
from dataset import service
from dataset.models.media_type import MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV, normalize_media_type
from diagnostics.gui_event_log import log_event
from desktop.i18n import tr
from desktop.settings.app_settings import get_persisted_data_language, get_persisted_interface_language
from desktop.watched.add_title.constants import (
    ADD_TITLE_DIALOG_STYLE,
    SEARCH_DIALOG_HEIGHT,
    SEARCH_DIALOG_HEIGHT_ACTIVE,
    SEARCH_DIALOG_WIDTH,
)
from desktop.watched.add_title.status_i18n import translate_resolve_progress_message
from desktop.watched.add_title.worker import AddTitleResolveWorker
from desktop.theme.scaling import layout_px


class AddTitleSearchDialog(QDialog):
    """Compact dialog: title, country, progress. Closes when resolve succeeds."""

    def __init__(
        self,
        parent=None,
        *,
        initial_title: str = "",
        initial_country: str = "",
        worker_factory: Callable | None = None,
    ) -> None:
        super().__init__(parent)
        self._bundle: service.AddTitleResolveBundle | None = None
        self._worker: AddTitleResolveWorker | None = None
        self._worker_factory = worker_factory or AddTitleResolveWorker
        self._interface_language = get_persisted_interface_language()
        self._data_language = get_persisted_data_language()
        self._request_seq = 0
        self._active_request_id = 0
        self._cancel_after_worker = False
        self._selected_tmdb_id: int | None = None
        self.last_title = initial_title.strip()
        self.last_country = initial_country
        self.last_media_type = MEDIA_TYPE_TV

        self.setObjectName("addTitleSearchDialog")
        self.setWindowTitle(tr("add_title.window.search"))
        self.setModal(True)
        self.setFixedSize(SEARCH_DIALOG_WIDTH, SEARCH_DIALOG_HEIGHT)
        self.setStyleSheet(ADD_TITLE_DIALOG_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            layout_px(14),
            layout_px(12),
            layout_px(14),
            layout_px(12),
        )
        root_layout.setSpacing(layout_px(8))

        header = QLabel(tr("add_title.header"))
        header.setObjectName("addTitleHeader")
        root_layout.addWidget(header)

        subtitle = QLabel(tr("add_title.search.subtitle"))
        subtitle.setObjectName("addTitleSubtitle")
        subtitle.setWordWrap(True)
        root_layout.addWidget(subtitle)

        search_frame = QFrame()
        search_frame.setObjectName("addTitleSearchPanel")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(
            layout_px(12),
            layout_px(10),
            layout_px(12),
            layout_px(10),
        )
        search_layout.setSpacing(layout_px(8))

        self._title_input = QLineEdit()
        self._title_input.setObjectName("addTitleSearchInput")
        self._title_input.setPlaceholderText(tr("add_title.search.input_placeholder"))
        self._title_input.setText(self.last_title)
        self._title_input.returnPressed.connect(lambda: self._start_search(trigger="enter"))

        self._country_combo = QComboBox()
        self._country_combo.setObjectName("addTitleCountryCombo")
        self._country_combo.setMinimumContentsLength(8)
        self._country_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        for label, value in add_title_country_combo_options():
            self._country_combo.addItem(self._country_display_label(label, value), value)
        self._set_country_selection(initial_country)

        self._media_type_combo = QComboBox()
        self._media_type_combo.setObjectName("addTitleMediaTypeCombo")
        self._media_type_combo.setMinimumContentsLength(6)
        self._media_type_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._media_type_combo.addItem(tr("media_type.tv"), MEDIA_TYPE_TV)
        self._media_type_combo.addItem(tr("media_type.movie"), MEDIA_TYPE_MOVIE)

        self._search_button = QPushButton(tr("add_title.search.button"))
        self._search_button.setObjectName("addTitleSearchButton")
        self._search_button.setAutoDefault(False)
        self._search_button.setDefault(False)
        self._search_button.clicked.connect(lambda: self._start_search(trigger="button"))

        search_layout.addWidget(self._title_input, stretch=4)
        search_layout.addWidget(self._media_type_combo, stretch=1)
        search_layout.addWidget(self._country_combo, stretch=1)
        search_layout.addWidget(self._search_button)
        root_layout.addWidget(search_frame)

        self._progress = QProgressBar()
        self._progress.setObjectName("addTitleProgress")
        self._progress.setTextVisible(True)
        self._progress.hide()
        root_layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setObjectName("addTitleStatus")
        self._status_label.setWordWrap(True)
        self._status_label.hide()
        root_layout.addWidget(self._status_label)

        self._title_input.setFocus(Qt.FocusReason.OtherFocusReason)
        if self.last_title:
            self._title_input.selectAll()

    @property
    def resolve_bundle(self) -> service.AddTitleResolveBundle | None:
        return self._bundle

    def _country_display_label(self, label: str, value: str) -> str:
        if str(value or "").strip() == "":
            return tr("add_title.country.any")
        codes = country_schema.normalize_country_filter_list(value or label)
        return (
            country_schema.build_country_display(codes, language=self._interface_language)
            or str(label or "").strip()
        )

    def _set_country_selection(self, country: str) -> None:
        normalized = str(country or "").strip()
        if normalized == "":
            self._country_combo.setCurrentIndex(0)
            return
        selected_codes = country_schema.normalize_country_filter_list(normalized)
        for index in range(self._country_combo.count()):
            if self._country_combo.itemData(index) == normalized:
                self._country_combo.setCurrentIndex(index)
                return
            option_codes = country_schema.normalize_country_filter_list(self._country_combo.itemData(index))
            if selected_codes and option_codes == selected_codes:
                self._country_combo.setCurrentIndex(index)
                return

    def _selected_country(self) -> str:
        country = self._country_combo.currentData()
        if country is None:
            return ""
        return str(country).strip()

    def _selected_media_type(self) -> str:
        return normalize_media_type(self._media_type_combo.currentData())

    def _set_search_active(self, active: bool) -> None:
        self._title_input.setEnabled(not active)
        self._media_type_combo.setEnabled(not active)
        self._country_combo.setEnabled(not active)
        self._search_button.setEnabled(not active)
        self._progress.setVisible(active)
        self._status_label.setVisible(active)
        self.setFixedHeight(SEARCH_DIALOG_HEIGHT_ACTIVE if active else SEARCH_DIALOG_HEIGHT)
        if active is False:
            self._progress.reset()

    def _cancel_search_dialog(self) -> None:
        worker_running = self._worker is not None and self._worker.isRunning()
        log_event(
            "add_title.search.cancel_clicked",
            request_id=self._active_request_id,
            title=self._title_input.text().strip(),
            worker_running=worker_running,
        )
        if worker_running:
            self._cancel_after_worker = True
            self._status_label.setVisible(True)
            self._status_label.setText(tr("add_title.search.cancel_after_step"))
            self._worker.requestInterruption()
            log_event("add_title.search.cancel_requested", request_id=self._active_request_id)
            return
        self.reject()

    def _start_search(self, *, trigger: str = "unknown") -> None:
        if self._worker is not None and self._worker.isRunning():
            log_event(
                "add_title.search.ignored_already_running",
                trigger=trigger,
                request_id=self._active_request_id,
            )
            return

        title = self._title_input.text().strip()
        if valid.is_correct_title(title) is False:
            log_event("add_title.search.invalid_title", trigger=trigger, request_id=0, title=title)
            QMessageBox.warning(self, tr("add_title.header"), tr("add_title.error.invalid_title"))
            return

        self.last_title = title
        self.last_country = self._selected_country()
        self.last_media_type = self._selected_media_type()
        self._bundle = None
        self._request_seq += 1
        self._active_request_id = self._request_seq
        self._cancel_after_worker = False
        request_id = self._active_request_id
        log_event(
            "add_title.search.start",
            trigger=trigger,
            request_id=request_id,
            title=title,
            country=self.last_country,
            media_type=self.last_media_type,
        )
        self._set_search_active(True)
        self._status_label.setText(tr("add_title.status.searching"))
        self._progress.setValue(0)
        self._progress.setMaximum(7)

        try:
            worker = self._worker_factory(
                title,
                self.last_country,
                self,
                data_language=self._data_language,
                media_type=self.last_media_type,
                selected_tmdb_id=self._selected_tmdb_id,
            )
        except TypeError:
            try:
                worker = self._worker_factory(
                    title,
                    self.last_country,
                    self,
                    media_type=self.last_media_type,
                    selected_tmdb_id=self._selected_tmdb_id,
                )
            except TypeError:
                try:
                    worker = self._worker_factory(
                        title,
                        self.last_country,
                        self,
                        media_type=self.last_media_type,
                    )
                except TypeError:
                    worker = self._worker_factory(title, self.last_country, self)
        worker.progress.connect(
            lambda current, total, message, rid=request_id: self._on_progress(rid, current, total, message)
        )
        worker.finished_with_result.connect(
            lambda bundle, rid=request_id: self._on_resolve_finished(rid, bundle)
        )
        worker.failed.connect(lambda message, rid=request_id: self._on_resolve_failed(rid, message))
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()
        log_event(
            "add_title.worker.started",
            request_id=request_id,
            title=title,
            country=self.last_country,
            media_type=self.last_media_type,
        )

    def _is_current_request(self, request_id: int) -> bool:
        return request_id == self._active_request_id

    def _on_progress(self, request_id: int, current: int, total: int, message: str) -> None:
        if self._is_current_request(request_id) is False:
            log_event("add_title.worker.progress_ignored_stale", request_id=request_id, message=message)
            return
        log_event("add_title.worker.progress", request_id=request_id, current=current, total=total, message=message)
        self._progress.setMaximum(max(total, 1))
        self._progress.setValue(min(current, total))
        percent = int(round(100 * current / max(total, 1)))
        self._progress.setFormat(f"{percent}%")
        if self._cancel_after_worker:
            self._status_label.setText(tr("add_title.search.cancel_after_step"))
        else:
            self._status_label.setText(translate_resolve_progress_message(message))

    def _on_resolve_failed(self, request_id: int, message: str) -> None:
        if self._is_current_request(request_id) is False:
            log_event("add_title.worker.failed_ignored_stale", request_id=request_id, message=message)
            return
        log_event("add_title.worker.failed", request_id=request_id, message=message)
        self._worker = None
        self._set_search_active(False)
        if self._cancel_after_worker:
            log_event("add_title.search.cancel_completed", request_id=request_id)
            self.reject()
            return
        QMessageBox.critical(
            self,
            tr("add_title.header"),
            tr("add_title.error.search_failed", message=message),
        )

    def _on_resolve_finished(self, request_id: int, bundle: service.AddTitleResolveBundle) -> None:
        if self._is_current_request(request_id) is False:
            log_event("add_title.worker.finished_ignored_stale", request_id=request_id)
            return
        log_event(
            "add_title.worker.finished",
            request_id=request_id,
            found=bundle.found,
            statuses=bundle.statuses,
            preview_title=bundle.preview_card.get("title"),
            preview_year=bundle.preview_card.get("year"),
        )
        self._worker = None
        self._set_search_active(False)
        if self._cancel_after_worker:
            log_event("add_title.search.cancel_completed", request_id=request_id)
            self.reject()
            return
        if self._selected_tmdb_id is None and len(bundle.search_results) > 1:
            options = [self._format_search_result(item) for item in bundle.search_results]
            selected_label, accepted = self._choose_search_result(options)
            if accepted is False:
                self._bundle = None
                return
            selected_index = options.index(selected_label)
            selected = bundle.search_results[selected_index]
            self._selected_tmdb_id = int(selected.get("id") or 0) or None
            if self._selected_tmdb_id != bundle.selected_tmdb_id:
                self._start_search(trigger="result_selection")
                return
        self._selected_tmdb_id = None
        self._bundle = bundle
        self.accept()

    @staticmethod
    def _format_search_result(item: dict) -> str:
        title = str(
            item.get("name")
            or item.get("title")
            or item.get("original_name")
            or item.get("original_title")
            or "—"
        ).strip()
        date_value = str(item.get("first_air_date") or item.get("release_date") or "")
        year = date_value[:4] if len(date_value) >= 4 else "—"
        original = str(item.get("original_name") or item.get("original_title") or "").strip()
        suffix = f" · {original}" if original and original.casefold() != title.casefold() else ""
        return f"{title} ({year}){suffix} · TMDb {item.get('id')}"

    def _choose_search_result(self, options: list[str]) -> tuple[str, bool]:
        dialog = QInputDialog(self)
        dialog.setWindowTitle(tr("add_title.results.title"))
        dialog.setLabelText(tr("add_title.results.prompt"))
        dialog.setComboBoxItems(options)
        dialog.setComboBoxEditable(False)
        dialog.setOkButtonText(tr("common.continue"))
        dialog.setCancelButtonText(tr("common.cancel"))
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.textValue(), accepted

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            log_event("add_title.search.reject_deferred", request_id=self._active_request_id)
            self._cancel_search_dialog()
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            log_event("add_title.search.close_with_running_worker", request_id=self._active_request_id)
            self._cancel_search_dialog()
            event.ignore()
            return
        log_event("add_title.search.close", request_id=self._active_request_id)
        super().closeEvent(event)
