"""Reusable loading and empty-state presentation for Recommendations."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QRegion
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from desktop.candidates.filter_icon_assets import filter_icon_pixmap
from desktop.i18n import tr
from desktop.theme.scaling import layout_px, list_px
from desktop.theme.tokens import FILM_ACCENT

UNCONSTRAINED_MINIMUM_HEIGHT = 0


@dataclass(frozen=True)
class _EmptyStateSpec:
    title_key: str
    subtitle_key: str
    icon: str


_STATE_SPECS = {
    "loading": _EmptyStateSpec(
        "recommendations.empty_state.loading.title",
        "recommendations.empty_state.loading.subtitle",
        "clock",
    ),
    "pool_empty": _EmptyStateSpec(
        "recommendations.empty_state.pool_empty.title",
        "recommendations.empty_state.pool_empty.subtitle",
        "replenish",
    ),
    "no_results": _EmptyStateSpec(
        "recommendations.empty_state.no_results.title",
        "recommendations.empty_state.no_results.subtitle",
        "search",
    ),
    "error": _EmptyStateSpec(
        "recommendations.empty_state.error.title",
        "recommendations.empty_state.error.subtitle",
        "refresh",
    ),
    "idle": _EmptyStateSpec(
        "recommendations.empty_state.idle.title",
        "recommendations.empty_state.idle.subtitle",
        "media",
    ),
}


class RecommendationEmptyState(QWidget):
    """Centered icon/title/subtitle block with an optional accessory widget."""

    def __init__(
        self,
        state: str = "idle",
        *,
        title: str | None = None,
        subtitle: str | None = None,
        icon: str | None = None,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("recommendationEmptyState")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._state = ""
        self._compact = False
        self._icon_name = "media"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addStretch(1)

        self._content = QWidget()
        self._content.setObjectName("recommendationEmptyStateContent")
        # The state is used in both the full detail pane and compact list pane.
        # A scaled fixed minimum can force its copy across a splitter boundary
        # at the 1.25 QA anchor; allow the layout to wrap it within its pane.
        self._content.setMinimumWidth(UNCONSTRAINED_MINIMUM_HEIGHT)
        self._content.setMaximumWidth(layout_px(680))
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._icon_shell = QFrame()
        self._icon_shell.setObjectName("recommendationEmptyStateIconShell")
        icon_layout = QVBoxLayout(self._icon_shell)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self._icon_label = QLabel()
        self._icon_label.setObjectName("recommendationEmptyStateIcon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(self._icon_label)
        self._content_layout.addWidget(
            self._icon_shell,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self.title_label = QLabel()
        self.title_label.setObjectName("candidateSearchDetailPlaceholder")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._content_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("recommendationEmptyStateSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._content_layout.addWidget(self.subtitle_label)

        self._accessory = QWidget()
        self._accessory.setObjectName("recommendationEmptyStateAccessory")
        self._accessory_layout = QVBoxLayout(self._accessory)
        self._accessory_layout.setContentsMargins(0, 0, 0, 0)
        self._accessory_layout.setSpacing(layout_px(8))
        self._content_layout.addWidget(self._accessory)
        self._accessory.hide()

        root.addWidget(self._content, alignment=Qt.AlignmentFlag.AlignHCenter)
        root.addStretch(1)

        self.set_compact(compact)
        self.set_state(state, title=title, subtitle=subtitle, icon=icon)

    @property
    def state(self) -> str:
        return self._state

    def add_accessory(self, widget: QWidget) -> None:
        """Place an existing progress/action widget below the explanatory copy."""
        self._accessory_layout.addWidget(widget)
        self._accessory.show()

    def set_state(
        self,
        state: str,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Update semantic state and optionally override its presentation copy."""
        try:
            spec = _STATE_SPECS[state]
        except KeyError as error:
            raise ValueError(f"Unsupported recommendation empty state: {state}") from error
        self._state = state
        self.setProperty("state", state)
        self.title_label.setText(title if title is not None else tr(spec.title_key))
        self.subtitle_label.setText(subtitle if subtitle is not None else tr(spec.subtitle_key))
        self.title_label.setMinimumHeight(UNCONSTRAINED_MINIMUM_HEIGHT)
        self.subtitle_label.setMinimumHeight(UNCONSTRAINED_MINIMUM_HEIGHT)
        self._set_icon(icon or spec.icon)
        self._content_layout.invalidate()
        self._content.updateGeometry()
        self.updateGeometry()
        QTimer.singleShot(0, self._sync_wrapped_label_heights)

    def set_compact(self, compact: bool) -> None:
        """Use reduced spacing for the one-column fallback surface."""
        self._compact = bool(compact)
        self.setProperty("compact", "true" if self._compact else "false")
        margin = layout_px(12 if self._compact else 24)
        spacing = layout_px(9 if self._compact else 14)
        self._content_layout.setContentsMargins(margin, margin, margin, margin)
        self._content_layout.setSpacing(spacing)
        icon_size = list_px(54 if self._compact else 72)
        self._icon_shell.setFixedSize(icon_size, icon_size)
        self._icon_shell.setMask(
            QRegion(self._icon_shell.rect(), QRegion.RegionType.Ellipse)
        )
        self._icon_shell.setProperty("compactIcon", "true" if self._compact else "false")
        self._set_icon(self._icon_name)
        for widget in (self, self._icon_shell, self.title_label, self.subtitle_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _set_icon(self, icon: str) -> None:
        self._icon_name = icon
        shell_size = max(1, self._icon_shell.width())
        glyph_size = max(1, int(round(shell_size * 0.62)))
        self._icon_label.setPixmap(filter_icon_pixmap(icon, glyph_size, FILM_ACCENT))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._sync_wrapped_label_heights()

    def _sync_wrapped_label_heights(self) -> None:
        margins = self._content_layout.contentsMargins()
        available_width = max(
            1,
            self._content.width() - margins.left() - margins.right(),
        )
        for label in (self.title_label, self.subtitle_label):
            height = label.heightForWidth(available_width)
            label.setMinimumHeight(max(0, height))
