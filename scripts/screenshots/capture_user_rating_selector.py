"""Capture all selected states of the shared user reaction selector."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")

    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(args.scale)
    from desktop.theme.ui_modules import ensure_scaled_ui_modules

    ensure_scaled_ui_modules()

    from PyQt6.QtGui import QFont, QFontDatabase
    from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    from desktop.i18n import tr
    from desktop.shared.widgets.user_rating_selector import UserRatingSelector
    from desktop.theme import FONT_APP, FONT_FAMILY, build_app_style, font_px, layout_px

    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, font_px(FONT_APP)))
    window = QWidget()
    window.setObjectName("candidateFiltersRoot")
    layout = QVBoxLayout(window)
    layout.setContentsMargins(layout_px(24), layout_px(24), layout_px(24), layout_px(24))
    layout.setSpacing(layout_px(16))
    title = QLabel(tr("user_rating.prompt"))
    title.setObjectName("candidateSearchHeader")
    layout.addWidget(title)
    selectors: list[UserRatingSelector] = []
    for value in (1, 2, 3):
        selector = UserRatingSelector()
        selector.setValue(value)
        layout.addWidget(selector)
        selectors.append(selector)
    selectors[1].buttons()[1].setFocus()
    window.setStyleSheet(build_app_style())
    window.resize(760, 320)
    window.show()
    deadline = time.monotonic() + 0.4
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    saved = window.grab().save(str(args.output))
    families = set(QFontDatabase.families())
    print(f"platform={app.platformName()}")
    print(f"font_probe={{'family_count': {len(families)}, 'has_segoe_ui': {'Segoe UI' in families}}}")
    print(f"scale={args.scale} window={window.width()}x{window.height()} saved={saved} path={args.output}")
    window.close()
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
