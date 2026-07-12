"""Capture the deck reserve indicator prototype at application UI scale."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _process_events(app, seconds: float = 0.5) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=220)
    parser.add_argument("--mode", choices=("loading", "ready"), default="ready")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("screens/tmp_ui/deck_reserve_indicator/prototype_scale100.png"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")

    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(args.scale)
    from desktop.theme.ui_modules import ensure_scaled_ui_modules

    ensure_scaled_ui_modules()

    from PyQt6.QtGui import QFont, QFontDatabase
    from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

    from candidates.deck_reserve_presentation import DeckReservePresentation
    from candidates.recommendation_deck_service import compute_deck_reserve_snapshot
    from desktop.candidates.deck_reserve_indicator import DeckReserveIndicator
    from desktop.i18n import tr
    from desktop.theme import FONT_APP, FONT_FAMILY, build_app_style, font_px, list_px
    from desktop.theme.tokens import FILM_SURFACE_0

    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, font_px(FONT_APP)))

    root = QWidget()
    root.setObjectName("deckReservePrototypeRoot")
    root.setStyleSheet(f"QWidget#deckReservePrototypeRoot {{ background-color: {FILM_SURFACE_0}; }}")
    root_layout = QVBoxLayout(root)
    root_layout.setContentsMargins(list_px(24), list_px(24), list_px(24), list_px(24))
    root_layout.setSpacing(list_px(16))

    feed_header = QWidget()
    feed_header.setObjectName("recommendationsFeedHeader")
    feed_header_layout = QHBoxLayout(feed_header)
    feed_header_layout.setContentsMargins(0, 0, 0, 0)
    feed_header_layout.setSpacing(list_px(10))

    feed_title = QLabel(tr("recommendations.feed.title"))
    feed_title.setObjectName("recommendationsFeedTitle")
    feed_header_layout.addWidget(feed_title)

    indicator = DeckReserveIndicator(feed_header)
    if args.mode == "loading":
        indicator.apply_presentation(
            DeckReservePresentation(
                mode="loading",
                tooltip_key="recommendations.deck_reserve.loading",
            )
        )
    else:
        snapshot = compute_deck_reserve_snapshot(
            {
                "active_limit": 25,
                "active": [{}] * 25,
                "reserve": [{}] * 70,
            }
        )
        indicator.apply_presentation(
            DeckReservePresentation(
                mode="ready",
                snapshot=snapshot,
                tooltip_key="recommendations.deck_reserve.tooltip",
                tooltip_kwargs={"remaining": snapshot.remaining, "target": snapshot.target},
            )
        )
    feed_header_layout.addWidget(indicator)
    feed_header_layout.addStretch(1)

    status_label = QLabel(tr("recommendations.feed.count", count=25))
    status_label.setObjectName("recommendationsDeckStatus")
    feed_header_layout.addWidget(status_label)

    root_layout.addWidget(feed_header)
    root_layout.addStretch(1)

    window = QMainWindow()
    window.setWindowTitle("Watchbane - Deck Reserve Indicator")
    window.setCentralWidget(root)
    window.setStyleSheet(build_app_style())
    window.resize(args.width, args.height)
    window.show()
    window.raise_()
    window.activateWindow()
    _process_events(app, 0.8)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    saved = window.grab().save(str(args.output))
    families = set(QFontDatabase.families())
    print(f"platform={app.platformName()}")
    print(
        "font_probe="
        f"{{'family_count': {len(families)}, 'has_segoe_ui': {'Segoe UI' in families}}}"
    )
    print(f"scale={args.scale} mode={args.mode} window={window.width()}x{window.height()}")
    print(f"saved={saved} path={args.output}")
    window.close()
    _process_events(app, 0.1)
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
