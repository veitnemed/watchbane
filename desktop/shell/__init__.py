"""Desktop shell: bootstrap and main window."""

from desktop.shell.bootstrap import main
from desktop.shell.tab_contract import TabView, activate_tab_view
from desktop.shell.tabs import MainTabRegistry, ShellTabSpec

__all__ = [
    "MainTabRegistry",
    "ShellTabSpec",
    "TabView",
    "WatchedMoviesWindow",
    "activate_tab_view",
    "main",
]


def __getattr__(name: str):
    if name == "WatchedMoviesWindow":
        from desktop.shell.main_window import WatchedMoviesWindow

        return WatchedMoviesWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
