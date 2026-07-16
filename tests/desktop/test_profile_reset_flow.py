from __future__ import annotations

import inspect

from PyQt6.QtWidgets import QComboBox, QPushButton

from storage import profiles


def test_profile_selector_lists_existing_profiles(monkeypatch, tmp_path, qapp) -> None:
    from desktop.startup.profile_selector import ProfileSelectionDialog

    profiles.set_base_data_dir(tmp_path)
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path))
    profiles.create_profile("friend", display_name="Friend")
    try:
        dialog = ProfileSelectionDialog()
        combo = dialog.findChild(QComboBox, "startupProfileCombo")
        continue_button = dialog.findChild(QPushButton, "startupProfileContinueButton")

        assert combo is not None
        assert continue_button is not None
        assert {combo.itemData(index) for index in range(combo.count())} == {"main", "friend"}

        combo.setCurrentIndex(combo.findData("friend"))
        continue_button.click()

        assert dialog.selected_profile == "friend"
        assert dialog.result() == dialog.DialogCode.Accepted
    finally:
        profiles.set_base_data_dir(None)


def test_bootstrap_processes_reset_and_selector_before_runtime_init() -> None:
    from desktop.shell import bootstrap

    source = inspect.getsource(bootstrap.main)

    process_reset = source.index("process_pending_profile_reset()")
    show_selector = source.index("ProfileSelectionDialog()")
    runtime_init = source.index("ensure_runtime_data_layout()")

    assert process_reset < show_selector < runtime_init


def test_settings_tab_exposes_full_profile_reset_panel(qapp) -> None:
    from desktop.settings.tab_view import SettingsTabView

    view = SettingsTabView()

    try:
        assert view.widget.findChild(QPushButton, "profileResetButton") is not None
    finally:
        view.widget.deleteLater()
