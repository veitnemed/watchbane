"""Three real Qt captures: clean home, entered query, E5 synthetic demo results.

No network, credentials, personal profile or external synopsis corpus is needed.
"""
import argparse
from pathlib import Path
import os
from time import monotonic,sleep


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--scale',type=float,default=1)
    args=parser.parse_args()
    from tools.qa.isolation import apply_isolated_data_dir
    apply_isolated_data_dir(args.runtime_root)
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    os.environ['WATCHBANE_STORY_MODEL_DIR']=str(args.model_dir.resolve())
    os.environ['WATCHBANE_INTERFACE_LANGUAGE']='ru'
    os.environ['WATCHBANE_DATA_LANGUAGE']='ru'
    import requests
    def deny(*a,**k):raise AssertionError('Screenshot must be offline')
    requests.Session.request=deny
    from PyQt6.QtCore import Qt,QCoreApplication,QEvent
    from PyQt6.QtGui import QFont
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    from desktop.theme.scaling import set_ui_scale,font_px
    set_ui_scale(args.scale)
    from desktop.theme import FONT_APP,FONT_FAMILY
    from desktop.shell.main_window import WatchedMoviesWindow
    from storage.runtime import ensure_runtime_data_layout
    from candidates.pool_service import get_pool_view
    ensure_runtime_data_layout()
    if get_pool_view():raise RuntimeError('Captures require an empty isolated profile')
    app=QApplication([]);app.setFont(QFont(FONT_FAMILY,font_px(FONT_APP)))
    window=WatchedMoviesWindow(initial_size=(1280,1000));window.show();window.schedule_tmdb_startup_gate(0)
    view=window._tab_registry._specs['story'].view
    args.output_dir.mkdir(parents=True,exist_ok=True)
    def capture(name):
        for _ in range(5):app.processEvents();sleep(.01)
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        if not window.grab().save(str(args.output_dir/name)):raise RuntimeError('Capture failed')
    capture('01-home.png')
    view.query.setFocus();view.query.setText('выживание в космосе')
    capture('02-query.png')
    QTest.mouseClick(view.search_button,Qt.MouseButton.LeftButton)
    deadline=monotonic()+60
    while view._worker is not None and monotonic()<deadline:app.processEvents();sleep(.005)
    assert view._worker is None and view.cards_layout.count()>1
    assert 'E5' in view.backend_label.text()
    capture('03-results.png')
    import json
    from PyQt6.QtWidgets import QScrollArea
    viewport=view.widget.findChild(QScrollArea).viewport()
    bottom=viewport.mapTo(window,viewport.rect().bottomLeft()).y()
    cards=[view.cards_layout.itemAt(i).widget() for i in range(view.cards_layout.count()-1)]
    metrics={'scale':args.scale,'first_card_y':cards[0].mapTo(window,cards[0].rect().topLeft()).y(),
             'fully_visible_cards':sum(c.mapTo(window,c.rect().bottomLeft()).y()<=bottom for c in cards),
             'window_size':[window.width(),window.height()], 'source':'actual Qt offscreen; original fictional demo; local FP32'}
    (args.output_dir/'geometry.json').write_text(json.dumps(metrics,indent=2)+'\n')
    window.shutdown_background_workers();window.close()
    print(f'Qt={app.platformName()}, scale={args.scale}; 3 PNG; actual E5; original fictional demo; no live TMDb import.')


if __name__=='__main__':main()
