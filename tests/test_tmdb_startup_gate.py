from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

import desktop.shell.main_window as main_window_module


def test_startup_gate_fast_path_skips_view(monkeypatch, qapp) -> None:
    monkeypatch.setattr(
        "apis.tmdb_connectivity.evaluate_tmdb_startup_readiness",
        lambda token=None: {"ready": True},
    )
    monkeypatch.setattr(
        main_window_module,
        "TmdbStartupGateView",
        lambda parent=None: (_ for _ in ()).throw(AssertionError("gate should not open")),
    )
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
