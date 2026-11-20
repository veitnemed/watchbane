from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QLabel
from desktop.story.view import StorySearchView
from tests.test_story_catalog import FakeTMDb


def test_clean_home_real_only_then_existing_auth_mock_import(qtbot,monkeypatch):
    import requests
    from apis import tmdb_api
    from desktop.startup import worker as auth_worker
    credentials=[False];fake=FakeTMDb()
    monkeypatch.setattr(requests.Session,'request',lambda *a,**k: (_ for _ in ()).throw(AssertionError('Live network prohibited')))
    monkeypatch.setattr(tmdb_api,'has_tmdb_credentials',lambda:credentials[0])
    monkeypatch.setattr(auth_worker,'evaluate_tmdb_startup_readiness',lambda token:{'ready':True})
    monkeypatch.setattr(tmdb_api,'save_tmdb_bearer_token',lambda token:credentials.__setitem__(0,True))
    monkeypatch.setattr(tmdb_api,'tmdb_get',lambda path,params,**kw:fake.discover(path.rsplit('/',1)[-1],params))
    monkeypatch.setattr(tmdb_api,'get_movie_details',lambda identifier,language,**kw:fake.details('movie',identifier,language))
    monkeypatch.setattr(tmdb_api,'get_tv_details',lambda identifier,language,**kw:fake.details('tv',identifier,language))
    view=StorySearchView();qtbot.addWidget(view.widget);view.widget.resize(1180,950);view.widget.show()
    assert view._auth_dialog is None and 'Каталог пока пуст' in view.catalog_status.text()
    assert not view.search_button.isEnabled()
    assert view.catalog_button.text()=='Заполнить каталог из TMDb'
    view.query.setText('врач');view.search()
    qtbot.waitUntil(lambda:view._worker is None)
    assert view.cards_layout.count()==1 and not fake.calls
    qtbot.mouseClick(view.catalog_button,Qt.MouseButton.LeftButton)
    assert view._auth_dialog.isVisible()
    from desktop.settings.tmdb_credentials_panel import TmdbCredentialsPanel
    panel=view._auth_dialog.findChild(TmdbCredentialsPanel)
    assert panel._token_input.echoMode()==QLineEdit.EchoMode.Password
    panel._token_input.setText('synthetic-test-token-not-a-secret');panel._save()
    qtbot.waitUntil(lambda:credentials[0] and view._catalog_worker is None and 'Добавлено: 6' in view.catalog_status.text(),timeout=10000)
    qtbot.waitUntil(lambda:view._worker is None,timeout=10000)
    assert view.search_button.isEnabled() and view.query.text() == "врач"
    assert len(view._records)==6 and view.cards_layout.count()>1
    assert any('Вымышленный' in w.text() for w in view.cards.findChildren(QLabel,'storyTitle'))
    assert all('query' not in c[2] and 'врач' not in str(c[2]) for c in fake.calls if c[0]=='discover')
    view._fill_catalog();qtbot.waitUntil(lambda:view._catalog_worker is None)
    qtbot.waitUntil(lambda:view._worker is None)
    assert 'Новых описаний' in view.catalog_status.text()
    view.prepare_for_shutdown()


def test_qt_cancel_and_error_keep_existing_catalog(qtbot,monkeypatch):
    from threading import Event
    from apis import tmdb_api
    from candidates import onboarding_service
    from candidates.repositories.pool_repository import load_candidate_pool
    from candidates.story_catalog import fill_story_catalog
    fill_story_catalog(client=FakeTMDb());before=load_candidate_pool()
    entered=Event();release=Event()
    fake=FakeTMDb()
    def discover(media,params):
        entered.set();release.wait(3)
        return {'results':[{'id':999}]}
    fake.discover=discover
    monkeypatch.setattr(tmdb_api,'has_tmdb_credentials',lambda:True)
    monkeypatch.setattr(onboarding_service,'_build_filter_replenish_tmdb_client',lambda:fake)
    view=StorySearchView();qtbot.addWidget(view.widget);view.widget.resize(1180,950);view.widget.show()
    view._fill_catalog();qtbot.waitUntil(entered.is_set)
    assert view.cancel_catalog_button.isVisible() and not view.catalog_button.isEnabled()
    view._cancel_catalog();release.set();qtbot.waitUntil(lambda:view._catalog_worker is None)
    assert 'отменена' in view.catalog_status.text() and load_candidate_pool()==before
    fake.discover=lambda *a: (_ for _ in ()).throw(OSError('mock network error'))
    view._fill_catalog();qtbot.waitUntil(lambda:view._catalog_worker is None)
    assert 'не удалась' in view.catalog_status.text() and load_candidate_pool()==before
    assert view.catalog_button.isEnabled()
    view.prepare_for_shutdown()
