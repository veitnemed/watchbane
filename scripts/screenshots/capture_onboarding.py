"""Capture native screenshots for the fullscreen onboarding flow.

Examples:
    py scripts/screenshots/capture_onboarding.py --step welcome --scale 1.0
    py scripts/screenshots/capture_onboarding.py --step plan --language ru --output screens/tmp_ui/onboarding/plan.png
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


STEP_NAMES = ("welcome", "scale", "taste", "plan", "loading", "final")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", choices=STEP_NAMES, default="welcome")
    parser.add_argument("--scale", type=float, default=1.0, help="Application UI scale.")
    parser.add_argument("--language", choices=("ru", "en"), default="ru")
    parser.add_argument("--empty-profile", action="store_true", help="Use dev empty-profile flags for this process.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="PNG output path. Defaults to screens/tmp_ui/onboarding/<step>_scaleNNN.png.",
    )
    return parser


def _process_events(app, rounds: int, delay: float = 0.03) -> None:
    for _ in range(rounds):
        app.processEvents()
        time.sleep(delay)


def _select_first_options(dialog) -> None:
    for _question, _page, group in dialog._question_pages:
        button = group.buttons()[0] if group.buttons() else None
        if button is not None:
            button.setChecked(True)
            dialog._answers[_question.key] = str(button.property("answer") or "")


def _prepare_step(dialog, step: str) -> None:
    if step in {"welcome", "scale"}:
        dialog._set_page(0)
        return
    if step == "taste":
        dialog._set_page(1)
        return
    _select_first_options(dialog)
    if step == "plan":
        dialog._set_page(dialog._plan_index())
        return
    if step == "loading":
        dialog._set_page(dialog._loading_index())
        dialog._progress.setValue(42)
        dialog._status_label.setText(dialog._text("Собираем фильмы · лёгкий вайб", "Building movies · light vibe"))
        return
    if step == "final":
        dialog._show_final_result(
            {
                "created_count": 99,
                "warning": "Starter pool underfilled: created 99 of 120.",
                "ok": True,
                "api_requests": 180,
                "rejected_future_count": 0,
                "planned_counts": {
                    "country": {"US": 108, "GB": 12},
                    "media_type": {"movie": 60, "tv": 60},
                    "origin": {"domestic": 60, "foreign": 60},
                },
                "actual_counts": {
                    "country": {"US": 90, "GB": 9},
                    "media_type": {"movie": 49, "tv": 50},
                    "origin": {"domestic": 39, "foreign": 60},
                },
            },
            failed=False,
        )
        return
    raise ValueError(f"Unsupported step: {step}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "windows" if os.name == "nt" else "offscreen"
    if args.empty_profile:
        os.environ["WATCHBANE_DEV_EMPTY_PROFILE"] = "1"
        os.environ["WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START"] = "1"

    from PyQt6.QtCore import QPoint
    from PyQt6.QtGui import QCursor, QFontDatabase
    from PyQt6.QtWidgets import QApplication

    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(args.scale)
    from desktop.theme.ui_modules import ensure_scaled_ui_modules

    ensure_scaled_ui_modules()
    from desktop.onboarding import OnboardingAutofillDialog

    app = QApplication.instance() or QApplication(sys.argv)
    families = set(QFontDatabase.families())
    dialog = OnboardingAutofillDialog(ui_language=args.language)
    _prepare_step(dialog, args.step)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    _process_events(app, 20)
    QCursor.setPos(dialog.mapToGlobal(QPoint(6, 6)))
    _process_events(app, 3, delay=0.02)

    output = args.output
    if output is None:
        scale_text = str(int(round(args.scale * 100))).zfill(3)
        output = Path("screens/tmp_ui/onboarding") / f"{args.step}_scale{scale_text}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    saved = dialog.grab().save(str(output))
    print(f"platform={app.platformName()}")
    print(
        "font_probe="
        f"{{'family_count': {len(families)}, "
        f"'has_segoe_ui': {'Segoe UI' in families}, "
        f"'has_arial': {'Arial' in families}}}"
    )
    print(f"step={args.step} language={args.language} scale={args.scale} empty_profile={args.empty_profile}")
    print(f"dialog_size={dialog.width()}x{dialog.height()}")
    print(f"saved={saved} path={output}")
    dialog.close()
    app.processEvents()
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
