"""Contracts for views registered as main-window shell tabs."""

from __future__ import annotations

from typing import Protocol

from PyQt6.QtWidgets import QWidget


class TabView(Protocol):
    """Minimal interface required by MainTabRegistry."""

    @property
    def widget(self) -> QWidget:
        """Root widget registered in QTabWidget."""
        ...


def activate_tab_view(view: TabView) -> None:
    """Run optional lazy activation hook for a tab view."""
    activated = getattr(view, "on_tab_activated", None)
    if callable(activated):
        activated()
