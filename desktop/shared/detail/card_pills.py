"""Pill row helpers for WatchedDetailCard."""

from __future__ import annotations

from desktop.shared.detail import profiles as detail_profiles
from desktop.shared.detail.profiles import GENRES_PER_ROW, DetailCardLayoutProfile
from desktop.shared.detail.rating_indicator import RatingCircleIndicator
from desktop.theme import COLOR_ACCENT, font_px, layout_px, px
from desktop.theme.tokens import (
    DETAIL_RATING_RING_LABEL_FONT_MIN,
    DETAIL_RATING_RING_VALUE_FONT_MIN,
)

CHIP_WIDTH_SAFETY = px(18)
CHIP_ELIDE_PADDING = px(8)


def _resolve_profile(profile: DetailCardLayoutProfile | None) -> DetailCardLayoutProfile:
    return profile or detail_profiles.DETAIL_CARD_LAYOUT_PROFILE


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
    pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if rich:
        pill.setTextFormat(Qt.TextFormat.RichText)
    pill.setText(text)
    return pill


def _chip_display_text(text: str, max_text_width: int, font_metrics) -> str:
    from PyQt6.QtCore import Qt

    if font_metrics.horizontalAdvance(text) <= max_text_width:
        return text
    return font_metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(1, max_text_width))


def _chip_width(text: str, available_width: int, profile: DetailCardLayoutProfile, font_metrics) -> int:
    max_width = max(1, min(profile.detail_chip_max_width, available_width))
    natural_width = (
        font_metrics.horizontalAdvance(text)
        + (2 * profile.detail_chip_h_padding)
        + CHIP_WIDTH_SAFETY
    )
    return max(1, min(max_width, natural_width))


def _append_chip_to_rows(
    rows: list[list[str]],
    row_widths: list[int],
    label: str,
    available_width: int,
    profile: DetailCardLayoutProfile,
    font_metrics,
) -> bool:
    width = _chip_width(label, available_width, profile, font_metrics)
    row_index = len(rows) - 1
    current_width = row_widths[row_index]
    gap = profile.detail_chip_col_gap if rows[row_index] else 0
    if current_width + gap + width <= available_width:
        rows[row_index].append(label)
        row_widths[row_index] = current_width + gap + width
        return True
    if len(rows) >= profile.detail_chip_max_rows:
        return False
    rows.append([label])
    row_widths.append(width)
    return True


def build_detail_chip_rows(
    labels: list[str],
    available_width: int,
    profile: DetailCardLayoutProfile | None = None,
    font_metrics=None,
) -> list[list[str]]:
    """Build width-aware detail chips with a strict max row count."""
    profile = _resolve_profile(profile)
    clean_labels = [str(label).strip() for label in labels if str(label).strip()]
    if not clean_labels:
        return []
    if font_metrics is None:
        from PyQt6.QtGui import QFont, QFontMetrics
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return [clean_labels[: profile.detail_chip_max_rows]]
        font = QFont(app.font())
        font.setPointSize(profile.detail_chip_font_size)
        font_metrics = QFontMetrics(font)

    safe_width = max(1, int(available_width))
    rows: list[list[str]] = [[]]
    row_widths: list[int] = [0]
    overflow_start: int | None = None

    for index, label in enumerate(clean_labels):
        if _append_chip_to_rows(rows, row_widths, label, safe_width, profile, font_metrics):
            continue
        overflow_start = index
        break

    rows = [row for row in rows if row]
    if overflow_start is None:
        return rows[: profile.detail_chip_max_rows]

    overflow_count = len(clean_labels) - overflow_start
    if not rows:
        return [[f"+{overflow_count}"]]

    while rows:
        removed_label = rows[-1].pop()
        overflow_count += 1
        if not rows[-1]:
            rows.pop()
            if not rows:
                return [[f"+{overflow_count}"]]
        test_rows = [row[:] for row in rows]
        test_widths = [
            sum(_chip_width(item, safe_width, profile, font_metrics) for item in row)
            + max(0, len(row) - 1) * profile.detail_chip_col_gap
            for row in test_rows
        ]
        overflow_label = f"+{overflow_count}"
        if _append_chip_to_rows(test_rows, test_widths, overflow_label, safe_width, profile, font_metrics):
            return test_rows[: profile.detail_chip_max_rows]
        overflow_count += 0
        if removed_label == overflow_label:
            break

    return [[f"+{len(clean_labels)}"]]


def make_meta_pill(item: dict, profile: DetailCardLayoutProfile | None = None):
    profile = _resolve_profile(profile)
    widget = RatingCircleIndicator(
        item.get("display_label") or item.get("label", ""),
        item.get("score"),
        item.get("accent", COLOR_ACCENT),
        display_value=item.get("display_value"),
        display_label=item.get("display_label") or item.get("label", ""),
        ring_progress=item.get("ring_progress"),
        widget_size=profile.detail_rating_widget_size,
        circle_diameter=profile.detail_rating_circle_diameter,
        value_font_point=max(
            profile.rating_value_font_point,
            font_px(DETAIL_RATING_RING_VALUE_FONT_MIN),
        ),
        label_font_point=max(
            profile.rating_label_font_point,
            font_px(DETAIL_RATING_RING_LABEL_FONT_MIN),
        ),
    )
    widget.setObjectName("detailTmdbScoreRing" if item.get("source") == "tmdb" else "detailScoreRing")
    return widget


def fill_meta_pill_row(
    layout,
    items: list[dict],
    profile: DetailCardLayoutProfile | None = None,
) -> None:
    profile = _resolve_profile(profile)
    clear_layout(layout)
    layout.setSpacing(layout_px(1))
    for item in items:
        layout.addWidget(make_meta_pill(item, profile))
    layout.addStretch()


def fill_pill_rows(container_layout, labels: list[str], object_name: str) -> None:
    clear_layout(container_layout)
    container_layout.setSpacing(layout_px(8))
    if len(labels) == 0:
        return
    from PyQt6.QtWidgets import QHBoxLayout

    for index in range(0, len(labels), GENRES_PER_ROW):
        row = QHBoxLayout()
        row.setSpacing(layout_px(8))
        for text in labels[index : index + GENRES_PER_ROW]:
            row.addWidget(make_pill_label(text, object_name))
        row.addStretch()
        container_layout.addLayout(row)


def fill_detail_chip_rows(
    container_layout,
    labels: list[str],
    available_width: int,
    object_name: str,
    profile: DetailCardLayoutProfile | None = None,
) -> None:
    profile = _resolve_profile(profile)
    clear_layout(container_layout)
    container_layout.setSpacing(profile.detail_chip_row_gap)
    if len(labels) == 0:
        return

    from PyQt6.QtGui import QFont, QFontMetrics
    from PyQt6.QtWidgets import QApplication, QHBoxLayout

    app = QApplication.instance()
    if app is not None:
        font = QFont(app.font())
        font.setPointSize(profile.detail_chip_font_size)
        font_metrics = QFontMetrics(font)
    else:
        font_metrics = None
    rows = build_detail_chip_rows(labels, available_width, profile, font_metrics)
    row_count = len(rows)
    if row_count == 0:
        return

    for row_labels in rows:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(profile.detail_chip_col_gap)
        for text in row_labels:
            chip_width = _chip_width(text, max(1, int(available_width)), profile, font_metrics)
            max_text_width = max(1, chip_width - (2 * CHIP_ELIDE_PADDING))
            display_text = (
                _chip_display_text(text, max_text_width, font_metrics)
                if not text.startswith("+")
                else text
            )
            chip = make_pill_label(display_text, object_name)
            if app is not None:
                chip.setFont(font)
            chip.setToolTip(text if display_text != text else "")
            chip.setFixedHeight(profile.detail_chip_height)
            chip.setMaximumWidth(profile.detail_chip_max_width)
            chip.setFixedWidth(chip_width)
            row.addWidget(chip)
        row.addStretch(1)
        container_layout.addLayout(row)
