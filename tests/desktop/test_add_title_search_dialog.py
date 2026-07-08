from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog

from dataset.add_flow.bundle import AddTitleResolveBundle
from desktop.i18n import tr
from desktop.watched.add_title.search_dialog import AddTitleSearchDialog


@dataclass
class WorkerHarness:
    workers: list["FakeResolveWorker"]

    def factory(self, title: str, country: str, parent=None, *, media_type: str = "tv"):
        worker = FakeResolveWorker(title, country, parent, media_type=media_type)
        self.workers.append(worker)
        return worker


class FakeResolveWorker(QObject):
    progress = pyqtSignal(int, int, str)
    finished_with_result = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, title: str, country: str, parent=None, *, media_type: str = "tv") -> None:
        super().__init__(parent)
        self.title = title
        self.country = country
        self.media_type = media_type
        self.started = False
        self.interrupted = False
        self.deleted = False

    def start(self) -> None:
        self.started = True

    def isRunning(self) -> bool:
        return self.started

    def requestInterruption(self) -> None:
        self.interrupted = True

    def deleteLater(self) -> None:
        self.deleted = True
        super().deleteLater()

    def complete(self, bundle: AddTitleResolveBundle) -> None:
        self.started = False
        self.finished_with_result.emit(bundle)
        self.finished.emit()

    def fail(self, message: str) -> None:
        self.started = False
        self.failed.emit(message)
        self.finished.emit()


def _bundle(title: str = "Триггер", year: int = 2018) -> AddTitleResolveBundle:
    return AddTitleResolveBundle(
        title=title,
        country="Россия",
        defaults={
            "main_info": {"title": title, "year": year, "country": "Россия"},
            "raw_scores": {},
            "genre": {},
        },
        meta_payload={},
        poster_hints={},
        preview_movie={"main_info": {"title": title, "year": year}},
        preview_card={"title": title, "year": year},
        found=True,
        statuses={"tmdb_api": "найдено"},
    )


def _dialog(harness: WorkerHarness | None = None) -> AddTitleSearchDialog:
    harness = harness or WorkerHarness([])
    return AddTitleSearchDialog(initial_title="Триггер", worker_factory=harness.factory)


def test_enter_in_title_input_starts_search_and_does_not_reject(qapp) -> None:
    harness = WorkerHarness([])
    dialog = _dialog(harness)

    QTest.keyClick(dialog._title_input, Qt.Key.Key_Return)

    assert len(harness.workers) == 1
    assert harness.workers[0].started is True
    assert dialog.result() == 0
    assert dialog.resolve_bundle is None


def test_media_type_selector_passes_movie_to_worker(qapp) -> None:
    harness = WorkerHarness([])
    dialog = _dialog(harness)
    dialog._media_type_combo.setCurrentIndex(1)

    dialog._start_search(trigger="button")

    assert len(harness.workers) == 1
    assert harness.workers[0].media_type == "movie"


def test_search_dialog_has_no_cancel_button(qapp) -> None:
    from PyQt6.QtWidgets import QPushButton

    dialog = _dialog()

    assert hasattr(dialog, "_cancel_button") is False
    assert all(button.text() != "Отмена" for button in dialog.findChildren(QPushButton))


def test_find_button_does_not_create_second_worker_when_search_is_running(qapp) -> None:
    harness = WorkerHarness([])
    dialog = _dialog(harness)

    dialog._start_search(trigger="button")
    dialog._search_button.click()

    assert len(harness.workers) == 1


def test_repeated_enter_while_running_does_not_create_second_worker(qapp) -> None:
    harness = WorkerHarness([])
    dialog = _dialog(harness)

    QTest.keyClick(dialog._title_input, Qt.Key.Key_Return)
    QTest.keyClick(dialog._title_input, Qt.Key.Key_Return)

    assert len(harness.workers) == 1


def test_cancel_while_running_requests_interruption_and_does_not_accept_late_result(qapp) -> None:
    harness = WorkerHarness([])
    dialog = _dialog(harness)
    dialog._start_search(trigger="button")
    worker = harness.workers[0]

    dialog._cancel_search_dialog()
    worker.complete(_bundle())

    assert worker.interrupted is True
    assert dialog.resolve_bundle is None
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_signals_from_old_request_id_are_ignored(qapp) -> None:
    dialog = _dialog()
    dialog._active_request_id = 2

    dialog._on_progress(1, 3, 7, "old progress")
    dialog._on_resolve_finished(1, _bundle("Старый"))

    assert dialog.resolve_bundle is None
    assert dialog.result() == 0
    assert dialog._status_label.text() == ""


def test_success_from_current_request_saves_bundle_and_accepts_dialog(qapp) -> None:
    harness = WorkerHarness([])
    dialog = _dialog(harness)
    dialog._start_search(trigger="button")
    bundle = _bundle()

    harness.workers[0].complete(bundle)

    assert dialog.resolve_bundle is bundle
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_failed_from_current_request_returns_dialog_to_idle_without_closing(qapp, monkeypatch) -> None:
    harness = WorkerHarness([])
    dialog = _dialog(harness)
    messages = []
    monkeypatch.setattr(
        "desktop.watched.add_title.search_dialog.QMessageBox.critical",
        lambda parent, title, message: messages.append((title, message)),
    )
    dialog._start_search(trigger="button")

    harness.workers[0].fail("network failed")

    assert messages == [
        (
            tr("add_title.header"),
            tr("add_title.error.search_failed", message="network failed"),
        )
    ]
    assert dialog._worker is None
    assert dialog._title_input.isEnabled() is True
    assert dialog._search_button.isEnabled() is True
    assert dialog.result() == 0


def test_all_add_title_log_events_from_search_dialog_get_request_id(qapp, monkeypatch) -> None:
    harness = WorkerHarness([])
    events = []
    monkeypatch.setattr(
        "desktop.watched.add_title.search_dialog.log_event",
        lambda event, **fields: events.append((event, fields)),
    )
    dialog = _dialog(harness)

    dialog._start_search(trigger="button")
    dialog._on_progress(dialog._active_request_id, 1, 7, "progress")
    dialog._start_search(trigger="enter")
    dialog._cancel_search_dialog()
    harness.workers[0].complete(_bundle())

    add_title_events = [item for item in events if item[0].startswith("add_title.")]
    assert add_title_events
    assert all("request_id" in fields for _event, fields in add_title_events)
