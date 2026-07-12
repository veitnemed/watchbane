from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QPushButton

from desktop.settings.pool_clear_dialog import PoolClearDialog, pool_clear_confirmation_text
from desktop.settings.pool_ops_panel import PoolOpsPanel
from desktop.settings.pool_ops_worker import (
    ACTION_DEDUPE,
    ACTION_IMPORT_JSON,
    ACTION_PURGE_WATCHED,
    ACTION_TMDB_BUILD,
    PoolMaintenanceWorker,
)


class FakePoolMaintenanceWorker(QObject):
    finished_with_result = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(
        self,
        action: str,
        *,
        import_path=None,
        build_kwargs=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.action = action
        self.import_path = import_path
        self.build_kwargs = build_kwargs
        self.started = False

    def start(self) -> None:
        self.started = True

    def isRunning(self) -> bool:
        return self.started

    def deleteLater(self) -> None:
        super().deleteLater()

    def complete(self, payload: dict) -> None:
        self.started = False
        self.finished_with_result.emit(self.action, payload)
        self.finished.emit()

    def fail(self, message: str) -> None:
        self.started = False
        self.failed.emit(self.action, message)
        self.finished.emit()


class FakeCandidateService:
    def __init__(self) -> None:
        self.stats_view = {
            "stats": {
                "unique_total": 3,
                "storage_total": 3,
                "duplicate_entries": 2,
                "similar_duplicate_total": 1,
                "cross_year_duplicate_total": 0,
            },
            "summary": "уникальных: 3",
            "lines": ["Уникальных кандидатов: 3", "В JSON: 5 (+2 дублей)"],
        }
        self.matches_view = {"match_count": 2, "matches": [{}, {}], "is_empty": False}
        self.clean_calls = 0
        self.purge_calls = 0

    def get_pool_stats_view(self, criteria_name=None):
        del criteria_name
        return self.stats_view

    def get_pool_dataset_title_matches_view(self):
        return self.matches_view

    def clean_common_pool_duplicates(self, **kwargs):
        del kwargs
        self.clean_calls += 1
        return {"removed_total": 2, "changed": True}

    def purge_pool_dataset_title_matches(self):
        self.purge_calls += 1
        return {"removed_dataset_title_matches": 2, "changed": True}

    def clear_common_candidate_pool(self):
        return {"cleared": 3}

    def import_tmdb_result_to_pool(self, result_path, criteria_name=None):
        del result_path, criteria_name
        return {"ok": True, "stats": {"added": 1, "updated": 0}}


def _build_panel(qtbot, monkeypatch, service: FakeCandidateService | None = None):
    service = service or FakeCandidateService()
    workers: list[FakePoolMaintenanceWorker] = []

    def worker_factory(action, *, import_path=None, build_kwargs=None, parent=None):
        worker = FakePoolMaintenanceWorker(
            action,
            import_path=import_path,
            build_kwargs=build_kwargs,
            parent=parent,
        )
        workers.append(worker)
        return worker

    monkeypatch.setattr("desktop.settings.pool_ops_panel.candidate_service", service)
    status_messages: list[tuple[str, int]] = []
    pool_changed_calls = {"count": 0}

    panel = PoolOpsPanel(
        on_status_message=lambda message, timeout: status_messages.append((message, timeout)),
        worker_factory=worker_factory,
    )
    panel.poolChanged.connect(lambda: pool_changed_calls.__setitem__("count", pool_changed_calls["count"] + 1))
    qtbot.addWidget(panel)
    return panel, service, workers, status_messages, pool_changed_calls


def test_refresh_stats_shows_each_detail_once_and_duplicate_warning(qtbot, monkeypatch) -> None:
    panel, service, _workers, _status, _changed = _build_panel(qtbot, monkeypatch)

    panel.refresh_stats()

    assert panel._summary_label.isHidden() is True
    assert len(panel._stats_line_labels) == 1
    assert "3" in panel._stats_line_labels[0].text()
    assert panel._stats_layout.count() == 1
    assert panel._warning_label.isHidden() is False


def test_dedupe_confirm_starts_worker_and_emits_pool_changed(qtbot, monkeypatch) -> None:
    panel, service, workers, _status, changed = _build_panel(qtbot, monkeypatch)
    monkeypatch.setattr(panel, "_ask_confirmation", lambda *_args: True)

    qtbot.mouseClick(panel.findChild(QPushButton, "poolOpsDedupeButton"), Qt.MouseButton.LeftButton)

    assert len(workers) == 1
    assert workers[0].action == ACTION_DEDUPE
    workers[0].complete({"ok": True, "result": service.clean_common_pool_duplicates()})
    qtbot.waitUntil(lambda: changed["count"] == 1)


def test_purge_confirm_starts_worker(qtbot, monkeypatch) -> None:
    panel, service, workers, _status, changed = _build_panel(qtbot, monkeypatch)
    monkeypatch.setattr(panel, "_ask_confirmation", lambda *_args: True)

    qtbot.mouseClick(panel.findChild(QPushButton, "poolOpsPurgeButton"), Qt.MouseButton.LeftButton)

    assert workers[0].action == ACTION_PURGE_WATCHED
    workers[0].complete({"ok": True, "result": service.purge_pool_dataset_title_matches()})
    qtbot.waitUntil(lambda: changed["count"] == 1)


def test_clear_requires_typed_confirmation(qtbot, monkeypatch) -> None:
    panel, service, workers, _status, changed = _build_panel(qtbot, monkeypatch)
    accepted = {"value": False}

    class FakeClearDialog:
        DialogCode = PoolClearDialog.DialogCode

        def __init__(self, unique_total, parent=None):
            del unique_total, parent

        def exec(self):
            return self.DialogCode.Accepted if accepted["value"] else self.DialogCode.Rejected

    monkeypatch.setattr("desktop.settings.pool_ops_panel.PoolClearDialog", FakeClearDialog)

    qtbot.mouseClick(panel.findChild(QPushButton, "poolOpsClearButton"), Qt.MouseButton.LeftButton)
    assert workers == []

    accepted["value"] = True
    qtbot.mouseClick(panel.findChild(QPushButton, "poolOpsClearButton"), Qt.MouseButton.LeftButton)
    assert len(workers) == 1
    workers[0].complete({"ok": True, "result": service.clear_common_candidate_pool()})
    qtbot.waitUntil(lambda: changed["count"] == 1)


def test_import_path_starts_import_worker(qtbot, monkeypatch) -> None:
    panel, service, workers, _status, changed = _build_panel(qtbot, monkeypatch)
    monkeypatch.setattr(
        "desktop.settings.pool_ops_panel.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: ("D:/tmp/result.json", "TMDb JSON (*.json)"),
    )
    monkeypatch.setattr(panel, "_ask_confirmation", lambda *_args: True)

    qtbot.mouseClick(panel.findChild(QPushButton, "poolOpsImportButton"), Qt.MouseButton.LeftButton)

    assert workers[0].action == ACTION_IMPORT_JSON
    assert workers[0].import_path == "D:/tmp/result.json"
    workers[0].complete({"ok": True, "result": service.import_tmdb_result_to_pool("x")})
    qtbot.waitUntil(lambda: changed["count"] == 1)


def test_import_into_non_empty_pool_requires_confirmation(qtbot, monkeypatch) -> None:
    panel, _service, workers, _status, _changed = _build_panel(qtbot, monkeypatch)
    monkeypatch.setattr(
        "desktop.settings.pool_ops_panel.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: ("D:/tmp/result.json", "TMDb JSON (*.json)"),
    )
    questions = []

    def reject_import(title, text):
        questions.append((title, text))
        return False

    monkeypatch.setattr(panel, "_ask_confirmation", reject_import)

    qtbot.mouseClick(panel.findChild(QPushButton, "poolOpsImportButton"), Qt.MouseButton.LeftButton)

    assert workers == []
    assert len(questions) == 1
    assert "3" in questions[0][1]


def test_import_file_dialog_cancel_starts_no_worker(qtbot, monkeypatch) -> None:
    panel, _service, workers, _status, _changed = _build_panel(qtbot, monkeypatch)
    monkeypatch.setattr(
        "desktop.settings.pool_ops_panel.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: ("", ""),
    )

    qtbot.mouseClick(panel.findChild(QPushButton, "poolOpsImportButton"), Qt.MouseButton.LeftButton)

    assert workers == []


def test_build_dialog_cancel_starts_no_worker(qtbot, monkeypatch) -> None:
    panel, _service, workers, _status, _changed = _build_panel(qtbot, monkeypatch)

    class RejectedBuildDialog:
        DialogCode = PoolClearDialog.DialogCode

        def __init__(self, parent=None):
            del parent

        def exec(self):
            return self.DialogCode.Rejected

    monkeypatch.setattr("desktop.settings.pool_ops_panel.TmdbBuildDialog", RejectedBuildDialog)

    qtbot.mouseClick(panel.findChild(QPushButton, "poolOpsBuildButton"), Qt.MouseButton.LeftButton)

    assert workers == []


def test_busy_panel_rejects_second_worker_start(qtbot, monkeypatch) -> None:
    panel, _service, workers, _status, _changed = _build_panel(qtbot, monkeypatch)

    panel._start_worker(ACTION_TMDB_BUILD, build_kwargs={"country": "US"})
    panel._start_worker(ACTION_TMDB_BUILD, build_kwargs={"country": "GB"})

    assert len(workers) == 1
    assert workers[0].build_kwargs == {"country": "US"}
    assert all(
        button.isEnabled() is False
        for button in (
            panel._dedupe_button,
            panel._purge_button,
            panel._clear_button,
            panel._import_button,
            panel._build_button,
        )
    )


def test_invalid_import_reports_safe_message_without_raw_error(qtbot, monkeypatch) -> None:
    panel, _service, workers, status, _changed = _build_panel(qtbot, monkeypatch)
    monkeypatch.setattr(
        "desktop.settings.pool_ops_panel.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: ("D:/private/corrupt.json", "TMDb JSON (*.json)"),
    )
    monkeypatch.setattr(panel, "_ask_confirmation", lambda *_args: True)
    qtbot.mouseClick(panel.findChild(QPushButton, "poolOpsImportButton"), Qt.MouseButton.LeftButton)

    workers[0].complete({"ok": False, "error": "D:/private/corrupt.json: raw parser error"})

    assert status
    assert "D:/private" not in status[-1][0]


def test_pool_clear_confirmation_text_matches_language(monkeypatch) -> None:
    monkeypatch.setattr("desktop.settings.pool_clear_dialog.get_interface_language", lambda: "en")
    assert pool_clear_confirmation_text() == "CLEAR"
    monkeypatch.setattr("desktop.settings.pool_clear_dialog.get_interface_language", lambda: "ru")
    assert pool_clear_confirmation_text() == "ОЧИСТИТЬ"


def test_worker_dedupe_action_delegates_to_service(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_clean(**kwargs):
        del kwargs
        calls["count"] += 1
        return {"removed_total": 1}

    monkeypatch.setattr(
        "desktop.settings.pool_ops_worker.candidate_service.clean_common_pool_duplicates",
        fake_clean,
    )
    worker = PoolMaintenanceWorker(ACTION_DEDUPE)
    worker.run()
    assert calls["count"] == 1
