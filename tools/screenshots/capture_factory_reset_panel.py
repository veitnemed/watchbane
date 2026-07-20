"""Capture the Factory Reset settings panel with its active runtime path."""

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
    from PyQt6.QtWidgets import QApplication

    from desktop.settings.factory_reset_panel import FactoryResetPanel
    from desktop.theme import FONT_APP, FONT_FAMILY, build_app_style, font_px

    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, font_px(FONT_APP)))
    panel = FactoryResetPanel()
    panel.setStyleSheet(build_app_style())
    panel.resize(760, panel.sizeHint().height())
    panel.show()
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    saved = panel.grab().save(str(args.output))
    families = set(QFontDatabase.families())
    print(f"platform={app.platformName()}")
    print(f"font_probe={{'family_count': {len(families)}, 'has_segoe_ui': {'Segoe UI' in families}}}")
    print(f"scale={args.scale} window={panel.width()}x{panel.height()} saved={saved} path={args.output}")
    panel.close()
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
