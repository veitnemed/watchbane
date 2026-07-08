"""Capture a native screenshot of the watched detail film card.

Example:
    py scripts/capture_film_card.py --scale 1.0 --output screens/tmp_ui/film_card/movie.png
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=1.0, help="Application UI scale.")
    parser.add_argument("--media-type", choices=("movie", "tv"), default="movie")
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("screens/tmp_ui/film_card/movie_scale100.png"),
    )
    parser.add_argument(
        "--scroll-detail-right",
        action="store_true",
        help="Scroll the detail viewport horizontally to the right before grabbing.",
    )
    return parser


def _process_events(app, rounds: int, delay: float = 0.03) -> None:
    for _ in range(rounds):
        app.processEvents()
        time.sleep(delay)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "windows" if os.name == "nt" else "offscreen"

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication, QListWidget, QScrollArea

    from dataset.models.media_type import MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV, normalize_media_type
    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(args.scale)
    from desktop.theme.ui_modules import ensure_scaled_ui_modules

    ensure_scaled_ui_modules()
    from desktop.shell.main_window import WatchedMoviesWindow

    app = QApplication.instance() or QApplication(sys.argv)
    families = set(QFontDatabase.families())
    target_media_type = MEDIA_TYPE_MOVIE if args.media_type == "movie" else MEDIA_TYPE_TV

    window = WatchedMoviesWindow(initial_size=(args.width, args.height))
    window.show()
    window.raise_()
    window.activateWindow()
    _process_events(app, 20)

    list_widget = window.findChild(QListWidget, "watchedList")
    selected_row = -1
    selected_title = ""
    if list_widget is not None:
        for row in range(list_widget.count()):
            item = list_widget.item(row)
            entry = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            if not (isinstance(entry, tuple) and len(entry) == 3):
                continue
            card = entry[2]
            if normalize_media_type(card.get("media_type")) != target_media_type:
                continue
            selected_row = row
            selected_title = str(card.get("title") or entry[0])
            list_widget.setCurrentRow(row)
            break

    _process_events(app, 30)

    if args.scroll_detail_right:
        areas = [
            area
            for area in window.findChildren(QScrollArea)
            if area.isVisible() and area.horizontalScrollBar().maximum() > 0
        ]
        if areas:
            area = max(areas, key=lambda item: item.geometry().width())
            area.horizontalScrollBar().setValue(area.horizontalScrollBar().maximum())
            _process_events(app, 20)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    saved = window.grab().save(str(args.output))
    print(f"platform={app.platformName()}")
    print(
        "font_probe="
        f"{{'family_count': {len(families)}, "
        f"'has_segoe_ui': {'Segoe UI' in families}, "
        f"'has_arial': {'Arial' in families}}}"
    )
    print(f"media_type={args.media_type} row={selected_row} title={selected_title}")
    print(f"window_size={window.width()}x{window.height()}")
    print(f"saved={saved} path={args.output}")
    window.close()
    app.processEvents()
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
