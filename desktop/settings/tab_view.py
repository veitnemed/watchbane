"""Desktop Settings tab."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from desktop.i18n import tr
from desktop.settings.pool_ops_panel import PoolOpsPanel
from desktop.settings.ui_scale_control import UiScaleControlPanel
from desktop.theme.scaling import layout_px
from desktop.theme.shell_layout import (
    LEFT_PANEL_TOP_COMPENSATION_PX,
    WATCHED_TAB_MARGIN_PX,
    WATCHED_TAB_SPACING_PX,
)

StatusCallback = Callable[[str, int], None]
PoolChangedCallback = Callable[[], None]


class SettingsTabView:
    """Settings tab: interface preferences such as UI scale."""

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        on_status_message: StatusCallback | None = None,
        on_pool_changed: PoolChangedCallback | None = None,
    ) -> None:
        self._on_status_message = on_status_message
        self._on_pool_changed = on_pool_changed

        scroll = QScrollArea(parent)
        scroll.setObjectName("settingsTabScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("settingsTabRoot")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            WATCHED_TAB_MARGIN_PX,
            WATCHED_TAB_MARGIN_PX + LEFT_PANEL_TOP_COMPENSATION_PX,
            WATCHED_TAB_MARGIN_PX,
            WATCHED_TAB_MARGIN_PX,
        )
        layout.setSpacing(WATCHED_TAB_SPACING_PX)

        title = QLabel(tr("settings.title"))
        title.setObjectName("settingsTabTitle")
        layout.addWidget(title)

        self._scale_panel = UiScaleControlPanel(content)
        self._scale_panel.settingsSaved.connect(self._on_settings_saved)
        layout.addWidget(self._scale_panel)

        self._pool_ops_panel = PoolOpsPanel(
            content,
            on_status_message=on_status_message,
        )
        self._pool_ops_panel.poolChanged.connect(self._on_pool_changed_signal)
        layout.addWidget(self._pool_ops_panel)
        layout.addStretch(1)

        scroll.setWidget(content)
        self._widget = scroll

    @property
    def widget(self) -> QWidget:
        return self._widget

    def on_tab_activated(self) -> None:
        self._scale_panel.load_from_settings()
        self._pool_ops_panel.refresh_stats()

    def _on_pool_changed_signal(self) -> None:
        if self._on_pool_changed is not None:
            self._on_pool_changed()

    def _on_settings_saved(self, message: str) -> None:
        if self._on_status_message is not None:
            self._on_status_message(message, 8000)
