"""PyQt6 desktop viewer for watched movies and series."""

from desktop.shell.bootstrap import main

__all__ = ["main"]


def __getattr__(name: str):
    if name == "WatchedMoviesWindow":
        from desktop.shell.main_window import WatchedMoviesWindow

        return WatchedMoviesWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    main()
