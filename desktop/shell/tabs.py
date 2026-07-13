"""Main window tab registry, factory and activation dispatch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QTabWidget, QWidget

from desktop.candidates.filters_view import CandidateFiltersView
from desktop.candidates.list_view import CandidateListView
from desktop.candidates.session import CandidateSearchSession
from desktop.language_context import DesktopLanguageContext, load_desktop_language_context
from desktop.shell.tab_contract import TabView, activate_tab_view
from desktop.settings.tab_view import SettingsTabView
from desktop.shared.brand_assets import watchbane_symbol_label
from desktop.theme.scaling import control_px, layout_px
from desktop.theme.tokens import SPACING_SMALL
from desktop.watched.tab import WatchedTabView


@dataclass(frozen=True)
class ShellTabSpec:
    """One registered main-window tab."""

    tab_id: str
    label: str
    view: TabView


@dataclass
class AppTabsContext:
    """Feature views and shared session for cross-tab callbacks."""

    watched_tab_view: WatchedTabView
    candidate_list_view: CandidateListView
    settings_tab_view: SettingsTabView
    candidate_session: CandidateSearchSession
    refresh_candidate_filters: Callable[[], None]
    focus_candidates: Callable[[], None]


class MainTabRegistry:
    """Register feature views with QTabWidget and dispatch on_tab_activated."""

    def __init__(self, tabs_widget: QTabWidget) -> None:
        self._tabs = tabs_widget
        self._specs: dict[str, ShellTabSpec] = {}
        self._widget_to_id: dict[QWidget, str] = {}
        self._tabs.currentChanged.connect(self.on_current_changed)

    def register(self, spec: ShellTabSpec) -> None:
        self._tabs.addTab(spec.view.widget, spec.label)
        self._specs[spec.tab_id] = spec
        self._widget_to_id[spec.view.widget] = spec.tab_id

    def focus(self, tab_id: str) -> None:
        spec = self._specs[tab_id]
        if self._tabs.currentWidget() is spec.view.widget:
            activate_tab_view(spec.view)
            return
        self._tabs.setCurrentWidget(spec.view.widget)

    def on_current_changed(self, index: int) -> None:
        if index < 0:
            return
        widget = self._tabs.widget(index)
        if widget is None:
            return
        tab_id = self._widget_to_id.get(widget)
        if tab_id is None:
            return
        view = self._specs[tab_id].view
        activate_tab_view(view)


def build_main_tabs(
    tabs: QTabWidget,
    parent: QWidget,
    *,
    on_status_message: Callable[[str, int], None],
    language_context: DesktopLanguageContext | None = None,
) -> tuple[MainTabRegistry, AppTabsContext]:
    """Create main-window tabs, register them and wire cross-tab callbacks."""
    registry = MainTabRegistry(tabs)
    languages = language_context or load_desktop_language_context()

    brand = QWidget()
    brand.setObjectName("watchbaneShellBrand")
    brand_layout = QHBoxLayout(brand)
    brand_layout.setContentsMargins(
        layout_px(6),
        layout_px(SPACING_SMALL),
        layout_px(7),
        layout_px(SPACING_SMALL),
    )
    brand_layout.setSpacing(0)
    symbol = watchbane_symbol_label(control_px(27))
    symbol.setToolTip("Watchbane")
    brand_layout.addWidget(symbol, alignment=Qt.AlignmentFlag.AlignVCenter)
    tabs.setCornerWidget(brand, Qt.Corner.TopLeftCorner)

    candidate_session = CandidateSearchSession()

    def on_candidate_moved_to_watched(result) -> None:
        added_key = getattr(result, "title", None)
        watched_tab_view.reload_entries(added_key=added_key)
        message = getattr(result, "message", None) or languages.tr("candidates.transfer.moved_to_watched")
        on_status_message(message, 5000)

    candidate_filters_view = CandidateFiltersView(
        candidate_session,
        on_applied=lambda: registry.focus("candidates"),
    )
    candidate_list_view = CandidateListView(
        candidate_session,
        on_watched_added=on_candidate_moved_to_watched,
        on_refill_needed=getattr(
            candidate_filters_view,
            "request_recommendation_refill",
            None,
        ),
    )

    def on_watched_entries_changed(_entries) -> None:
        candidate_session.reload_from_pool(force=True)
        candidate_list_view.refresh()
        candidate_filters_view.reload_filter_options()

    watched_tab_view = WatchedTabView(
        parent=parent,
        on_status_message=on_status_message,
        on_entries_changed=on_watched_entries_changed,
    )
    set_replenish_state_listener = getattr(
        candidate_filters_view,
        "set_replenish_state_listener",
        None,
    )
    if callable(set_replenish_state_listener):
        set_replenish_state_listener(candidate_list_view.on_replenish_state_changed)
    registry.register(ShellTabSpec("candidates", languages.tr("tabs.candidates"), candidate_list_view))
    registry.register(ShellTabSpec("watched", languages.tr("tabs.watched"), watched_tab_view))
    registry.register(ShellTabSpec("filters", languages.tr("tabs.filters"), candidate_filters_view))

    refresh_candidate_filters = getattr(candidate_filters_view, "reload_filter_options", lambda: None)

    def on_pool_changed() -> None:
        candidate_session.reload_from_pool(force=True)
        refresh_candidate_filters()

    settings_tab_view = SettingsTabView(
        parent=parent,
        on_status_message=on_status_message,
        on_pool_changed=on_pool_changed,
    )
    registry.register(ShellTabSpec("settings", languages.tr("tabs.settings"), settings_tab_view))

    def activate_initial_tab() -> None:
        try:
            current_index = tabs.currentIndex()
        except RuntimeError:
            return
        registry.on_current_changed(current_index)

    QTimer.singleShot(0, activate_initial_tab)

    context = AppTabsContext(
        watched_tab_view=watched_tab_view,
        candidate_list_view=candidate_list_view,
        settings_tab_view=settings_tab_view,
        candidate_session=candidate_session,
        refresh_candidate_filters=refresh_candidate_filters,
        focus_candidates=lambda: registry.focus("candidates"),
    )
    return registry, context
