"""Existing SQLite catalog + Qt save/reopen smoke in an explicitly isolated profile.
External corpus content is never included in the output report.
"""
import argparse
import json
import os
from pathlib import Path
from time import perf_counter, sleep


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--seed-corpus', type=Path, required=True)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from tools.qa.isolation import apply_isolated_data_dir
    apply_isolated_data_dir(args.runtime_root)
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    os.environ['WATCHBANE_STORY_MODEL_DIR'] = str(args.model_dir.resolve())
    os.environ['WATCHBANE_INTERFACE_LANGUAGE'] = 'ru'
    os.environ['WATCHBANE_DATA_LANGUAGE'] = 'ru'
    from storage.runtime import ensure_runtime_data_layout
    from candidates.repositories.pool_repository import save_candidate_pool
    from candidates.pool_service import get_pool_view
    ensure_runtime_data_layout()
    if not get_pool_view():
        raw = json.loads(args.seed_corpus.read_text())
        records = {}
        for r in raw:
            if r.get('language') != 'ru-RU' or not r.get('overview'):
                continue
            records[r['key']] = dict(title=r['title'], overview=r['overview'], media_type=r['media_type'],
                                     tmdb_id=int(r['key'].split(':')[1]), source='tmdb')
        save_candidate_pool(records)
    count = len(get_pool_view())
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QPushButton, QLabel, QScrollArea
    from desktop.shell.main_window import WatchedMoviesWindow
    from candidates import story_service
    app = QApplication([])
    ticks = []
    timer = QTimer(); timer.timeout.connect(lambda: ticks.append(perf_counter())); timer.start(20)
    start = perf_counter(); window = WatchedMoviesWindow(initial_size=(1180, 950)); window.show()
    window.schedule_tmdb_startup_gate(0); app.processEvents()
    startup_ms = (perf_counter()-start)*1000
    view = window._tab_registry._specs['story'].view
    assert view.mode.currentIndex() == 2
    def search(query):
        start = perf_counter(); view.query.setText(query)
        QTest.mouseClick(view.search_button, Qt.MouseButton.LeftButton)
        assert view.query.isEnabled()
        while view._worker is not None and perf_counter()-start < 120:
            app.processEvents(); sleep(.005)
        assert view._worker is None, 'Search timeout'
        app.processEvents()
        return (perf_counter()-start)*1000
    cold = search('сериал про преступника')
    first_engine = next(iter(story_service._INDEX_CACHE.values()))
    assert view._records and all(not h.demo for h in first_engine.documents)
    first_titles = [w.text() for w in view.cards.findChildren(QLabel, 'storyTitle')]
    warm = search('отмывание денег')
    assert next(iter(story_service._INDEX_CACHE.values())) is first_engine
    save = next(b for b in view.cards.findChildren(QPushButton) if b.text() == 'Сохранить')
    view.widget.findChild(QScrollArea).ensureWidgetVisible(save)
    app.processEvents(); QTest.mouseClick(save, Qt.MouseButton.LeftButton); app.processEvents()
    assert 'Сохранено' in view.status.text(), view.status.text()
    window.shutdown_background_workers(); window.close(); app.processEvents()
    window = WatchedMoviesWindow(initial_size=(1180, 950)); window.show(); app.processEvents()
    watched = window._tabs_context.watched_tab_view
    window._tab_registry.focus('watched'); watched._switch_section('watchlist'); app.processEvents()
    saved_count = len(watched._entries)
    assert saved_count >= 1
    window._tab_registry.focus('story'); view = window._tab_registry._specs['story'].view
    reopen = search('отмывание денег')
    assert view._records
    window.shutdown_background_workers(); window.close(); timer.stop()
    gaps = [(b-a)*1000 for a,b in zip(ticks,ticks[1:])]
    report = dict(platform=app.platformName(), catalog_records=count, automatic_local_catalog=True,
                  startup_ms=startup_ms, cold_search_ms=cold, warm_search_ms=warm,
                  same_engine_reused=True, reopened_search_ms=reopen, saved_after_reopen=saved_count,
                  heartbeat_max_gap_ms=max(gaps,default=0), input_enabled_during_search=True,
                  first_result_titles=first_titles, notes='Linux offscreen. Temporary SQLite with genuine external TMDb descriptions. No API or personal profile; no synopsis text exported.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__': main()
