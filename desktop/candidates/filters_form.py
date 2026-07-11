"""Scrollable filter form widgets for the candidate Filters tab."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from candidates.onboarding.taste_presets import get_taste_preset
from desktop.candidates.filter_icon_assets import filter_section_icon_label
from desktop.candidates.filters_controls import (
    SCORE_SLIDER_MAX,
    VOTES_SLIDER_MAX_INDEX,
    add_threshold_filter_row,
    field_label,
    make_min_threshold_slider,
    update_score_range_label,
    update_votes_range_label,
)
from desktop.candidates.session import DEFAULT_BROWSE_FILTERS
from desktop.i18n import tr
from desktop.shared.widgets.country_chip_selector import CountryChipSelector
from desktop.shared.widgets.genre_chip_selector import GenreChipSelector
from desktop.shared.widgets.range_slider import RangeSlider
from desktop.shared.widgets.segmented_control import SegmentedControl
from desktop.shared.widgets.stepped_rotary_control import SteppedRotaryControl
from desktop.theme import TRANSPARENT_STYLE
from desktop.theme.scaling import get_ui_scale, layout_px

CANDIDATE_YEAR_MIN = 2000

REPLENISH_PRESETS = (
    ("candidates.filters.replenish.preset.manual", "manual"),
    ("candidates.filters.replenish.preset.hollywood_mainstream", "hollywood_mainstream"),
    ("candidates.filters.replenish.preset.russian_mainstream", "russian_mainstream"),
    ("candidates.filters.replenish.preset.anime", "anime"),
    ("candidates.filters.replenish.preset.k_drama", "k_drama"),
    ("candidates.filters.replenish.preset.turkish_dramas", "turkish_dramas"),
    ("candidates.filters.replenish.preset.british_european_detective", "british_european_detective"),
    ("candidates.filters.replenish.preset.family_animation", "family_animation"),
    ("candidates.filters.replenish.preset.dark_thriller_crime", "dark_thriller_crime"),
)
ANIMATION_MODE_OPTIONS = (
    ("candidates.filters.replenish.animation.any", "any"),
    ("candidates.filters.replenish.animation.animation_only", "animation_only"),
    ("candidates.filters.replenish.animation.live_action_only", "live_action_only"),
)
VIBE_OPTIONS = (
    ("candidates.filters.replenish.vibe.mixed", "mixed"),
    ("candidates.filters.replenish.vibe.light", "light"),
    ("candidates.filters.replenish.vibe.dark", "dark"),
)
RELEASE_OPTIONS = (
    ("candidates.filters.replenish.release.mixed", "mixed"),
    ("candidates.filters.replenish.release.new", "new"),
    ("candidates.filters.replenish.release.classic", "classic"),
)
ORIGIN_OPTIONS = (
    ("candidates.filters.replenish.origin.any", "any"),
    ("candidates.filters.replenish.origin.domestic", "domestic"),
    ("candidates.filters.replenish.origin.foreign", "foreign"),
    ("candidates.filters.replenish.origin.mixed", "mixed"),
)
SIMPLE_MEDIA_OPTIONS = (
    ("preferences.media.both", "both"),
    ("preferences.media.movie", "movie"),
    ("preferences.media.tv", "tv"),
)
SIMPLE_COLLECTION_OPTIONS = (
    ("preferences.collection.mixed", "mixed"),
    ("preferences.collection.new", "new"),
    ("preferences.collection.classic", "classic"),
    ("preferences.collection.unusual", "unusual"),
)
SIMPLE_ORIGIN_OPTIONS = (
    ("preferences.origin.any", "any"),
    ("preferences.origin.russia", "russia"),
    ("preferences.origin.west", "west"),
    ("preferences.origin.asia", "asia"),
)
SIMPLE_MOOD_OPTIONS = (
    ("preferences.mood.any", "any"),
    ("preferences.mood.light", "light"),
    ("preferences.mood.dark", "dark"),
    ("preferences.mood.dynamic", "dynamic"),
    ("preferences.mood.drama", "drama"),
)


@dataclass
class FiltersFormWidgets:
    """Widget handles for the filters scroll form."""

    scroll: QScrollArea
    simple_media_combo: QComboBox
    simple_collection_combo: QComboBox
    simple_origin_combo: QComboBox
    simple_mood_combo: QComboBox
    direction_control: SteppedRotaryControl
    discovery_media_control: SegmentedControl
    discovery_animation_control: SegmentedControl
    discovery_release_control: SegmentedControl
    vector_openness_control: SteppedRotaryControl
    vector_rarity_control: SteppedRotaryControl
    vector_diversity_control: SteppedRotaryControl
    vector_mood_control: SegmentedControl
    variation_button: QPushButton
    advanced_mode_toggle: QToolButton
    country_selector: CountryChipSelector
    media_type_combo: QComboBox
    year_range_label: QLabel
    year_slider: RangeSlider
    replenish_preset_combo: QComboBox
    replenish_animation_mode_combo: QComboBox
    replenish_vibe_combo: QComboBox
    replenish_release_preference_combo: QComboBox
    replenish_origin_preference_combo: QComboBox
    replenish_enabled_check: QCheckBox
    replenish_advanced_override_check: QCheckBox
    include_genre_selector: GenreChipSelector
    exclude_genre_selector: GenreChipSelector
    tmdb_score_range_label: QLabel
    tmdb_score_slider: RangeSlider
    tmdb_votes_range_label: QLabel
    tmdb_votes_slider: RangeSlider
    only_complete_check: QCheckBox
    only_unwatched_check: QCheckBox
    hide_hidden_check: QCheckBox


def build_filters_form(
    *,
    year_max: int,
    on_year_range_changed: Callable[[int, int], None],
) -> FiltersFormWidgets:
    """Build the scrollable filter form and return widget handles."""
    scroll = QScrollArea()
    scroll.setObjectName("candidateSearchFiltersScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    form_host = QWidget()
    form_host.setObjectName("candidateSearchFiltersHost")
    form = QVBoxLayout(form_host)
    form.setContentsMargins(0, 0, layout_px(10), 0)
    form.setSpacing(layout_px(8))
    compact_combo_max_width = layout_px(480)
    section_index = 0

    def add_section(
        title: str,
        *,
        object_name: str = "candidateFilterSection",
        icon_name: str = "document",
        badge_object_name: str = "candidateFilterSectionBadge",
        icon_color: str = "#22D3C5",
    ) -> tuple[QFrame, QVBoxLayout]:
        nonlocal section_index
        section_index += 1
        section = QFrame()
        section.setObjectName(object_name)
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(
            layout_px(14),
            layout_px(10),
            layout_px(14),
            layout_px(10),
        )
        section_layout.setSpacing(layout_px(8))

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(layout_px(8))
        badge = filter_section_icon_label(
            icon_name,
            badge_object_name,
            layout_px(24),
            icon_color,
        )
        title_label = QLabel(f"{section_index}. {title}")
        title_label.setObjectName("candidateFilterSectionTitle")
        title_row.addWidget(badge)
        title_row.addWidget(title_label)
        title_row.addStretch(1)
        section_layout.addLayout(title_row)
        form.addWidget(section)
        return section, section_layout

    def add_advanced_group(parent_layout: QVBoxLayout, title: str) -> QVBoxLayout:
        group = QWidget()
        group.setObjectName("candidateAdvancedFiltersGroup")
        group.setStyleSheet(TRANSPARENT_STYLE)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(layout_px(8))
        title_label = QLabel(title)
        title_label.setObjectName("candidateAdvancedFiltersGroupTitle")
        group_layout.addWidget(title_label)
        parent_layout.addWidget(group)
        return group_layout

    def add_divider(section_layout: QVBoxLayout) -> None:
        divider = QFrame()
        divider.setObjectName("candidateFilterDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        section_layout.addSpacing(layout_px(1))
        section_layout.addWidget(divider)
        section_layout.addSpacing(layout_px(1))

    def make_hint(text: str) -> QLabel:
        hint = QLabel(text)
        hint.setObjectName("candidateSearchHint")
        hint.setWordWrap(True)
        return hint

    def add_hint(section_layout: QVBoxLayout, text: str) -> QLabel:
        hint = make_hint(text)
        section_layout.addWidget(hint)
        return hint

    def constrain_combo_width(combo: QComboBox) -> None:
        combo.setMaximumWidth(compact_combo_max_width)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def add_combo(options: tuple[tuple[str, str], ...], object_name: str) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(object_name)
        for label_key, value in options:
            combo.addItem(tr(label_key), value)
        constrain_combo_width(combo)
        return combo

    simple_section, simple_layout = add_section(
        tr("preferences.title"),
        object_name="candidateSimplePreferencesSection",
        icon_name="heart",
        icon_color="#F4A7C5",
    )
    simple_lead = QLabel(tr("preferences.lead"))
    simple_lead.setObjectName("candidateSimplePreferencesLead")
    simple_lead.setWordWrap(True)
    simple_layout.addWidget(simple_lead)
    simple_grid = QGridLayout()
    simple_grid.setContentsMargins(0, 0, 0, 0)
    simple_grid.setHorizontalSpacing(layout_px(12))
    simple_grid.setVerticalSpacing(layout_px(10))
    simple_columns = 1 if get_ui_scale() >= 1.25 else 2
    for column in range(simple_columns):
        simple_grid.setColumnStretch(column, 1)

    simple_media_combo = add_combo(SIMPLE_MEDIA_OPTIONS, "simplePreferenceMedia")
    simple_collection_combo = add_combo(SIMPLE_COLLECTION_OPTIONS, "simplePreferenceCollection")
    simple_origin_combo = add_combo(SIMPLE_ORIGIN_OPTIONS, "simplePreferenceOrigin")
    simple_mood_combo = add_combo(SIMPLE_MOOD_OPTIONS, "simplePreferenceMood")

    def add_simple_field(index: int, label_key: str, combo: QComboBox) -> None:
        cell = QWidget()
        cell.setObjectName("candidateSimplePreferenceField")
        cell.setStyleSheet(TRANSPARENT_STYLE)
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(layout_px(5))
        cell_layout.addWidget(field_label(tr(label_key)))
        cell_layout.addWidget(combo)
        simple_grid.addWidget(cell, index // simple_columns, index % simple_columns)

    add_simple_field(0, "preferences.media.label", simple_media_combo)
    add_simple_field(1, "preferences.collection.label", simple_collection_combo)
    add_simple_field(2, "preferences.origin.label", simple_origin_combo)
    add_simple_field(3, "preferences.mood.label", simple_mood_combo)
    simple_layout.addLayout(simple_grid)
    simple_section.setVisible(False)

    direction_options = (
        ("recommendations.discovery.direction.world", "manual"),
        ("recommendations.discovery.direction.hollywood", "hollywood_mainstream"),
        ("recommendations.discovery.direction.russia", "russian_mainstream"),
        ("recommendations.discovery.direction.anime", "anime"),
        ("recommendations.discovery.direction.k_drama", "k_drama"),
        ("recommendations.discovery.direction.turkish", "turkish_dramas"),
        ("recommendations.discovery.direction.europe", "british_european_detective"),
        ("recommendations.discovery.direction.family_animation", "family_animation"),
        ("recommendations.discovery.direction.dark_crime", "dark_thriller_crime"),
        ("recommendations.discovery.direction.manual", "manual"),
    )

    panels_host = QWidget()
    panels_host.setObjectName("recommendationPreferencePanels")
    panels_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, panels_host)
    panels_layout.setContentsMargins(0, 0, 0, 0)
    panels_layout.setSpacing(layout_px(12))

    class ResponsivePanels(QWidget):
        def resizeEvent(self, event) -> None:
            super().resizeEvent(event)
            direction = (
                QBoxLayout.Direction.TopToBottom
                if self.width() < layout_px(980) or get_ui_scale() >= 1.5
                else QBoxLayout.Direction.LeftToRight
            )
            panels_layout.setDirection(direction)

    responsive_host = ResponsivePanels()
    responsive_host.setObjectName("recommendationResponsivePanels")
    responsive_layout = QVBoxLayout(responsive_host)
    responsive_layout.setContentsMargins(0, 0, 0, 0)
    responsive_layout.addWidget(panels_host)

    def panel_header(layout: QVBoxLayout, module_key: str, title_key: str) -> None:
        module = QLabel(tr(module_key))
        module.setObjectName("recommendationModuleLabel")
        layout.addWidget(module)
        title = QLabel(tr(title_key))
        title.setObjectName("recommendationPanelTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

    discovery_panel = QFrame()
    discovery_panel.setObjectName("recommendationDiscoveryPanel")
    discovery_layout = QVBoxLayout(discovery_panel)
    discovery_layout.setContentsMargins(layout_px(16), layout_px(14), layout_px(16), layout_px(14))
    discovery_layout.setSpacing(layout_px(9))
    panel_header(discovery_layout, "recommendations.discovery.module", "recommendations.discovery.title")
    discovery_layout.addWidget(field_label(tr("recommendations.discovery.direction.label")))
    direction_control = SteppedRotaryControl(
        [tr(label_key) for label_key, _value in direction_options],
        value=0,
    )
    direction_control.setObjectName("recommendationDirectionControl")
    direction_control.setProperty("directionValues", [value for _label, value in direction_options])
    direction_control.setAccessibleName(tr("recommendations.discovery.direction.label"))
    direction_control.setAccessibleDescription(tr("recommendations.discovery.direction.tooltip"))
    direction_control.setToolTip(tr("recommendations.discovery.direction.tooltip"))
    discovery_layout.addWidget(direction_control, alignment=Qt.AlignmentFlag.AlignHCenter)

    discovery_media_control = SegmentedControl((
        (tr("recommendations.discovery.media.movie"), "movie"),
        (tr("recommendations.discovery.media.both"), "both"),
        (tr("recommendations.discovery.media.tv"), "tv"),
    ))
    discovery_media_control.setObjectName("recommendationDiscoveryMedia")
    discovery_animation_control = SegmentedControl((
        (tr("recommendations.discovery.animation.live"), "live_action_only"),
        (tr("recommendations.discovery.animation.any"), "any"),
        (tr("recommendations.discovery.animation.animation"), "animation_only"),
    ))
    discovery_animation_control.setObjectName("recommendationDiscoveryAnimation")
    discovery_release_control = SegmentedControl((
        (tr("recommendations.discovery.release.classic"), "classic"),
        (tr("recommendations.discovery.release.mixed"), "mixed"),
        (tr("recommendations.discovery.release.new"), "new"),
    ))
    discovery_release_control.setObjectName("recommendationDiscoveryRelease")
    for label_key, control in (
        ("recommendations.discovery.media.label", discovery_media_control),
        ("recommendations.discovery.animation.label", discovery_animation_control),
        ("recommendations.discovery.release.label", discovery_release_control),
    ):
        discovery_layout.addWidget(field_label(tr(label_key)))
        discovery_layout.addWidget(control)
    discovery_layout.addStretch(1)

    vector_panel = QFrame()
    vector_panel.setObjectName("recommendationVectorPanel")
    vector_layout = QVBoxLayout(vector_panel)
    vector_layout.setContentsMargins(layout_px(16), layout_px(14), layout_px(16), layout_px(14))
    vector_layout.setSpacing(layout_px(9))
    panel_header(vector_layout, "recommendations.vector.module", "recommendations.vector.title")
    dials_row = QHBoxLayout()
    dials_row.setContentsMargins(0, 0, 0, 0)
    dials_row.setSpacing(layout_px(6))

    def add_vector_dial(label_key: str, value_keys: tuple[str, ...], object_name: str) -> SteppedRotaryControl:
        host = QWidget()
        host.setObjectName("recommendationVectorDialHost")
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(layout_px(2))
        label = field_label(tr(label_key))
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        host_layout.addWidget(label)
        dial = SteppedRotaryControl([tr(key) for key in value_keys], value=2)
        dial.setObjectName(object_name)
        dial.setAccessibleName(tr(label_key))
        dial.setAccessibleDescription(tr(f"{label_key}.tooltip"))
        dial.setToolTip(tr(f"{label_key}.tooltip"))
        host_layout.addWidget(dial, alignment=Qt.AlignmentFlag.AlignHCenter)
        dials_row.addWidget(host, 1)
        return dial

    vector_openness_control = add_vector_dial(
        "recommendations.vector.openness.label",
        tuple(f"recommendations.vector.openness.{index}" for index in range(5)),
        "recommendationVectorOpenness",
    )
    vector_rarity_control = add_vector_dial(
        "recommendations.vector.rarity.label",
        tuple(f"recommendations.vector.rarity.{index}" for index in range(5)),
        "recommendationVectorRarity",
    )
    vector_diversity_control = add_vector_dial(
        "recommendations.vector.diversity.label",
        tuple(f"recommendations.vector.diversity.{index}" for index in range(5)),
        "recommendationVectorDiversity",
    )
    vector_layout.addLayout(dials_row)
    vector_layout.addWidget(field_label(tr("recommendations.vector.mood.label")))
    vector_mood_control = SegmentedControl((
        (tr("recommendations.vector.mood.any"), "any"),
        (tr("recommendations.vector.mood.light"), "light"),
        (tr("recommendations.vector.mood.dynamic"), "dynamic"),
        (tr("recommendations.vector.mood.drama"), "drama"),
        (tr("recommendations.vector.mood.dark"), "dark"),
    ))
    vector_mood_control.setObjectName("recommendationVectorMood")
    vector_layout.addWidget(vector_mood_control)
    variation_button = QPushButton(tr("recommendations.variation.action"))
    variation_button.setObjectName("recommendationVariationButton")
    vector_layout.addWidget(variation_button)

    panels_layout.addWidget(discovery_panel, 1)
    panels_layout.addWidget(vector_panel, 1)
    form.insertWidget(form.indexOf(simple_section), responsive_host)

    advanced_mode_toggle = QToolButton()
    advanced_mode_toggle.setObjectName("candidateRecommendationAdvancedModeToggle")
    advanced_mode_toggle.setCheckable(True)
    advanced_mode_toggle.setChecked(False)
    advanced_mode_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    advanced_mode_toggle.setArrowType(Qt.ArrowType.RightArrow)
    advanced_mode_toggle.setText(tr("recommendations.discovery.exact_settings"))
    form.addWidget(advanced_mode_toggle)

    _replenish_section, replenish_layout = add_section(
        tr("candidates.filters.replenish.title"),
        icon_name="heart",
        icon_color="#F4A7C5",
    )

    _basic_section, basic_layout = add_section(
        tr("candidates.filters.basic"),
        icon_name="filter",
    )
    country_selector = CountryChipSelector([])
    basic_layout.addWidget(field_label(tr("candidates.filters.country")))
    basic_layout.addWidget(country_selector)
    add_hint(basic_layout, tr("candidates.filters.country_hint"))
    add_divider(basic_layout)

    media_type_combo = QComboBox()
    media_type_combo.setObjectName("candidateSearchMediaType")
    media_type_combo.addItem(tr("watched.filters.media_all"), None)
    media_type_combo.addItem(tr("media_type.tv"), "tv")
    media_type_combo.addItem(tr("media_type.movie"), "movie")
    constrain_combo_width(media_type_combo)
    basic_layout.addWidget(field_label(tr("candidates.filters.media_type")))
    basic_layout.addWidget(media_type_combo)
    add_divider(basic_layout)

    year_header = QHBoxLayout()
    year_header.setContentsMargins(0, 0, 0, 0)
    year_header.setSpacing(layout_px(8))
    year_header.addWidget(field_label(tr("candidates.filters.year")))
    year_header.addStretch()
    year_range_label = QLabel("")
    year_range_label.setObjectName("candidateSearchYearRangeLabel")
    year_header.addWidget(year_range_label)
    basic_layout.addLayout(year_header)

    year_slider = RangeSlider(
        CANDIDATE_YEAR_MIN,
        year_max,
        CANDIDATE_YEAR_MIN,
        year_max,
    )
    year_slider.setObjectName("candidateSearchYearRange")
    year_slider.rangeChanged.connect(on_year_range_changed)
    basic_layout.addWidget(year_slider)

    def set_combo_data(combo: QComboBox, value: str | None) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    replenish_preset_combo = add_combo(REPLENISH_PRESETS, "candidateReplenishPreset")
    replenish_animation_mode_combo = add_combo(ANIMATION_MODE_OPTIONS, "candidateReplenishAnimationMode")
    replenish_vibe_combo = add_combo(VIBE_OPTIONS, "candidateReplenishVibe")
    replenish_release_preference_combo = add_combo(RELEASE_OPTIONS, "candidateReplenishReleasePreference")
    replenish_origin_preference_combo = add_combo(ORIGIN_OPTIONS, "candidateReplenishOriginPreference")
    replenish_enabled_check = QCheckBox(tr("candidates.filters.replenish.enable"))
    replenish_enabled_check.setObjectName("candidateReplenishEnabled")
    replenish_enabled_check.setChecked(False)
    replenish_advanced_override_check = QCheckBox(tr("candidates.filters.replenish.advanced_override"))
    replenish_advanced_override_check.setObjectName("candidateReplenishAdvancedOverride")
    replenish_advanced_override_check.setChecked(False)

    replenish_action_row = QWidget()
    replenish_action_row.setObjectName("candidateReplenishActionRow")
    replenish_action_row.setStyleSheet(TRANSPARENT_STYLE)
    action_layout_cls = QVBoxLayout if get_ui_scale() >= 1.25 else QHBoxLayout
    replenish_action_layout = action_layout_cls(replenish_action_row)
    replenish_action_layout.setContentsMargins(0, 0, 0, 0)
    replenish_action_layout.setSpacing(layout_px(8))
    replenish_action_layout.addWidget(replenish_enabled_check)
    replenish_action_layout.addWidget(replenish_advanced_override_check)
    if isinstance(replenish_action_layout, QHBoxLayout):
        replenish_action_layout.addStretch(1)
    replenish_layout.addWidget(replenish_action_row)
    replenish_layout.addWidget(make_hint(tr("candidates.filters.replenish.hint.advanced_override")))
    add_divider(replenish_layout)

    replenish_grid = QGridLayout()
    replenish_grid.setContentsMargins(0, 0, 0, 0)
    replenish_grid.setHorizontalSpacing(layout_px(12))
    replenish_grid.setVerticalSpacing(layout_px(10))
    if get_ui_scale() >= 1.25:
        replenish_column_count = 1
    elif get_ui_scale() > 1.0:
        replenish_column_count = 2
    else:
        replenish_column_count = 3
    for column in range(replenish_column_count):
        replenish_grid.setColumnStretch(column, 1)

    def replenish_grid_position(index: int) -> tuple[int, int]:
        return index // replenish_column_count, index % replenish_column_count

    def add_replenish_field(
        row: int,
        column: int,
        label_text: str,
        combo: QComboBox,
        *,
        hint_text: str | None = None,
    ) -> None:
        cell = QWidget()
        cell.setObjectName("candidateReplenishField")
        cell.setStyleSheet(TRANSPARENT_STYLE)
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(layout_px(5))
        cell_layout.addWidget(field_label(label_text))
        cell_layout.addWidget(combo)
        if hint_text:
            cell_layout.addWidget(make_hint(hint_text))
        replenish_grid.addWidget(cell, row, column)

    row, column = replenish_grid_position(0)
    add_replenish_field(
        row,
        column,
        tr("candidates.filters.replenish.preset"),
        replenish_preset_combo,
        hint_text=tr("candidates.filters.replenish.hint.anime"),
    )
    row, column = replenish_grid_position(1)
    add_replenish_field(
        row,
        column,
        tr("candidates.filters.replenish.animation_mode"),
        replenish_animation_mode_combo,
        hint_text=tr("candidates.filters.replenish.hint.live_action"),
    )
    row, column = replenish_grid_position(2)
    add_replenish_field(row, column, tr("candidates.filters.replenish.vibe"), replenish_vibe_combo)
    row, column = replenish_grid_position(3)
    add_replenish_field(
        row,
        column,
        tr("candidates.filters.replenish.release_preference"),
        replenish_release_preference_combo,
    )
    row, column = replenish_grid_position(4)
    add_replenish_field(
        row,
        column,
        tr("candidates.filters.replenish.origin_preference"),
        replenish_origin_preference_combo,
    )
    replenish_layout.addLayout(replenish_grid)

    def preset_country_codes(preset_id: str | None) -> set[str]:
        if preset_id in (None, "", "manual"):
            return set()
        preset = get_taste_preset(str(preset_id or ""))
        return {
            str(code).strip().upper()
            for code in (preset.countries if preset is not None else ())
            if str(code).strip()
        }

    def set_combo_item_enabled(combo: QComboBox, index: int, enabled: bool, *, reason: str = "") -> None:
        item = getattr(combo.model(), "item", lambda _index: None)(index)
        if item is None:
            return
        item.setEnabled(enabled)
        item.setToolTip("" if enabled else reason)

    def refresh_replenish_compatibility() -> None:
        selected_countries = {
            str(code).strip().upper()
            for code in country_selector.selected_country_codes()
            if str(code).strip()
        }
        current_preset_id = str(replenish_preset_combo.currentData() or "manual")
        current_preset_countries = preset_country_codes(current_preset_id)
        disabled_country_codes: set[str] = set()
        if current_preset_countries:
            disabled_country_codes = {
                code
                for code in country_selector.country_codes()
                if str(code).strip().upper() not in current_preset_countries
            }
        country_selector.set_disabled_codes(
            disabled_country_codes,
            reason=tr("candidates.filters.replenish.compat.country_locked"),
        )

        conflict_reason = tr("candidates.filters.replenish.compat.preset_locked")
        for index in range(replenish_preset_combo.count()):
            preset_id = str(replenish_preset_combo.itemData(index) or "manual")
            required_countries = preset_country_codes(preset_id)
            enabled = True
            if required_countries and selected_countries:
                enabled = selected_countries.issubset(required_countries)
            set_combo_item_enabled(
                replenish_preset_combo,
                index,
                enabled,
                reason=conflict_reason,
            )

    def apply_preset_suggestion() -> None:
        preset_id = replenish_preset_combo.currentData()
        if preset_id == "manual":
            refresh_replenish_compatibility()
            return
        preset = get_taste_preset(str(preset_id or ""))
        if preset is None:
            refresh_replenish_compatibility()
            return
        country_selector.set_selected_codes(list(preset.countries))
        set_combo_data(media_type_combo, None if preset.media_type == "both" else preset.media_type)
        set_combo_data(replenish_animation_mode_combo, preset.animation_mode)
        set_combo_data(replenish_vibe_combo, preset.vibe)
        set_combo_data(replenish_release_preference_combo, preset.release_preference)
        refresh_replenish_compatibility()

    replenish_preset_combo.currentIndexChanged.connect(apply_preset_suggestion)
    country_selector.selection_changed.connect(refresh_replenish_compatibility)

    _advanced_section, advanced_layout = add_section(
        tr("candidates.filters.additional"),
        icon_name="sliders",
    )
    advanced_toggle = QToolButton()
    advanced_toggle.setObjectName("candidateAdvancedFiltersToggle")
    advanced_toggle.setCheckable(True)
    advanced_toggle.setChecked(False)
    advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    advanced_toggle.setArrowType(Qt.ArrowType.RightArrow)
    advanced_layout.addWidget(advanced_toggle)

    advanced_content = QWidget()
    advanced_content.setObjectName("candidateAdvancedFiltersContent")
    advanced_content.setStyleSheet(TRANSPARENT_STYLE)
    advanced_content.setVisible(False)
    advanced_content_layout = QVBoxLayout(advanced_content)
    advanced_content_layout.setContentsMargins(0, 0, 0, 0)
    advanced_content_layout.setSpacing(layout_px(9))
    advanced_layout.addWidget(advanced_content)

    def set_advanced_visible(checked: bool) -> None:
        advanced_content.setVisible(bool(checked))
        advanced_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        advanced_toggle.setText(
            tr("candidates.filters.additional.hide")
            if checked
            else tr("candidates.filters.additional.show")
        )

    advanced_toggle.toggled.connect(set_advanced_visible)
    set_advanced_visible(False)

    genres_layout = add_advanced_group(advanced_content_layout, tr("candidates.filters.genres"))
    include_genre_selector = GenreChipSelector(object_name="candidateSearchIncludeGenres")
    exclude_genre_selector = GenreChipSelector(object_name="candidateSearchExcludeGenres")
    genres_layout.addWidget(field_label(tr("candidates.filters.include")))
    genres_layout.addWidget(include_genre_selector)
    add_divider(genres_layout)
    genres_layout.addWidget(field_label(tr("candidates.filters.exclude")))
    genres_layout.addWidget(exclude_genre_selector)

    add_divider(advanced_content_layout)

    tmdb_layout = add_advanced_group(advanced_content_layout, tr("candidates.filters.tmdb"))
    tmdb_score_range_label = QLabel("")
    tmdb_score_range_label.setObjectName("candidateSearchFilterValue")
    tmdb_score_slider = make_min_threshold_slider(
        0,
        SCORE_SLIDER_MAX,
        "candidateSearchTmdbScoreRange",
        lambda: update_score_range_label(tmdb_score_slider, tmdb_score_range_label),
    )
    add_threshold_filter_row(tmdb_layout, tr("candidates.filters.score"), tmdb_score_range_label, tmdb_score_slider)
    add_divider(tmdb_layout)

    tmdb_votes_range_label = QLabel("")
    tmdb_votes_range_label.setObjectName("candidateSearchFilterValue")
    tmdb_votes_slider = make_min_threshold_slider(
        0,
        VOTES_SLIDER_MAX_INDEX,
        "candidateSearchTmdbVotesRange",
        lambda: update_votes_range_label(tmdb_votes_slider, tmdb_votes_range_label),
    )
    add_threshold_filter_row(tmdb_layout, tr("candidates.filters.votes"), tmdb_votes_range_label, tmdb_votes_slider)

    add_divider(advanced_content_layout)

    visibility_layout = add_advanced_group(advanced_content_layout, tr("candidates.filters.visibility"))
    only_complete_check = QCheckBox(tr("candidates.filters.only_complete"))
    only_complete_check.setObjectName("candidateSearchOnlyComplete")
    only_complete_check.setChecked(DEFAULT_BROWSE_FILTERS["only_complete"])
    only_unwatched_check = QCheckBox(tr("candidates.filters.only_unwatched"))
    only_unwatched_check.setObjectName("candidateSearchOnlyUnwatched")
    only_unwatched_check.setChecked(DEFAULT_BROWSE_FILTERS["only_unwatched"])
    hide_hidden_check = QCheckBox(tr("candidates.filters.hide_hidden"))
    hide_hidden_check.setObjectName("candidateSearchHideHidden")
    hide_hidden_check.setChecked(DEFAULT_BROWSE_FILTERS["hide_hidden"])
    visibility_layout.addWidget(only_complete_check)
    visibility_layout.addWidget(only_unwatched_check)
    visibility_layout.addWidget(hide_hidden_check)

    _replenish_section.setVisible(False)
    advanced_sections = (_basic_section, _advanced_section)

    def set_advanced_mode(checked: bool) -> None:
        for section in advanced_sections:
            section.setVisible(bool(checked))
        advanced_mode_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        advanced_mode_toggle.setText(
            tr("recommendations.discovery.exact_settings.hide")
            if checked
            else tr("recommendations.discovery.exact_settings")
        )

    advanced_mode_toggle.toggled.connect(set_advanced_mode)
    set_advanced_mode(False)
    form.addStretch(1)

    scroll.setWidget(form_host)
    refresh_replenish_compatibility()

    return FiltersFormWidgets(
        scroll=scroll,
        simple_media_combo=simple_media_combo,
        simple_collection_combo=simple_collection_combo,
        simple_origin_combo=simple_origin_combo,
        simple_mood_combo=simple_mood_combo,
        direction_control=direction_control,
        discovery_media_control=discovery_media_control,
        discovery_animation_control=discovery_animation_control,
        discovery_release_control=discovery_release_control,
        vector_openness_control=vector_openness_control,
        vector_rarity_control=vector_rarity_control,
        vector_diversity_control=vector_diversity_control,
        vector_mood_control=vector_mood_control,
        variation_button=variation_button,
        advanced_mode_toggle=advanced_mode_toggle,
        country_selector=country_selector,
        media_type_combo=media_type_combo,
        year_range_label=year_range_label,
        year_slider=year_slider,
        replenish_preset_combo=replenish_preset_combo,
        replenish_animation_mode_combo=replenish_animation_mode_combo,
        replenish_vibe_combo=replenish_vibe_combo,
        replenish_release_preference_combo=replenish_release_preference_combo,
        replenish_origin_preference_combo=replenish_origin_preference_combo,
        replenish_enabled_check=replenish_enabled_check,
        replenish_advanced_override_check=replenish_advanced_override_check,
        include_genre_selector=include_genre_selector,
        exclude_genre_selector=exclude_genre_selector,
        tmdb_score_range_label=tmdb_score_range_label,
        tmdb_score_slider=tmdb_score_slider,
        tmdb_votes_range_label=tmdb_votes_range_label,
        tmdb_votes_slider=tmdb_votes_slider,
        only_complete_check=only_complete_check,
        only_unwatched_check=only_unwatched_check,
        hide_hidden_check=hide_hidden_check,
    )
