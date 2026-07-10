from PyQt6.QtWidgets import QCheckBox, QComboBox

from desktop.candidates.filters_form import build_filters_form


def _build_form(qtbot):
    form = build_filters_form(year_max=2026, on_year_range_changed=lambda _lower, _upper: None)
    qtbot.addWidget(form.scroll)
    form.country_selector.set_options(
        [
            {"code": "JP", "label": "Japan"},
            {"code": "KR", "label": "Korea"},
            {"code": "RU", "label": "Russia"},
            {"code": "US", "label": "United States"},
            {"code": "GB", "label": "United Kingdom"},
        ]
    )
    return form


def _set_combo(combo: QComboBox, value: str | None) -> None:
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def _combo_item_enabled(combo: QComboBox, value: str) -> bool:
    index = combo.findData(value)
    assert index >= 0
    return combo.model().item(index).isEnabled()


def test_replenish_controls_exist_and_default_safe(qtbot) -> None:
    form = _build_form(qtbot)

    assert form.scroll.findChild(QComboBox, "candidateReplenishPreset") is form.replenish_preset_combo
    assert form.scroll.findChild(QComboBox, "candidateReplenishAnimationMode") is form.replenish_animation_mode_combo
    assert form.scroll.findChild(QComboBox, "candidateReplenishVibe") is form.replenish_vibe_combo
    assert (
        form.scroll.findChild(QComboBox, "candidateReplenishReleasePreference")
        is form.replenish_release_preference_combo
    )
    assert (
        form.scroll.findChild(QComboBox, "candidateReplenishOriginPreference")
        is form.replenish_origin_preference_combo
    )
    assert form.scroll.findChild(QCheckBox, "candidateReplenishEnabled") is form.replenish_enabled_check
    assert (
        form.scroll.findChild(QCheckBox, "candidateReplenishAdvancedOverride")
        is form.replenish_advanced_override_check
    )

    assert form.replenish_preset_combo.currentData() == "manual"
    assert form.replenish_animation_mode_combo.currentData() == "any"
    assert form.replenish_vibe_combo.currentData() == "mixed"
    assert form.replenish_release_preference_combo.currentData() == "mixed"
    assert form.replenish_origin_preference_combo.currentData() == "any"
    assert form.replenish_enabled_check.isChecked() is False
    assert form.replenish_advanced_override_check.isChecked() is False


def test_anime_preset_suggests_jp_and_animation_only(qtbot) -> None:
    form = _build_form(qtbot)

    _set_combo(form.replenish_preset_combo, "anime")

    assert form.country_selector.selected_country_codes() == ["JP"]
    assert form.media_type_combo.currentData() is None
    assert form.replenish_animation_mode_combo.currentData() == "animation_only"


def test_k_drama_preset_suggests_kr_live_action_tv(qtbot) -> None:
    form = _build_form(qtbot)

    _set_combo(form.replenish_preset_combo, "k_drama")

    assert form.country_selector.selected_country_codes() == ["KR"]
    assert form.media_type_combo.currentData() == "tv"
    assert form.replenish_animation_mode_combo.currentData() == "live_action_only"


def test_family_animation_preset_suggests_animation_only(qtbot) -> None:
    form = _build_form(qtbot)

    _set_combo(form.replenish_preset_combo, "family_animation")

    assert form.replenish_animation_mode_combo.currentData() == "animation_only"
    assert "JP" in form.country_selector.selected_country_codes()


def test_manual_preset_does_not_overwrite_existing_choices(qtbot) -> None:
    form = _build_form(qtbot)
    _set_combo(form.replenish_preset_combo, "anime")
    _set_combo(form.replenish_preset_combo, "manual")
    form.country_selector.set_selected_codes(["RU"])
    _set_combo(form.media_type_combo, "movie")
    _set_combo(form.replenish_animation_mode_combo, "live_action_only")

    assert form.country_selector.selected_country_codes() == ["RU"]
    assert form.media_type_combo.currentData() == "movie"
    assert form.replenish_animation_mode_combo.currentData() == "live_action_only"


def test_country_selection_blocks_conflicting_replenish_presets(qtbot) -> None:
    form = _build_form(qtbot)

    form.country_selector.set_selected_codes(["RU"])

    assert _combo_item_enabled(form.replenish_preset_combo, "hollywood_mainstream") is False
    assert _combo_item_enabled(form.replenish_preset_combo, "russian_mainstream") is True
    assert _combo_item_enabled(form.replenish_preset_combo, "manual") is True


def test_replenish_preset_disables_conflicting_country_chips(qtbot) -> None:
    form = _build_form(qtbot)

    _set_combo(form.replenish_preset_combo, "hollywood_mainstream")

    assert form.country_selector.selected_country_codes() == ["US"]
    assert form.country_selector._chips["US"].isEnabled() is True
    assert form.country_selector._chips["RU"].isEnabled() is False
    assert form.country_selector._chips["RU"].toolTip() != ""

    _set_combo(form.replenish_preset_combo, "manual")

    assert form.country_selector._chips["RU"].isEnabled() is True
