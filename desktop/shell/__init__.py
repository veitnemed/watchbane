"""Desktop shell public API with scale-safe lazy imports."""

__all__ = [
    "MainTabRegistry",
    "ShellTabSpec",
    "TabView",
    "WatchedMoviesWindow",
    "activate_tab_view",
    "main",
]


def __getattr__(name: str):
    if name == "main":
        from desktop.shell.bootstrap import main

        return main
    if name in {"MainTabRegistry", "ShellTabSpec"}:
        from desktop.shell.tabs import MainTabRegistry, ShellTabSpec

        return {"MainTabRegistry": MainTabRegistry, "ShellTabSpec": ShellTabSpec}[name]
    if name in {"TabView", "activate_tab_view"}:
        from desktop.shell.tab_contract import TabView, activate_tab_view

        return {"TabView": TabView, "activate_tab_view": activate_tab_view}[name]
    if name == "WatchedMoviesWindow":
        from desktop.shell.main_window import WatchedMoviesWindow

        return WatchedMoviesWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
