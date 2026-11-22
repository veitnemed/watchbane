"""TMDB credits stay reachable in the offline-first two-tab product shell."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QNetworkAccessManager
from PyQt6.QtWidgets import QMessageBox, QPushButton

from desktop.shell.main_window import WatchedMoviesWindow


_EN = "This product uses the TMDB API but is not endorsed or certified by TMDB."
_RU = "Этот продукт использует API TMDB, но не одобрен и не сертифицирован TMDB."


@pytest.mark.parametrize("language,caption,collection", (("ru", "О программе", "Коллекция"),
                                                         ("en", "About", "Collection")))
def test_persistent_about_after_offline_start_without_network(qtbot, monkeypatch, language, caption, collection):
    monkeypatch.setenv("WATCHBANE_INTERFACE_LANGUAGE", language)
    attempts = []

    def unexpected(*args, **kwargs):
        attempts.append(1)
        raise AssertionError("Opening the About dialog must not call the network")

    monkeypatch.setattr(QNetworkAccessManager, "get", unexpected)
    monkeypatch.setattr(QNetworkAccessManager, "post", unexpected)
    monkeypatch.setattr("requests.Session.request", unexpected)
    window = WatchedMoviesWindow(initial_size=(920, 680))
    qtbot.addWidget(window)
    window.show()
    window.schedule_tmdb_startup_gate()
    assert window._tmdb_local_mode and window._tmdb_gate_view is None
    tabs = window._main_tabs
    assert tabs.count() == 2 and tabs.tabText(1) == collection

    button = tabs.cornerWidget(Qt.Corner.TopRightCorner)
    assert isinstance(button, QPushButton) and button.isVisible() and button.isEnabled()
    assert button.accessibleName() == button.text() == caption
    tabs.setCurrentIndex(1)
    assert button.isVisible()  # Available both before searching and from the library.
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: bool(window.findChild(QMessageBox, "watchbaneAboutDialog")))
    dialog = window.findChild(QMessageBox, "watchbaneAboutDialog")
    assert dialog.isVisible() and dialog.windowTitle() == caption and dialog.text() == "Watchbane"
    credits = dialog.informativeText()
    assert "The Movie Database (TMDB)" in credits and "https://www.themoviedb.org" in credits
    assert credits.count(_EN) == 1
    assert (_RU in credits) == (language == "ru")
    assert dialog.textFormat() == Qt.TextFormat.PlainText
    assert not (dialog.textInteractionFlags() & Qt.TextInteractionFlag.LinksAccessibleByMouse)
    qtbot.mouseClick(dialog.button(QMessageBox.StandardButton.Close), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.findChild(QMessageBox, "watchbaneAboutDialog") is None)
    assert tabs.currentIndex() == 1 and not attempts
    window.shutdown_background_workers()
