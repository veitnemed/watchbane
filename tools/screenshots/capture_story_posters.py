"""Real Qt cartoon shell: empty home, synthetic local search, saved collection."""
import argparse,json,os
from pathlib import Path
from time import monotonic,sleep


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--scale',type=float,default=1)
    p.add_argument("--live-cdn", action="store_true", help="Explicit direct TMDb image CDN smoke; no API or search sent")
    a=p.parse_args()
    from tools.qa.isolation import apply_isolated_data_dir
    apply_isolated_data_dir(a.runtime_root)
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen');os.environ['WATCHBANE_STORY_MODEL_DIR']=str(a.model_dir.resolve())
    os.environ['WATCHBANE_INTERFACE_LANGUAGE']='ru';os.environ['WATCHBANE_DATA_LANGUAGE']='ru'
    import requests
    requests.Session.request=lambda *x,**k: (_ for _ in ()).throw(AssertionError('Offline screenshot'))
    from PyQt6.QtWidgets import QApplication,QPushButton,QLabel,QScrollArea
    from PyQt6.QtCore import Qt,QCoreApplication,QEvent
    from PyQt6.QtGui import QFont
    from PyQt6.QtTest import QTest
    from desktop.theme.scaling import set_ui_scale,font_px
    set_ui_scale(a.scale)
    from desktop.theme import FONT_APP,FONT_FAMILY
    from storage.runtime import ensure_runtime_data_layout
    from candidates.pool_service import get_pool_view
    ensure_runtime_data_layout()
    if get_pool_view():raise RuntimeError('Use a fresh empty temporary profile')
    from desktop.shell.main_window import WatchedMoviesWindow
    app=QApplication([]);app.setFont(QFont(FONT_FAMILY,font_px(FONT_APP)))
    window=WatchedMoviesWindow(initial_size=(1280,1000));window.show();window.schedule_tmdb_startup_gate(0)
    view=window._tab_registry._specs['story'].view
    network=[]
    view.posters.controller._manager.finished.connect(lambda reply: network.append({'status':reply.attribute(__import__('PyQt6.QtNetwork',fromlist=['QNetworkRequest']).QNetworkRequest.Attribute.HttpStatusCodeAttribute),'error':reply.error().name}))
    a.output_dir.mkdir(parents=True,exist_ok=True)
    def capture(name):
        for _ in range(5):app.processEvents();sleep(.01)
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        assert window.grab().save(str(a.output_dir/name))
    capture('01-home.png')
    # Original Watchbane fiction, persisted only in this disposable QA profile.
    from candidates.story_demo import demo_documents
    from candidates.repositories.pool_repository import save_candidate_pool
    docs=demo_documents()
    selected=[d for d in docs if d.title in ('Обратная орбита','Точка пересадки','Дело на орбите')]
    assert len(selected)==3
    records={f'preview:{i}':{'title':d.title,'overview':d.overview,'year':2025,'media_type':d.media_type,'tmdb_id':9900000+i,'source':'synthetic-preview'} for i,d in enumerate(selected)}
    if a.live_cdn:
        # Public TMDb Interstellar image URL; synopsis below is authored for this smoke.
        records = {'poster-smoke': {'title':'Интерстеллар', 'overview':'Космонавты покидают умирающую Землю и ищут новый дом для человечества. Отец пытается вернуться к дочери сквозь пространство и время.', 'year':2014, 'media_type':'movie', 'tmdb_id':157336, 'source':'TMDb poster CDN; independently authored smoke synopsis', 'poster_path':'/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg', 'poster_url':'https://image.tmdb.org/t/p/w342/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg'}}
    save_candidate_pool(records)
    view.on_tab_activated();view.query.setText('выживание в космосе');QTest.keyClick(view.query,Qt.Key.Key_Return)
    deadline=monotonic()+60
    while view._worker is not None and monotonic()<deadline:app.processEvents();sleep(.005)
    assert view._worker is None and view.cards_layout.count()==(2 if a.live_cdn else 4)
    if a.live_cdn:
        deadline=monotonic()+15
        while monotonic()<deadline:
            app.processEvents();sleep(.01)
            if view.posters.controller._attempted_urls and not view.posters.controller._active:break
    from PyQt6.QtWidgets import QLabel
    poster_labels=[x for x in view.cards.findChildren(QLabel)] if hasattr(view,'cards') else view.widget.findChildren(QLabel,'storyPoster')
    poster_count=sum(1 for x in poster_labels if x.objectName()=='storyPoster' and x.pixmap() is not None and not x.pixmap().isNull())
    capture('02-results.png')
    card=view.cards_layout.itemAt(0).widget();top=card.mapTo(window,card.rect().topLeft()).y()
    button=next(b for b in card.findChildren(QPushButton) if b.text()=='Сохранить');QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    window._tab_registry.focus('watched');app.processEvents()
    collection=window._tab_registry._specs['watched'].view
    assert len(collection._entries)==1
    capture('03-collection.png')
    collection_posters=sum(1 for x in collection.widget.findChildren(QLabel,'storyPoster') if x.pixmap() is not None and not x.pixmap().isNull())
    window.shutdown_background_workers();window.close();app.processEvents()
    reopened=WatchedMoviesWindow(initial_size=(1280,1000))
    reopened_collection=reopened._tab_registry._specs['watched'].view
    reopened_collection.posters.controller._manager.get=lambda *args: (_ for _ in ()).throw(AssertionError('Reopen must use local poster cache'))
    reopened.show();reopened._tab_registry.focus('watched')
    for _ in range(5):app.processEvents();sleep(.01)
    if a.live_cdn and poster_count:
        assert any(x.pixmap() is not None and not x.pixmap().isNull() for x in reopened_collection.widget.findChildren(QLabel,'storyPoster'))
    assert len(reopened._tab_registry._specs['watched'].view._entries)==1
    reopened.shutdown_background_workers();reopened.close()
    report={'scale':a.scale,'visible_sections':['Поиск','Коллекция'],'first_card_y':top,'saved_and_reopened':True,
            'network':network, 'collection_posters':collection_posters, 'reopen_network_disabled':True, 'posters_visible':poster_count, 'source':('Linux Qt offscreen; real FP32; live direct TMDb CDN; independently authored Interstellar synopsis; no API/token' if a.live_cdn else 'Linux Qt offscreen; original fiction; no network')}
    (a.output_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
