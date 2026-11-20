from threading import Event, get_ident

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton

from candidates import story_model_install
from desktop.story import view as story_ui
from storage.sqlite.settings_repository import get_setting, set_setting


@pytest.fixture(autouse=True)
def isolated_controls(monkeypatch):
    monkeypatch.delenv(story_ui._MODEL_ENV, raising=False)
    monkeypatch.delenv("WATCHBANE_STORY_SEED_CATALOG", raising=False)
    monkeypatch.setattr(story_ui, "_semantic_install_available", lambda: True)


def open_view(qtbot):
    view = story_ui.StorySearchView()
    qtbot.addWidget(view.widget)
    view.widget.resize(1280, 900)
    view.widget.show()
    return view


def click(qtbot, button):
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_no_download_before_confirmation_and_no_automatic_query_after_success(qtbot, monkeypatch):
    from candidates import service

    calls = []
    uid = get_ident()

    def installer(destination, *, on_progress, cancelled):
        calls.append((get_ident(), destination))
        on_progress(486_000_000, 486_000_000)
        return destination

    monkeypatch.setattr(story_model_install, "install_story_model", installer)
    view = open_view(qtbot)
    assert view._model_install_worker is None and not calls
    visible_model_entries = [button for button in view.widget.findChildren(QPushButton)
                             if button.isVisible() and ("по смыслу" in button.text() or "E5" in button.text())]
    assert visible_model_entries == [view.install_model_button]
    view.install_model_button.setFocus()
    qtbot.keyClick(view.install_model_button, Qt.Key.Key_Space)
    assert view._model_install_dialog.isVisible() and not calls
    assert view._install_manual.isEnabled()
    labels = [label.text() for label in view._model_install_dialog.findChildren(QLabel)]
    assert any("487 МБ" in label and "Hugging Face" in label for label in labels)
    assert any("не содержит описаний" in label and "TMDb" in label and "файл каталога" in label
               for label in labels)
    assert get_setting(story_ui._MODEL_SETTING, "absent") == "absent"

    search_calls = []
    monkeypatch.setattr(service, "local_story_catalog", lambda *a, **k: search_calls.append(a))
    view.query.setText("врач")
    click(qtbot, view._install_confirm)
    qtbot.waitUntil(lambda: view._model_install_worker is None)
    assert len(calls) == 1 and calls[0][0] != uid
    assert view.model_dir == str(calls[0][1])
    assert get_setting(story_ui._MODEL_SETTING) == view.model_dir
    assert "проверена" in view._install_status.text()
    assert view.query.text() == "врач" and not search_calls
    assert not view.search_button.isEnabled()
    assert not view._install_confirm.isEnabled()
    view._model_install_dialog.accept()
    assert open_view(qtbot).model_dir == view.model_dir


def test_cancel_does_not_adopt_a_late_verified_install(qtbot, monkeypatch, tmp_path):
    from candidates.story_search import StoryDocument
    monkeypatch.setattr(story_ui.service, "story_catalog_snapshot", lambda: ([
        StoryDocument("existing", "Existing", "Врач лечит пациентов.", "tv", "fixture"),
    ], {}))
    old_directory = str(tmp_path / "manual-model")
    set_setting(story_ui._MODEL_SETTING, old_directory)
    started, release = Event(), Event()
    cancellation_seen = []

    def installer(destination, *, on_progress, cancelled):
        on_progress(12_000_000, 486_000_000)
        started.set()
        assert release.wait(5)
        cancellation_seen.append(cancelled())
        return destination  # A commit racing with the click still must not bind the preference.

    monkeypatch.setattr(story_model_install, "install_story_model", installer)
    view = open_view(qtbot)
    view._search_failed()  # existing model failed, exposing replacement controls.
    click(qtbot, view.install_model_button)
    click(qtbot, view._install_confirm)
    try:
        qtbot.waitUntil(started.is_set)
        qtbot.waitUntil(lambda: "12 МБ" in view._install_status.text())
        assert view._install_progress.isVisible()
        assert view.model_dir == get_setting(story_ui._MODEL_SETTING) == old_directory
        assert view.search_button.isEnabled() and not view._install_manual.isEnabled()
        click(qtbot, view._install_cancel)
    finally:
        release.set()
    qtbot.waitUntil(lambda: view._model_install_worker is None)
    assert cancellation_seen == [True]
    assert view.model_dir == get_setting(story_ui._MODEL_SETTING) == old_directory
    assert "отменена" in view._install_status.text()
    assert view._install_confirm.isEnabled()


def test_offline_failure_preserves_word_mode_and_manual_option(qtbot, monkeypatch, tmp_path):
    set_setting(story_ui._MODEL_SETTING, None)

    def offline(*_args, **_kwargs):
        raise story_model_install.StoryModelInstallError("private transport failure details")

    monkeypatch.setattr(story_model_install, "install_story_model", offline)
    view = open_view(qtbot)
    click(qtbot, view.install_model_button)
    click(qtbot, view._install_confirm)
    qtbot.waitUntil(lambda: view._model_install_worker is None)
    assert not view.model_dir and get_setting(story_ui._MODEL_SETTING, "absent") is None
    assert "Проверьте интернет" in view._install_status.text()
    assert "private" not in view._install_status.text()
    assert view._install_confirm.isEnabled() and view._install_manual.isEnabled()
    manual = str(tmp_path / "готовая папка")
    monkeypatch.setattr(story_ui.QFileDialog, "getExistingDirectory", lambda *args: manual)
    click(qtbot, view._install_manual)
    assert view.model_dir == get_setting(story_ui._MODEL_SETTING) == manual


def test_lexical_runtime_does_not_offer_download(qtbot, monkeypatch):
    monkeypatch.setattr(story_ui, "_semantic_install_available", lambda: False)
    calls = []
    monkeypatch.setattr(story_model_install, "install_story_model", lambda *a, **k: calls.append(a))
    view = open_view(qtbot)
    click(qtbot, view.install_model_button)
    assert "только поиск по словам" in view._install_status.text()
    assert not view._install_confirm.isEnabled()
    view._start_model_install()  # guard even if called without the disabled widget.
    assert not calls and view._model_install_worker is None



@pytest.mark.parametrize(("code", "visible"), [
    ("integrity", "контрольная сумма"),
    ("existing_invalid", "оставлены без изменений"),
    ("tls", "защищённое соединение"),
    ("unknown_private_code", "Проверьте интернет"),
])
def test_model_install_uses_only_safe_hints(qtbot, monkeypatch, code, visible):
    set_setting(story_ui._MODEL_SETTING, None)

    def fail(*_args, **_kwargs):
        raise story_model_install.StoryModelInstallError("private signed URL and local file path", code)

    monkeypatch.setattr(story_model_install, "install_story_model", fail)
    view = open_view(qtbot)
    click(qtbot, view.install_model_button)
    click(qtbot, view._install_confirm)
    qtbot.waitUntil(lambda: view._model_install_worker is None)
    text = view._install_status.text()
    assert visible in text and "режим не изменился" in text
    assert "private" not in text and code not in text and view.model_dir is None
