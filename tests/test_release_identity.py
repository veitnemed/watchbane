from pathlib import Path

from common.release import (
    APP_DISPLAY_NAME,
    APP_RELEASE_TAG,
    APP_VERSION,
    RECOMMENDATION_ENGINE_DISPLAY_NAME,
    release_signature,
)


ROOT = Path(__file__).resolve().parents[1]


def test_release_identity_is_stable_and_public() -> None:
    assert APP_VERSION == "0.1.1-alpha.1"
    assert APP_RELEASE_TAG == "v0.1.1-alpha.1"
    assert APP_DISPLAY_NAME == "Watchbane 0.1.1-alpha.1 — Open Route"
    assert RECOMMENDATION_ENGINE_DISPLAY_NAME == "ReDeck v0.1.0"
    assert release_signature() == (
        "Watchbane 0.1.1-alpha.1 — Open Route · ReDeck v0.1.0"
    )


def test_windows_bundle_uses_matching_version_metadata() -> None:
    spec = (ROOT / "watchbane.spec").read_text(encoding="utf-8")
    metadata = (ROOT / "tools" / "windows_version_info.txt").read_text(encoding="utf-8")

    assert 'version="tools/windows_version_info.txt"' in spec
    assert "0.1.1-alpha.1" in metadata
    assert "ReDeck v0.1.0" in metadata


def test_release_identity_is_visible_on_startup_and_settings(qapp) -> None:
    import desktop.settings.app_settings  # noqa: F401 — load settings before theme modules
    from PyQt6.QtWidgets import QLabel

    from desktop.onboarding.wizard import OnboardingAutofillDialog
    from desktop.settings.tab_view import SettingsTabView
    from desktop.startup.tmdb_gate import TmdbStartupGateView

    startup = TmdbStartupGateView(autostart=False)
    onboarding = OnboardingAutofillDialog(ui_language="ru")
    settings = SettingsTabView()

    startup_label = startup.findChild(QLabel, "startupReleaseVersion")
    onboarding_label = onboarding.findChild(QLabel, "onboardingReleaseVersion")
    settings_label = settings.widget.findChild(QLabel, "settingsReleaseVersion")

    assert startup_label is not None
    assert startup_label.text() == release_signature()
    assert onboarding_label is not None
    assert onboarding_label.text() == release_signature()
    assert settings_label is not None
    assert settings_label.text() == release_signature()


def test_main_window_close_cancels_delayed_startup_gate(qapp) -> None:
    import desktop.settings.app_settings  # noqa: F401

    from desktop.shell.main_window import WatchedMoviesWindow

    window = WatchedMoviesWindow(initial_size=(900, 700))
    window.schedule_tmdb_startup_gate(10_000)

    assert window._tmdb_gate_timer.isActive() is True
    window.close()
    qapp.processEvents()
    assert window._tmdb_gate_timer.isActive() is False
