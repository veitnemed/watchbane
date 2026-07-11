"""DetailCard widget for watched, candidate and add-title flows."""

from __future__ import annotations

from typing import Any

from desktop.i18n import tr
from desktop.shared.detail import profiles as detail_profiles
from desktop.shared.detail.action_icons import make_detail_metadata_pixmap
from desktop.shared.detail.card_layout import build_detail_card_layout
from desktop.shared.detail.card_pills import clear_layout, fill_detail_chip_rows, make_meta_pill
from desktop.shared.detail.card_poster import DetailCardPosterMixin
from desktop.shared.detail.main_info import build_main_info_items, build_title_meta_text
from desktop.shared.detail.posters import resolve_local_poster_path
from desktop.shared.detail.presenters import (
    build_detail_info_pill_labels,
    build_final_score_star_item,
    build_meta_pill_items,
    build_user_score_badge_item,
)
from desktop.shared.detail.profiles import DetailCardLayoutProfile
from desktop.shared.detail.types import DetailEntry
from dataset.models.media_type import MEDIA_TYPE_TV, normalize_media_type

MAIN_INFO_COLLAPSED_ROW_COUNT = 4
MEDIA_THEME_OBJECT_NAMES = {
    "detailTitle",
    "detailTitleMeta",
    "detailScoreSummaryTopDivider",
    "detailScoreSummaryBottomDivider",
    "genrePill",
    "detailMainInfoIcon",
    "detailMainInfoRowDivider",
}
UNCONSTRAINED_MINIMUM_HEIGHT = 0


class DetailCard(DetailCardPosterMixin):
    """Detail card widget for selected watched, candidate and add-title entries."""

    def __init__(self, parent=None, profile: DetailCardLayoutProfile | None = None) -> None:
        self._profile = profile or detail_profiles.DETAIL_CARD_LAYOUT_PROFILE
        self._poster_source_pixmap = None
        self._local_poster_path: str | None = None
        self._mark_watched_handler = None
        self._hide_handler = None
        self._mark_watched_button = None
        self._hide_button = None
        self._detail_chip_labels: list[str] = []
        self._main_info_items: list[dict[str, Any]] = []
        self._main_info_expanded = False
        self._layout_handles = build_detail_card_layout(self, parent, self._profile)
        self._media_type_theme = MEDIA_TYPE_TV
        self._apply_media_theme_properties()

    @property
    def widget(self):
        return self._frame

    def add_main_info_footer(self, widget) -> None:
        """Place a screen-specific control block directly after main information."""
        layout = self._main_info_section.layout()
        if layout is not None:
            layout.addWidget(widget)

    def set_mark_watched_handler(self, handler) -> None:
        """Optional callback for candidate transfer to watched dataset."""
        self._mark_watched_handler = handler
        if self._mark_watched_button is not None:
            self._mark_watched_button.setEnabled(handler is not None)

    def set_hide_handler(self, handler) -> None:
        """Optional callback for hiding candidate rows."""
        self._hide_handler = handler
        if self._hide_button is not None:
            self._hide_button.setEnabled(handler is not None)

    def _on_mark_watched_clicked(self) -> None:
        if self._mark_watched_handler is not None:
            self._mark_watched_handler()

    def _on_hide_clicked(self) -> None:
        if self._hide_handler is not None:
            self._hide_handler()

    def _score_summary_should_show(self, has_tmdb_ring: bool, has_final_stars: bool) -> bool:
        if has_tmdb_ring or has_final_stars:
            return True
        return False

    def _info_column_content_width(self) -> int:
        width = self._info_column_widget.width()
        if width > 0:
            return width
        frame_width = self._frame.width()
        if frame_width <= 0:
            return 0
        return max(
            120,
            frame_width
            - self._profile.detail_poster_width
            - self._profile.detail_poster_right_gap
            - (2 * self._profile.detail_hero_card_padding),
        )

    def _schedule_detail_chip_reflow(self) -> None:
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._refresh_detail_chips)

    def _schedule_poster_column_height_sync(self) -> None:
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._sync_poster_column_minimum_height)

    def _sync_poster_column_minimum_height(self) -> None:
        overview_layout = self._overview_frame.layout()
        if self._overview_frame.isVisible() and overview_layout is not None:
            overview_width = self._overview_frame.width() or self._profile.detail_poster_width
            overview_height = overview_layout.heightForWidth(overview_width)
            if overview_height < 0:
                overview_height = overview_layout.sizeHint().height()
            self._overview_frame.setMinimumHeight(max(0, overview_height))
        else:
            self._overview_frame.setMinimumHeight(UNCONSTRAINED_MINIMUM_HEIGHT)

        layout = self._poster_column_widget.layout()
        if layout is None:
            return
        self._poster_column_widget.setMinimumHeight(UNCONSTRAINED_MINIMUM_HEIGHT)
        layout.invalidate()
        layout.activate()
        self._poster_column_widget.setMinimumHeight(
            max(self._profile.detail_poster_height, layout.sizeHint().height())
        )

    def _refresh_detail_chips(self) -> None:
        if len(self._detail_chip_labels) == 0:
            clear_layout(self._genre_pills_layout)
            self._genre_section.setVisible(False)
            self._genre_section.setFixedHeight(0)
            return

        fill_detail_chip_rows(
            self._genre_pills_layout,
            self._detail_chip_labels,
            self._info_column_content_width(),
            "genrePill",
            self._profile,
        )
        self._apply_media_theme_properties()
        row_count = min(self._profile.detail_chip_max_rows, self._genre_pills_layout.count())
        if row_count <= 0:
            self._genre_section.setVisible(False)
            self._genre_section.setFixedHeight(0)
            return

        height = (
            self._profile.detail_chip_height * row_count
            + self._profile.detail_chip_row_gap * max(0, row_count - 1)
        )
        self._genre_section.setFixedHeight(height)
        self._genre_section.setVisible(True)

    def show_empty(self, title: str | None = None) -> None:
        self._set_media_theme(MEDIA_TYPE_TV, show_media_badge=False)
        if title is None:
            title = tr("watched.empty.select_title")
        self._set_poster_placeholder()
        self._set_local_poster_path(None)
        self._title_label.setText(title)
        self._set_title_meta("")
        self._set_user_score_badge(None)
        self._set_score_summary_items([], None)
        self._detail_chip_labels = []
        self._refresh_detail_chips()
        self._overview_label.setText("")
        self._overview_frame.setVisible(False)
        self._overview_gap_widget.setVisible(False)
        self._main_info_expanded = False
        self._set_main_info_items([])
        if self._mark_watched_button is not None:
            self._mark_watched_button.setEnabled(self._mark_watched_handler is not None)
        if self._hide_button is not None:
            self._hide_button.setEnabled(self._hide_handler is not None)
        self._schedule_poster_height_sync()
        self._schedule_poster_column_height_sync()

    def show_entry(self, entry: DetailEntry) -> None:
        from desktop.shared.detail.presenters import get_overview_display, has_overview_text

        _, movie, card = entry
        self._set_media_theme(self._resolve_entry_media_type(movie, card), show_media_badge=True)
        self._title_label.setText(card.get("title") or entry[0])
        title_meta = build_title_meta_text(card)
        search_reasons = card.get("search_reasons") or []
        if search_reasons:
            reason_text = "\n".join(str(line) for line in search_reasons[:3] if line not in (None, ""))
            if reason_text:
                title_meta = f"{title_meta}\n{reason_text}" if title_meta else reason_text
        self._set_title_meta(title_meta)
        self._set_user_score_badge(build_user_score_badge_item(card))

        meta_pills = build_meta_pill_items(card)
        star_item = build_final_score_star_item(card)
        self._set_score_summary_items(meta_pills, star_item)
        if self._mark_watched_button is not None:
            self._mark_watched_button.setEnabled(self._mark_watched_handler is not None)
        if self._hide_button is not None:
            self._hide_button.setEnabled(self._hide_handler is not None)

        detail_pills = build_detail_info_pill_labels(card)
        self._detail_chip_labels = detail_pills
        self._refresh_detail_chips()

        self._main_info_expanded = False
        self._set_main_info_items(build_main_info_items(card))
        self._apply_media_theme_properties()

        if has_overview_text(card):
            self._overview_label.setText(get_overview_display(card))
            self._overview_gap_widget.setVisible(True)
            self._overview_frame.setVisible(True)
        else:
            self._overview_label.setText("")
            self._overview_gap_widget.setVisible(False)
            self._overview_frame.setVisible(False)

        poster_path = resolve_local_poster_path(movie, card)
        if poster_path is None or self._set_poster_image(poster_path) is False:
            self._set_poster_placeholder()
        self._set_local_poster_path(poster_path)
        self._schedule_poster_height_sync()
        self._schedule_poster_column_height_sync()

    def _resolve_entry_media_type(self, movie: dict, card: dict) -> str:
        media_candidates = [
            card.get("media_type"),
            card.get("object_type"),
        ]
        if isinstance(movie, dict):
            main_info = movie.get("main_info")
            if isinstance(main_info, dict):
                media_candidates.append(main_info.get("media_type"))
                media_candidates.append(main_info.get("object_type"))
            media_candidates.append(movie.get("media_type"))
            media_candidates.append(movie.get("object_type"))
        for value in media_candidates:
            if value not in (None, ""):
                return normalize_media_type(value)
        return MEDIA_TYPE_TV

    def _set_media_theme(self, media_type, *, show_media_badge: bool = True) -> None:
        self._media_type_theme = normalize_media_type(media_type)
        self._set_media_type_badge(show_media_badge)
        self._apply_media_theme_properties()

    def _set_media_type_badge(self, visible: bool) -> None:
        if self._media_type_theme == "movie":
            label = tr("media_type.movie")
        else:
            label = tr("media_type.tv")
        self._media_type_badge.setText(str(label).upper())
        self._media_type_badge.setVisible(visible)

    def _apply_media_theme_properties(self) -> None:
        from PyQt6.QtWidgets import QWidget

        widgets = [
            self._frame,
            self._poster_shell,
            self._user_score_badge,
            self._media_type_badge,
            self._main_info_panel,
            self._main_info_divider,
            self._overview_divider,
        ]
        widgets.extend(
            child
            for child in self._frame.findChildren(QWidget)
            if child.objectName() in MEDIA_THEME_OBJECT_NAMES
        )
        seen: set[int] = set()
        for widget in widgets:
            if widget is None or id(widget) in seen:
                continue
            seen.add(id(widget))
            if widget.property("mediaType") == self._media_type_theme:
                continue
            widget.setProperty("mediaType", self._media_type_theme)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def _set_title_meta(self, text: str) -> None:
        value = str(text or "").strip()
        self._title_meta_label.setText(value)
        self._title_meta_label.setVisible(value != "")

    def _set_score_summary_items(self, meta_pills: list[dict], star_item: dict | None) -> None:
        from PyQt6.QtCore import Qt

        clear_layout(self._tmdb_ring_layout)
        tmdb_ring_items = [item for item in meta_pills if item.get("source") == "tmdb"]
        has_tmdb_ring = len(tmdb_ring_items) > 0
        if has_tmdb_ring:
            self._tmdb_ring_layout.addStretch(1)
            self._tmdb_ring_layout.addWidget(
                make_meta_pill(tmdb_ring_items[0], self._profile),
                alignment=Qt.AlignmentFlag.AlignCenter,
            )
            self._tmdb_ring_layout.addStretch(1)
        self._tmdb_ring_slot.setVisible(has_tmdb_ring)

        has_final_stars = star_item is not None
        if has_final_stars:
            self._rating_stars_widget.set_stars(star_item.get("stars"), star_item.get("tooltip") or "")
        else:
            self._rating_stars_widget.set_stars(None)
        self._final_score_stars_block.setVisible(has_final_stars)
        self._final_score_stars_lane.setVisible(has_final_stars)
        self._score_summary_widget.setVisible(self._score_summary_should_show(has_tmdb_ring, has_final_stars))

    def _set_user_score_badge(self, badge: dict | None) -> None:
        if badge is None:
            self._user_score_badge.setText("")
            self._user_score_badge.hide()
            return
        self._user_score_badge.setText(str(badge.get("text", "")))
        self._resize_user_score_badge()
        self._user_score_badge.show()
        self._user_score_badge.raise_()

    def _resize_user_score_badge(self) -> None:
        badge_width = max(
            self._profile.detail_user_score_badge_min_width,
            self._user_score_badge.sizeHint().width(),
        )
        self._user_score_badge.setFixedSize(
            badge_width,
            self._profile.detail_user_score_badge_height,
        )

    def _main_info_icon_kind(self, label: str) -> str:
        label_to_icon = {
            tr("detail.info.type"): "type",
            tr("detail.info.country"): "country",
            tr("detail.info.premiere"): "date",
            tr("detail.info.last_episode"): "date",
            tr("detail.info.watch_where"): "watch",
            tr("detail.info.tmdb_votes"): "votes",
        }
        return label_to_icon.get(str(label), "info")

    def _set_info_grid_items(
        self,
        grid,
        section,
        items: list[dict[str, Any]],
        *,
        label_object_name: str,
        value_object_name: str,
    ) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
        from desktop.theme import FILM_TEXT_MUTED, TRANSPARENT_STYLE

        clear_layout(grid)
        compact_row_height = min(
            self._profile.detail_main_info_row_height,
            self._profile.detail_main_info_compact_row_height,
        )
        stacked_info_rows = (
            detail_profiles.use_stacked_detail_info_rows()
            and self._profile.include_bottom_stretch
        )
        icon_size = max(16, min(22, compact_row_height // 2))
        for row, item in enumerate(items):
            row_widget = QWidget()
            row_widget.setObjectName("detailMainInfoRow")
            row_widget.setStyleSheet(TRANSPARENT_STYLE)
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)

            content_widget = QWidget()
            content_widget.setStyleSheet(TRANSPARENT_STYLE)
            content_layout_class = QGridLayout if stacked_info_rows else QHBoxLayout
            content_layout = content_layout_class(content_widget)
            content_layout.setContentsMargins(0, 0, 0, 0)
            if stacked_info_rows:
                content_layout.setHorizontalSpacing(self._profile.detail_small_spacing)
                content_layout.setVerticalSpacing(max(1, self._profile.detail_small_spacing // 3))
                content_layout.setColumnStretch(0, 0)
                content_layout.setColumnStretch(1, 1)
            else:
                content_layout.setSpacing(self._profile.detail_small_spacing)

            icon = QLabel()
            icon.setObjectName("detailMainInfoIcon")
            icon.setFixedSize(icon_size + self._profile.detail_small_spacing, compact_row_height)
            icon.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            icon.setPixmap(
                make_detail_metadata_pixmap(
                    self._main_info_icon_kind(str(item.get("label", ""))),
                    FILM_TEXT_MUTED,
                    icon_size,
                )
            )

            label = QLabel(str(item.get("label", "")))
            label.setObjectName(label_object_name)
            if stacked_info_rows:
                label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            else:
                label.setFixedWidth(self._profile.detail_main_info_label_width)
            label.setFixedHeight(compact_row_height)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            value_text = str(item.get("value", ""))
            value = QLabel(value_text)
            value.setObjectName(value_object_name)
            value.setWordWrap(False)
            value.setFixedHeight(compact_row_height)
            if stacked_info_rows:
                value_max_width = self._profile.detail_info_column_max_width
            else:
                value_max_width = max(
                    80,
                    self._profile.detail_info_column_max_width
                    - self._profile.detail_main_info_label_width
                    - icon.width()
                    - (2 * self._profile.detail_main_info_panel_padding_x)
                    - (2 * self._profile.detail_small_spacing),
                )
            value.setMaximumWidth(value_max_width)
            value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            value.setToolTip(str(item.get("tooltip") or value_text))

            if stacked_info_rows:
                icon.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                content_layout.addWidget(icon, 0, 0, 2, 1)
                content_layout.addWidget(label, 0, 1)
                content_layout.addWidget(value, 1, 1)
            else:
                content_layout.addWidget(icon)
                content_layout.addWidget(label)
                content_layout.addWidget(value, stretch=1)
            row_layout.addWidget(content_widget)

            if row < len(items) - 1:
                divider = QFrame()
                divider.setObjectName("detailMainInfoRowDivider")
                divider.setFrameShape(QFrame.Shape.HLine)
                divider.setFixedHeight(self._profile.detail_divider_height)
                divider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                row_layout.addWidget(divider)

            grid.addWidget(row_widget, row, 0, 1, 2)

        section.setVisible(len(items) > 0)

    def _set_main_info_items(self, items: list[dict[str, Any]]) -> None:
        self._main_info_items = list(items)
        self._render_main_info_items()

    def _visible_main_info_items(self) -> list[dict[str, Any]]:
        if self._main_info_expanded:
            return list(self._main_info_items)
        return list(self._main_info_items[:MAIN_INFO_COLLAPSED_ROW_COUNT])

    def _toggle_main_info_expanded(self) -> None:
        self._main_info_expanded = not self._main_info_expanded
        self._render_main_info_items()

    def _update_main_info_toggle_button(self) -> None:
        has_hidden_rows = len(self._main_info_items) > MAIN_INFO_COLLAPSED_ROW_COUNT
        self._main_info_toggle_button.setVisible(has_hidden_rows)
        if has_hidden_rows:
            self._main_info_toggle_button.setText(
                tr("detail.show_less") if self._main_info_expanded else tr("detail.show_more")
            )

    def _render_main_info_items(self) -> None:
        if len(self._main_info_items) <= MAIN_INFO_COLLAPSED_ROW_COUNT:
            self._main_info_expanded = False
        visible_items = self._visible_main_info_items()
        self._set_info_grid_items(
            self._main_info_grid,
            self._main_info_section,
            visible_items,
            label_object_name="detailMainInfoLabel",
            value_object_name="detailMainInfoValue",
        )
        self._update_main_info_toggle_button()


# WatchedDetailCard is kept for backward compatibility.
WatchedDetailCard = DetailCard
