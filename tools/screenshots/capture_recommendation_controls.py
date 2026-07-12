"""Capture the recommendation controls with a synthetic local candidate pool."""

from __future__ import annotations

import argparse
import os
import sys
import time
from copy import deepcopy
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
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--advanced", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")

    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(args.scale)
    from desktop.theme.ui_modules import ensure_scaled_ui_modules

    ensure_scaled_ui_modules()

    from PyQt6.QtGui import QFont, QFontDatabase
    from PyQt6.QtWidgets import QApplication, QMainWindow, QScrollArea

    from desktop.candidates.filters_view import CandidateFiltersView
    from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS
    from desktop.theme import FONT_APP, FONT_FAMILY, build_app_style, font_px

    candidates = [
        {
            "pool_entry_key": f"visual-{index}|2024|movie",
            "title": f"Тайтл {index + 1}",
            "year": 2024,
            "media_type": "movie",
            "country_codes": ["RU" if index % 2 else "US"],
            "is_searchable": True,
            "is_complete": True,
        }
        for index in range(36)
    ]

    class LocalService:
        SEARCH_SORT_MODES = ("final_score",)

        def get_search_overview_view(self):
            return {
                "is_empty": False,
                "stats": {"unique_total": len(candidates)},
                "candidates": deepcopy(candidates),
            }

        def search_candidate_pool(self, source, _filters):
            return {"candidates": list(source), "filtered_count": len(source)}

        def sort_search_candidates(self, source, sort_mode):
            return {"candidates": list(source), "sort_mode": sort_mode, "hidden_duplicates": 0}

        def get_search_filter_defaults_view(self):
            return {"defaults": dict(DEFAULT_BROWSE_FILTERS)}

        def get_search_filter_chip_options_view(self):
            return {
                "genres": [{"label": value} for value in ("Драма", "Комедия", "Триллер", "Фантастика")],
                "countries": [
                    {"code": "RU", "label": "Россия"},
                    {"code": "US", "label": "США"},
                    {"code": "JP", "label": "Япония"},
                    {"code": "KR", "label": "Южная Корея"},
                ],
            }

    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, font_px(FONT_APP)))
    service = LocalService()
    session = CandidateSearchSession(service=service)
    view = CandidateFiltersView(session, service=service)
    view._form.advanced_mode_toggle.setChecked(args.advanced)

    window = QMainWindow()
    window.setWindowTitle("Watchbane - Recommendations")
    window.setCentralWidget(view.widget)
    window.setStyleSheet(build_app_style())
    window.resize(args.width, args.height)
    window.show()
    window.raise_()
    window.activateWindow()
    _process_events(app, 0.8)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    saved = window.grab().save(str(args.output))
    families = set(QFontDatabase.families())
    horizontal_scroll = [
        (area.objectName(), area.horizontalScrollBar().maximum())
        for area in window.findChildren(QScrollArea)
        if area.isVisible() and area.horizontalScrollBar().maximum() > 0
    ]
    print(f"platform={app.platformName()}")
    print(
        "font_probe="
        f"{{'family_count': {len(families)}, 'has_segoe_ui': {'Segoe UI' in families}}}"
    )
    print(
        f"scale={args.scale} window={window.width()}x{window.height()} "
        f"advanced={args.advanced} horizontal_scroll={horizontal_scroll}"
    )
    print(f"saved={saved} path={args.output}")
    window.close()
    _process_events(app, 0.1)
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
