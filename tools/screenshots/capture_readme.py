"""Capture a release README screenshot from an isolated Watchbane runtime."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _process_events(app, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--tab", choices=("candidates", "watched", "filters"), required=True)
    parser.add_argument(
        "--candidates-state",
        choices=("ready", "preparing"),
        default="ready",
        help="Force the Recommendations capture surface without changing runtime data.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=960)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--interface-language", choices=("ru", "en"), default="en")
    parser.add_argument("--watched-title", default="Breaking Bad")
    args = parser.parse_args(argv)

    os.environ["WATCHBANE_DATA_DIR"] = str(args.runtime_root.resolve())
    os.environ["WATCHBANE_INTERFACE_LANGUAGE"] = args.interface_language
    os.environ["WATCHBANE_DATA_LANGUAGE"] = "en"
    os.environ["WATCHBANE_UI_SCALE"] = str(args.scale)
    os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont, QFontDatabase
    from PyQt6.QtWidgets import QApplication, QListView, QListWidget, QScrollArea, QStackedWidget, QWidget

    from desktop.shell.main_window import WatchedMoviesWindow
    from desktop.theme import FONT_APP, FONT_FAMILY, font_px
    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(args.scale)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, font_px(FONT_APP)))
    window = WatchedMoviesWindow(initial_size=(args.width, args.height))
    window.show()
    window.raise_()
    window.activateWindow()
    window._tab_registry.focus(args.tab)
    _process_events(app, 4.0 if args.tab == "candidates" else 1.2)

    if args.tab == "watched":
        watched = window.findChild(QListWidget, "watchedList")
        if watched is not None and watched.count() > 0:
            target_row = 0
            for row in range(watched.count()):
                item = watched.item(row)
                entry = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
                card = entry[2] if isinstance(entry, tuple) and len(entry) == 3 else {}
                if str(card.get("title") or "").casefold() == args.watched_title.casefold():
                    target_row = row
                    break
            watched.setCurrentRow(target_row)
            _process_events(app, 0.8)
    elif args.tab == "candidates":
        if args.candidates_state == "preparing":
            stack = window.findChild(QStackedWidget, "recommendationsDeckStack")
            loading_page = window.findChild(QWidget, "recommendationsDeckLoadingPage")
            if stack is not None and loading_page is not None:
                stack.setCurrentWidget(loading_page)
                _process_events(app, 0.4)
        else:
            candidates = window.findChild(QListView, "candidateListWidget")
            if candidates is not None and candidates.model() is not None and candidates.model().rowCount() > 0:
                candidates.setCurrentIndex(candidates.model().index(0, 0))
                _process_events(app, 1.0)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    saved = window.grab().save(str(args.output))
    families = set(QFontDatabase.families())
    horizontal_scroll = [
        (area.objectName(), area.horizontalScrollBar().maximum())
        for area in window.findChildren(QScrollArea)
        if area.isVisible() and area.horizontalScrollBar().maximum() > 0
    ]
    print(f"platform={app.platformName()}")
    print(f"font_probe={{'family_count': {len(families)}, 'has_segoe_ui': {'Segoe UI' in families}}}")
    print(
        f"tab={args.tab} scale={args.scale} window={window.width()}x{window.height()} "
        f"horizontal_scroll={horizontal_scroll}"
    )
    print(f"saved={saved} path={args.output}")
    window.close()
    _process_events(app, 0.2)
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
