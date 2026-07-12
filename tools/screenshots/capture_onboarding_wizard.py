"""Capture a native screenshot of the onboarding autofill wizard.

Example:
    py tools/screenshots/capture_onboarding_wizard.py --scale 1.0 --output tmp/ui/onboarding/wizard_scale100.png
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=1.0, help="Application UI scale.")
    parser.add_argument("--language", choices=("ru", "en"), default="ru")
    parser.add_argument("--page", type=int, default=0, help="Zero-based question page index.")
    parser.add_argument("--loading", action="store_true", help="Capture the loading/progress page.")
    parser.add_argument("--plan", action="store_true", help="Capture the autofill plan summary page.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tmp/ui/onboarding/wizard_scale100.png"),
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

    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(args.scale)
    from desktop.theme.ui_modules import ensure_scaled_ui_modules

    ensure_scaled_ui_modules()
    from desktop.onboarding import OnboardingAutofillDialog

    app = QApplication.instance() or QApplication(sys.argv)
    families = set(QFontDatabase.families())
    dialog = OnboardingAutofillDialog(ui_language=args.language)
    page_count = len(dialog._question_pages)
    if args.plan:
        page = dialog._plan_index()
    elif args.loading:
        page = dialog._loading_index()
    else:
        page = max(0, min(int(args.page), max(0, page_count - 1)))
    dialog._set_page(page)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    _process_events(app, 20)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    saved = dialog.grab().save(str(args.output))
    print(f"platform={app.platformName()}")
    print(
        "font_probe="
        f"{{'family_count': {len(families)}, "
        f"'has_segoe_ui': {'Segoe UI' in families}, "
        f"'has_arial': {'Arial' in families}}}"
    )
    print(f"language={args.language} scale={args.scale} page={page} page_count={page_count} loading={args.loading}")
    print(f"dialog_size={dialog.width()}x{dialog.height()}")
    print(f"saved={saved} path={args.output}")
    dialog.close()
    app.processEvents()
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
