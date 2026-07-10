"""Capture a native screenshot of the TMDb startup gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("screens/tmp_ui/startup/tmdb_gate_scale100.png"),
    )
    args = parser.parse_args(argv)

    from PyQt6.QtWidgets import QApplication

    from desktop.startup import TmdbStartupGateView
    from desktop.theme import build_app_style
    from desktop.theme.scaling import set_ui_scale

    app = QApplication(sys.argv)
    set_ui_scale(args.scale)
    gate = TmdbStartupGateView()
    gate.setStyleSheet(build_app_style())
    gate.resize(1180, 720)
    gate.show()
    app.processEvents()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    gate.grab().save(str(args.output))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
