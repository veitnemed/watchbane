"""Pill row helpers for WatchedDetailCard."""

from __future__ import annotations

from desktop.shared.detail.profiles import DETAIL_CARD_LAYOUT_PROFILE, GENRES_PER_ROW, DetailCardLayoutProfile
from desktop.shared.detail.rating_indicator import RatingCircleIndicator
from desktop.theme import COLOR_ACCENT


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        if child_layout is not None:
            clear_layout(child_layout)
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def make_pill_label(text: str, object_name: str, rich: bool = False):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel

    pill = QLabel()
    pill.setObjectName(object_name)
    if rich:
        pill.setTextFormat(Qt.TextFormat.RichText)
    pill.setText(text)
    return pill


def make_meta_pill(item: dict, profile: DetailCardLayoutProfile = DETAIL_CARD_LAYOUT_PROFILE):
    return RatingCircleIndicator(
        item.get("display_label") or item.get("label", ""),
        item.get("score"),
        item.get("accent", COLOR_ACCENT),
        display_value=item.get("display_value"),
        display_label=item.get("display_label") or item.get("label", ""),
        ring_progress=item.get("ring_progress"),
        footer_label=item.get("footer_label"),
        widget_size=profile.rating_widget_size,
        circle_diameter=profile.rating_circle_diameter,
        value_font_point=profile.rating_value_font_point,
        label_font_point=profile.rating_label_font_point,
    )


def fill_meta_pill_row(
    layout,
    items: list[dict],
    profile: DetailCardLayoutProfile = DETAIL_CARD_LAYOUT_PROFILE,
) -> None:
    clear_layout(layout)
    layout.setSpacing(8)
    for item in items:
        layout.addWidget(make_meta_pill(item, profile))
    layout.addStretch()


def fill_pill_rows(container_layout, labels: list[str], object_name: str) -> None:
    clear_layout(container_layout)
    container_layout.setSpacing(8)
    if len(labels) == 0:
        return
    from PyQt6.QtWidgets import QHBoxLayout

    for index in range(0, len(labels), GENRES_PER_ROW):
        row = QHBoxLayout()
        row.setSpacing(8)
        for text in labels[index : index + GENRES_PER_ROW]:
            row.addWidget(make_pill_label(text, object_name))
        row.addStretch()
        container_layout.addLayout(row)
