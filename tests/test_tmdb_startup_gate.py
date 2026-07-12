from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget

import desktop.shell.main_window as main_window_module


def test_token_validation_worker_reports_error_instead_of_raising(monkeypatch, qapp) -> None:
    from desktop.startup.worker import TmdbStartupValidateWorker

    monkeypatch.setattr(
        "desktop.startup.worker.evaluate_tmdb_startup_readiness",
        lambda token: (_ for _ in ()).throw(ValueError("bad token payload")),
    )
    results: list[dict] = []
    worker = TmdbStartupValidateWorker("wrong-token")
    worker.completed.connect(results.append)

    worker.run()

    assert results == [
        {
            "ready": False,
            "error": "validation_failed",
            "details": "bad token payload",
        }
    ]


def test_token_validation_worker_interruption_skips_validation_and_save(monkeypatch, qapp) -> None:
    from threading import Event

    from desktop.startup.worker import TmdbStartupValidateWorker

    validation_started = Event()
    release_validation = Event()

    def blocking_readiness(_token):
        validation_started.set()
        assert release_validation.wait(2.0)
        return {"ready": True}

    monkeypatch.setattr(
        "desktop.startup.worker.evaluate_tmdb_startup_readiness",
        blocking_readiness,
    )
    saved_tokens: list[str] = []
    monkeypatch.setattr(
        "desktop.startup.worker.tmdb_api.save_tmdb_bearer_token",
        saved_tokens.append,
    )
    results: list[dict] = []
    worker = TmdbStartupValidateWorker("cancelled-token")
    worker.completed.connect(results.append)

    worker.start()
    assert validation_started.wait(1.0)
    worker.requestInterruption()
    release_validation.set()
    assert worker.wait(1000)

    assert results == []
    assert saved_tokens == []


def test_startup_readiness_worker_keeps_gui_event_loop_responsive(monkeypatch, qapp) -> None:
    from threading import Event

    from desktop.startup.worker import TmdbStartupReadinessWorker

    readiness_started = Event()
    release_readiness = Event()

    def blocking_readiness():
        readiness_started.set()
        assert release_readiness.wait(2.0)
        return {"ready": False, "error": "network_unreachable"}

    monkeypatch.setattr(
        "desktop.startup.worker.evaluate_tmdb_startup_readiness",
        blocking_readiness,
    )
    heartbeat = {"processed": False}
    worker = TmdbStartupReadinessWorker()
    worker.start()
    assert readiness_started.wait(1.0)

    QTimer.singleShot(0, lambda: heartbeat.__setitem__("processed", True))
    qapp.processEvents()

    assert heartbeat["processed"] is True
    worker.requestInterruption()
    release_readiness.set()
    assert worker.wait(1000)


def test_startup_gate_shows_clear_validation_error_in_form(monkeypatch, qapp) -> None:
    from desktop.startup.tmdb_gate import TmdbStartupGateView

    monkeypatch.setattr(TmdbStartupGateView, "_start_network_probe", lambda self: None)
    gate = TmdbStartupGateView()
    try:
        gate._on_network_probe_finished({"ok": True})
        gate._on_validate_finished({"ready": False, "error": "invalid_token"})

        assert gate._error_label.isHidden() is False
        assert "TMDb" in gate._error_label.text()
        assert "#FF7F8E" in gate.styleSheet()
    finally:
        gate.close()


def test_startup_gate_async_fast_path_passes_without_token_entry(monkeypatch, qapp) -> None:
    from desktop.startup.tmdb_gate import TmdbStartupGateView

    monkeypatch.setattr(TmdbStartupGateView, "_start_network_probe", lambda self: None)
    monkeypatch.setattr(
        main_window_module.candidate_service,
        "should_show_onboarding_autofill",
        lambda: False,
    )
    monkeypatch.setattr(
        main_window_module,
        "build_main_tabs",
        lambda tabs, parent, *, on_status_message: (
            object(),
            SimpleNamespace(
                candidate_session=SimpleNamespace(
                    reload_from_pool=lambda force=False: None,
                    invalidate_pool_cache=lambda: None,
                ),
                refresh_candidate_filters=lambda: None,
                focus_candidates=lambda: None,
            ),
        ),
    )

    window = main_window_module.WatchedMoviesWindow(initial_size=(900, 600))
    try:
        window.maybe_show_tmdb_startup_gate()
        gate = window._tmdb_gate_view
        assert isinstance(gate, TmdbStartupGateView)
        gate._on_network_probe_finished({"ready": True, "network": {"ok": True}})
        assert window._tmdb_gate_passed is True
        assert window._tmdb_gate_view is None
        window.maybe_show_onboarding_autofill()
    finally:
        window.close()


def test_startup_gate_blocks_onboarding_until_passed(monkeypatch, qapp) -> None:
    class FakeGate(QWidget):
        passed = pyqtSignal()

        def __init__(self, parent=None) -> None:
            super().__init__(parent)

        def setWindowFlag(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(
        "apis.tmdb_connectivity.evaluate_tmdb_startup_readiness",
        lambda token=None: {"ready": False, "error": "missing_token"},
    )
    monkeypatch.setattr(main_window_module, "TmdbStartupGateView", FakeGate)
    monkeypatch.setattr(
        main_window_module.candidate_service,
        "should_show_onboarding_autofill",
        lambda: True,
    )
    monkeypatch.setattr(
        main_window_module,
        "OnboardingAutofillDialog",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("onboarding blocked")),
    )
    monkeypatch.setattr(
        main_window_module,
        "build_main_tabs",
        lambda tabs, parent, *, on_status_message: (
            object(),
            SimpleNamespace(
                candidate_session=SimpleNamespace(
                    reload_from_pool=lambda force=False: None,
                    invalidate_pool_cache=lambda: None,
                ),
                refresh_candidate_filters=lambda: None,
                focus_candidates=lambda: None,
            ),
        ),
    )

    window = main_window_module.WatchedMoviesWindow(initial_size=(900, 600))
    try:
        window.maybe_show_tmdb_startup_gate()
        assert window._tmdb_gate_passed is False
        assert window._tmdb_gate_view is not None
        window.maybe_show_onboarding_autofill()
        assert window._onboarding_view is None
    finally:
        window.close()


def test_startup_gate_pass_marks_ready_and_opens_onboarding(monkeypatch, qapp) -> None:
    onboarding_calls = {"count": 0}

    class FakeGate(QWidget):
        passed = pyqtSignal()

        def __init__(self, parent=None) -> None:
            super().__init__(parent)

        def setWindowFlag(self, *_args, **_kwargs) -> None:
            return None

        def emit_passed(self) -> None:
            self.passed.emit()

    fake_gate = None

    def gate_factory(parent=None):
        nonlocal fake_gate
        fake_gate = FakeGate(parent=parent)
        return fake_gate

    monkeypatch.setattr(
        "apis.tmdb_connectivity.evaluate_tmdb_startup_readiness",
        lambda token=None: {"ready": False, "error": "missing_token"},
    )
    monkeypatch.setattr(main_window_module, "TmdbStartupGateView", gate_factory)
    monkeypatch.setattr("apis.tmdb_api.reload_tmdb_env", lambda: None)
    monkeypatch.setattr(
        main_window_module.candidate_service,
        "should_show_onboarding_autofill",
        lambda: (onboarding_calls.__setitem__("count", onboarding_calls["count"] + 1), False)[1],
    )
    monkeypatch.setattr(
        main_window_module,
        "build_main_tabs",
        lambda tabs, parent, *, on_status_message: (
            object(),
            SimpleNamespace(
                candidate_session=SimpleNamespace(
                    reload_from_pool=lambda force=False: None,
                    invalidate_pool_cache=lambda: None,
                ),
                refresh_candidate_filters=lambda: None,
                focus_candidates=lambda: None,
            ),
        ),
    )

    window = main_window_module.WatchedMoviesWindow(initial_size=(900, 600))
    try:
        window.maybe_show_tmdb_startup_gate()
        assert fake_gate is not None
        fake_gate.emit_passed()
        assert window._tmdb_gate_passed is True
        assert window._tmdb_gate_view is None
        assert onboarding_calls["count"] == 1
    finally:
        window.close()


def test_existing_pool_does_not_refill_during_startup_gate_flow(monkeypatch, qapp) -> None:
    monkeypatch.setattr(
        main_window_module.candidate_service,
        "should_show_onboarding_autofill",
        lambda: False,
    )
    monkeypatch.setattr(
        main_window_module,
        "build_main_tabs",
        lambda tabs, parent, *, on_status_message: (
            object(),
            SimpleNamespace(
                candidate_session=SimpleNamespace(
                    reload_from_pool=lambda force=False: None,
                    invalidate_pool_cache=lambda: None,
                ),
                refresh_candidate_filters=lambda: None,
                focus_candidates=lambda: None,
            ),
        ),
    )
    window = main_window_module.WatchedMoviesWindow(initial_size=(900, 600))
    calls = {"count": 0}
    window.maybe_start_pool_auto_refill = lambda: calls.__setitem__("count", calls["count"] + 1)
    window._tmdb_gate_passed = True
    try:
        window.maybe_show_onboarding_autofill()
        assert calls["count"] == 0
    finally:
        window.close()
