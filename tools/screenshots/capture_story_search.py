"""Offline story-home capture with an explicitly isolated runtime."""
import argparse
import os
from pathlib import Path
import sys
from time import monotonic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale",type=float,default=1.0)
    parser.add_argument("--runtime-root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--query",default="сериал про пристурника")
    args=parser.parse_args()
    from tools.qa.isolation import apply_isolated_data_dir
    apply_isolated_data_dir(args.runtime_root)
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    os.environ["WATCHBANE_INTERFACE_LANGUAGE"]="ru"
    os.environ["WATCHBANE_DATA_LANGUAGE"]="ru"
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont
    from desktop.theme.scaling import set_ui_scale, font_px
    set_ui_scale(args.scale)
    from desktop.theme import FONT_APP, FONT_FAMILY
    from desktop.shell.main_window import WatchedMoviesWindow
    app=QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY,font_px(FONT_APP)))
    window=WatchedMoviesWindow(initial_size=(1180,850))
    window.show()
    window.schedule_tmdb_startup_gate(0)
    view=window._tab_registry._specs["story"].view
    view.query.setText(args.query); view.search()
    deadline=monotonic()+15
    while view._worker is not None and monotonic()<deadline: app.processEvents()
    if view._worker is not None: raise RuntimeError("Search timeout")
    for _ in range(10): app.processEvents()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if not window.grab().save(str(args.output)): raise RuntimeError("Screenshot save failed")
    print(f"platform={app.platformName()} scale={args.scale} cards={view.cards_layout.count()-1} output={args.output}")
    window.shutdown_background_workers(); window.close()

if __name__=="__main__": main()
