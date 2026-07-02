"""Threshold slider helpers for the candidate filters form."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from desktop.shared.widgets.range_slider import RangeSlider

SCORE_SLIDER_MAX = 100
SCORE_SLIDER_STEP = 0.1
VOTES_SLIDER_STEPS = (
    0,
    100,
    1_000,
    5_000,
    10_000,
    50_000,
    100_000,
    500_000,
    1_000_000,
    5_000_000,
)
VOTES_SLIDER_MAX_INDEX = len(VOTES_SLIDER_STEPS) - 1


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("candidateSearchFieldLabel")
    return label


def add_threshold_filter_row(
    form: QVBoxLayout,
    title: str,
    value_label: QLabel,
    slider: RangeSlider,
) -> None:
    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.addWidget(field_label(title))
    header.addStretch()
    header.addWidget(value_label)
    form.addLayout(header)
    form.addWidget(slider)


def make_min_threshold_slider(
    minimum: int,
    maximum: int,
    object_name: str,
    on_change: Callable[[], None],
) -> RangeSlider:
    slider = RangeSlider(minimum, maximum, minimum, maximum)
    slider.setObjectName(object_name)

    def _on_range_changed(lower: int, upper: int) -> None:
        if upper != maximum:
            slider.blockSignals(True)
            slider.setValues(lower, maximum)
            slider.blockSignals(False)
        on_change()

    slider.rangeChanged.connect(_on_range_changed)
    return slider


def format_min_score_label(tenths: int) -> str:
    if tenths <= 0:
        return "—"
    return f"{tenths * SCORE_SLIDER_STEP:.1f}+"


def score_tenths_from_slider(slider: RangeSlider) -> int:
    lower, _upper = slider.values()
    return max(0, int(lower))


def min_score_from_slider(slider: RangeSlider) -> float | None:
    tenths = score_tenths_from_slider(slider)
    if tenths <= 0:
        return None
    return round(tenths * SCORE_SLIDER_STEP, 1)


def set_score_slider_from_default(slider: RangeSlider, value) -> None:
    tenths = 0
    if value not in (None, ""):
        try:
            tenths = max(0, min(SCORE_SLIDER_MAX, int(round(float(value) / SCORE_SLIDER_STEP))))
        except (TypeError, ValueError):
            tenths = 0
    slider.blockSignals(True)
    slider.setValues(tenths, SCORE_SLIDER_MAX)
    slider.blockSignals(False)


def format_min_votes_label(step_index: int) -> str:
    if step_index <= 0:
        return "—"
    return f"{VOTES_SLIDER_STEPS[step_index]:,}".replace(",", " ") + "+"


def votes_index_from_slider(slider: RangeSlider) -> int:
    lower, _upper = slider.values()
    return max(0, min(VOTES_SLIDER_MAX_INDEX, int(lower)))


def min_votes_from_slider(slider: RangeSlider) -> int | None:
    index = votes_index_from_slider(slider)
    if index <= 0:
        return None
    return VOTES_SLIDER_STEPS[index]


def set_votes_slider_from_default(slider: RangeSlider, value) -> None:
    index = 0
    if value not in (None, ""):
        try:
            target = int(value)
        except (TypeError, ValueError):
            target = 0
        if target > 0:
            for step_index, step_value in enumerate(VOTES_SLIDER_STEPS):
                if step_value <= target:
                    index = step_index
    slider.blockSignals(True)
    slider.setValues(index, VOTES_SLIDER_MAX_INDEX)
    slider.blockSignals(False)


def update_score_range_label(slider: RangeSlider, value_label: QLabel) -> None:
    tenths = score_tenths_from_slider(slider)
    value_label.setText(format_min_score_label(tenths))


def update_votes_range_label(slider: RangeSlider, value_label: QLabel) -> None:
    index = votes_index_from_slider(slider)
    value_label.setText(format_min_votes_label(index))
