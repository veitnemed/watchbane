from pathlib import Path

import pytest
from PyQt6.QtCore import Qt

from desktop.story import view as story_ui
from storage.sqlite.settings_repository import get_setting, set_setting


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.setattr(story_ui, "_semantic_install_available", lambda: True)
    monkeypatch.delenv(story_ui._MODEL_ENV, raising=False)
    monkeypatch.delenv("WATCHBANE_STORY_SEED_CATALOG", raising=False)


def open_view(qtbot):
    view = story_ui.StorySearchView()
    qtbot.addWidget(view.widget)
    view.widget.resize(1150, 800)
    view.widget.show()
    return view


def choose_folder(monkeypatch, directory):
    monkeypatch.setattr(story_ui.QFileDialog, "getExistingDirectory", lambda *args: str(directory))


def mouse(qtbot, button):
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_choose_reopens_lazily_and_isolated_to_the_current_profile(qtbot, monkeypatch, tmp_path):
    from storage import profiles

    from candidates import story_semantic
    from requests import Session

    def forbidden(*args, **kwargs):
        raise AssertionError("Reading or choosing a path must not load weights or access the network")

    monkeypatch.setattr(story_semantic, "LocalE5", forbidden)
    monkeypatch.setattr(Session, "request", forbidden)

    profile_a = profiles.create_profile("profile-a")
    profile_b = profiles.create_profile("profile-b")
    profiles.set_active_profile(profile_a)
    first = open_view(qtbot)
    directory = tmp_path / "Модель E5"
    directory.mkdir()
    choose_folder(monkeypatch, directory)
    mouse(qtbot, first.install_model_button)
    assert first._model_install_dialog.isVisible()
    mouse(qtbot, first._install_manual)
    assert get_setting(story_ui._MODEL_SETTING) == str(directory)
    assert first.text_search_button.isVisible()
    first.widget.close()

    reopened = open_view(qtbot)
    assert reopened.model_dir == str(directory)
    assert reopened.text_search_button.isVisible()
    assert not reopened.install_model_button.isVisible()
    assert reopened._worker is None

    profiles.set_active_profile(profile_b)
    different = open_view(qtbot)
    assert different.model_dir is None
    assert different.install_model_button.isVisible()
    # Even a departing window cannot write a preference into the next profile.
    mouse(qtbot, reopened.text_search_button)
    assert get_setting(story_ui._MODEL_SETTING, "missing") == "missing"
    profiles.set_active_profile(profile_a)
    assert get_setting(story_ui._MODEL_SETTING, "missing") is None
    assert open_view(qtbot).model_dir is None


def test_cli_override_is_session_only_until_explicit_selection_or_disable(qtbot, monkeypatch, tmp_path):
    stored, override, replacement = [str(tmp_path / name) for name in ("saved", "override", "replacement")]
    set_setting(story_ui._MODEL_SETTING, stored)
    monkeypatch.setenv(story_ui._MODEL_ENV, override)
    view = open_view(qtbot)
    assert view.model_dir == override
    assert get_setting(story_ui._MODEL_SETTING) == stored

    mouse(qtbot, view.text_search_button)
    assert view.model_dir is None
    assert get_setting(story_ui._MODEL_SETTING, "missing") is None
    assert view.install_model_button.isVisible() and not view.text_search_button.isVisible()
    choose_folder(monkeypatch, "")
    mouse(qtbot, view.install_model_button)
    assert view._model_install_dialog.isVisible()
    mouse(qtbot, view._install_manual)
    assert view.model_dir is None
    assert get_setting(story_ui._MODEL_SETTING, "missing") is None

    choose_folder(monkeypatch, replacement)
    assert view._model_install_dialog.isVisible()
    mouse(qtbot, view._install_manual)
    assert view.model_dir == replacement
    assert get_setting(story_ui._MODEL_SETTING) == replacement

    assert open_view(qtbot).model_dir == override
    monkeypatch.delenv(story_ui._MODEL_ENV)
    assert open_view(qtbot).model_dir == replacement


def test_missing_saved_folder_can_retry_same_query_and_reconnect(qtbot, monkeypatch, tmp_path):
    from candidates import story_service

    absent = tmp_path / "absent"
    set_setting(story_ui._MODEL_SETTING, str(absent))
    monkeypatch.setattr(story_service, "get_pool_view", lambda: [{
        "title": "QA", "tmdb_id": 177, "media_type": "movie", "overview": "Врач лечит пациентов."
    }])
    view = open_view(qtbot)
    assert Path(view.model_dir) == absent
    view.query.setText("врач")
    mouse(qtbot, view.search_button)
    qtbot.waitUntil(lambda: view._worker is None)
    assert "Не удалось" in view.status.text()
    assert view.text_search_button.isVisible() and view.install_model_button.isVisible()
    assert get_setting(story_ui._MODEL_SETTING) == str(absent)
    mouse(qtbot, view.text_search_button)
    qtbot.waitUntil(lambda: view._worker is None)
    assert view.query.text() == "врач" and view.cards_layout.count() == 2
    assert "Поиск по словам" in view.scope.text()
    assert open_view(qtbot).model_dir is None

    replacement = tmp_path / "other"
    choose_folder(monkeypatch, replacement)
    mouse(qtbot, view.install_model_button)
    assert view._model_install_dialog.isVisible()
    mouse(qtbot, view._install_manual)
    assert open_view(qtbot).model_dir == str(replacement)


def test_malformed_setting_does_not_block_startup(qtbot):
    set_setting(story_ui._MODEL_SETTING, {"path": "unexpected"})
    view = open_view(qtbot)
    assert view.model_dir is None
    assert view.install_model_button.isVisible()


def publisher_layout(monkeypatch, tmp_path, *, frozen=True):
    import sys

    executable = tmp_path / "Папка Watchbane" / "Watchbane.exe"
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    bundle = tmp_path / "_internal"
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    directory = executable.parent / "assets" / "story-model"
    directory.mkdir(parents=True)
    (bundle / "assets" / "story-model").mkdir(parents=True)
    return directory


def test_publisher_model_requires_frozen_external_directory(qtbot, monkeypatch, tmp_path):
    import sys

    directory = publisher_layout(monkeypatch, tmp_path, frozen=False)
    assert open_view(qtbot).model_dir is None
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    directory.rmdir()
    assert open_view(qtbot).model_dir is None   # _MEIPASS is not consulted.
    directory.write_text("not a directory", encoding="utf-8")
    assert open_view(qtbot).model_dir is None


def test_publisher_default_never_writes_preference_and_respects_explicit_word_mode(qtbot, monkeypatch, tmp_path):
    directory = publisher_layout(monkeypatch, tmp_path)
    default_view = open_view(qtbot)
    assert default_view.model_dir == str(directory)
    assert get_setting(story_ui._MODEL_SETTING, "absent") == "absent"
    mouse(qtbot, default_view.text_search_button)
    assert get_setting(story_ui._MODEL_SETTING, "absent") is None
    assert open_view(qtbot).model_dir is None

    user_folder = str(tmp_path / "manual")
    set_setting(story_ui._MODEL_SETTING, user_folder)
    assert open_view(qtbot).model_dir == user_folder

    override = str(tmp_path / "explicit")
    monkeypatch.setenv(story_ui._MODEL_ENV, override)
    assert open_view(qtbot).model_dir == override
    assert get_setting(story_ui._MODEL_SETTING) == user_folder

    set_setting(story_ui._MODEL_SETTING, None)
    assert open_view(qtbot).model_dir == override
    assert get_setting(story_ui._MODEL_SETTING, "absent") is None
    monkeypatch.delenv(story_ui._MODEL_ENV)
    assert open_view(qtbot).model_dir is None


def test_publisher_model_uses_existing_validation_lazily_and_recovers(qtbot, monkeypatch, tmp_path):
    from candidates import story_semantic, story_service

    directory = publisher_layout(monkeypatch, tmp_path)
    monkeypatch.setattr(story_service, "get_pool_view", lambda: [{
        "title": "QA", "tmdb_id": 177, "media_type": "movie", "overview": "Врач лечит пациентов."
    }])
    attempts = []

    def invalid_model(path):
        attempts.append(path)
        raise ValueError("Missing or unverified local E5 artifact")

    monkeypatch.setattr(story_semantic, "LocalE5", invalid_model)
    view = open_view(qtbot)
    assert view.model_dir == str(directory) and not attempts
    assert view._worker is None and "будет проверена при поиске" in view.scope.text()

    view.query.setText("врач")
    mouse(qtbot, view.search_button)
    qtbot.waitUntil(lambda: view._worker is None)
    assert attempts == [str(directory)]
    assert "Не удалось" in view.status.text() and view.text_search_button.isVisible()
    assert get_setting(story_ui._MODEL_SETTING, "absent") == "absent"

    mouse(qtbot, view.text_search_button)
    qtbot.waitUntil(lambda: view._worker is None)
    assert view.query.text() == "врач" and view.cards_layout.count() == 2
    assert open_view(qtbot).model_dir is None
