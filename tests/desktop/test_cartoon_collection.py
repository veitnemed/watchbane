from PyQt6.QtWidgets import QPushButton,QMessageBox,QInputDialog
from candidates import service
from candidates.title_state_service import get_title_state


def test_saved_hidden_watched_score_and_confirmed_delete(qtbot,monkeypatch):
    candidate={'title':'Вымышленная тестовая история','year':2025,'media_type':'movie','tmdb_id':993001,
               'overview':'Врач спасает путешественников.','source':'synthetic'}
    service.add_candidate_to_watchlist(candidate)
    from desktop.shell.main_window import WatchedMoviesWindow
    window=WatchedMoviesWindow(initial_size=(1280,1000));qtbot.addWidget(window);window.show()
    collection=window._tab_registry._specs['watched'].view;window._tab_registry.focus('watched')
    def click(text):
        next(b for b in collection.cards.findChildren(QPushButton) if b.text()==text).click()
        qtbot.wait(10)
    assert len(collection._entries)==1
    click('Скрыть');assert get_title_state(candidate)=='hidden'
    collection._switch_section('hidden');assert len(collection._entries)==1
    click('Вернуть');assert get_title_state(candidate)=='available'
    service.add_candidate_to_watchlist(candidate);collection._switch_section('watchlist')
    click('Смотрел');assert get_title_state(candidate)=='watched'
    collection._switch_section('watched');assert len(collection._entries)==1
    monkeypatch.setattr(QInputDialog,'getItem',lambda *a,**k:('3',True))
    click('Оценка')
    assert collection._entries[0][1]['main_info']['user_score']==3
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.No)
    click('Удалить…');assert get_title_state(candidate)=='watched'
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Yes)
    click('Удалить…');assert get_title_state(candidate)!='watched'
    window.shutdown_background_workers()


def test_collection_title_search_and_legacy_add_action(qtbot,monkeypatch):
    service.add_candidate_to_watchlist({'title':'Вымышленная орбита','year':2025,'media_type':'movie','tmdb_id':993002,'source':'synthetic'})
    from desktop.shell.main_window import WatchedMoviesWindow
    window=WatchedMoviesWindow(initial_size=(1280,1000));qtbot.addWidget(window);window.show()
    collection=window._tab_registry._specs['watched'].view;window._tab_registry.focus('watched')
    collection.search.setText('неизвестно');assert 'ничего нет' in collection.status.text()
    collection.search.setText('орбита');assert collection.layout.count()==2
    calls=[];monkeypatch.setattr(collection.legacy,'_open_add_title_dialog',lambda:calls.append('existing title flow'))
    next(b for b in collection.widget.findChildren(QPushButton) if b.text()=='Добавить по названию…').click()
    assert calls==['existing title flow']
    window.shutdown_background_workers()


def test_delete_service_failure_is_visible_without_losing_record(qtbot,monkeypatch):
    candidate={'title':'Вымышленная запись для ошибки','year':2025,'media_type':'movie','tmdb_id':993003,'source':'synthetic'}
    service.mark_story_watched(candidate)
    from desktop.shell.main_window import WatchedMoviesWindow
    from app.use_cases import watched_library
    window=WatchedMoviesWindow(initial_size=(1280,1000));qtbot.addWidget(window);window.show()
    view=window._tab_registry._specs['watched'].view;view._switch_section('watched')
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(watched_library,'delete_watched_title',lambda _: {'ok':False})
    next(b for b in view.cards.findChildren(QPushButton) if b.text()=='Удалить…').click()
    assert 'Не удалось удалить' in view.status.text()
    assert get_title_state(candidate)=='watched'
    window.shutdown_background_workers()


def test_added_title_opens_watched_and_returned_search_respects_hidden(qtbot,monkeypatch):
    from candidates.repositories.pool_repository import save_candidate_pool
    candidate={'title':'Вымышленный врач','year':2025,'media_type':'movie','tmdb_id':993004,'overview':'Врач лечит пациентов в больнице.','source':'synthetic'}
    save_candidate_pool({'fixture':candidate})
    from desktop.shell.main_window import WatchedMoviesWindow
    window=WatchedMoviesWindow(initial_size=(1280,1000));qtbot.addWidget(window);window.show()
    view=window._tab_registry._specs['story'].view;view.query.setText('врач');view.search();qtbot.waitUntil(lambda:view._worker is None)
    assert view.cards_layout.count()==2
    window._tab_registry.focus('watched')
    service.hide_candidate(candidate)
    window._tab_registry.focus('story');qtbot.waitUntil(lambda:view._worker is None)
    assert view.cards_layout.count()==1
    collection=window._tab_registry._specs['watched'].view
    from candidates.title_state_service import restore_candidate
    restore_candidate(candidate)
    monkeypatch.setattr(collection.legacy,'_open_add_title_dialog',lambda:service.mark_story_watched(candidate))
    collection._add_title()
    assert collection.legacy._library_section=='watched' and len(collection._entries)==1
    window.shutdown_background_workers()


def test_imported_saved_hidden_conflict_keeps_separate_media_and_restores(qtbot):
    from desktop.shell.main_window import WatchedMoviesWindow
    from storage.sqlite import action_repository as repo

    movie = {"title": "Общее имя", "year": 2025, "media_type": "movie"}
    series = dict(movie, media_type="tv")
    key = "общее имя|2025"
    repo.save_candidate_actions_dict(repo.ACTION_WATCHLIST, {
        key: repo.build_action_entry(movie, repo.ACTION_WATCHLIST),
        key + "|tv": repo.build_action_entry(series, repo.ACTION_WATCHLIST),
    })
    repo.save_candidate_actions_dict(repo.ACTION_HIDDEN, {
        key + "|movie": repo.build_action_entry(movie, repo.ACTION_HIDDEN),
    })
    window = WatchedMoviesWindow(initial_size=(1280, 1000))
    qtbot.addWidget(window)
    window.show()
    window._tab_registry.focus("watched")
    collection = window._tab_registry._specs["watched"].view
    assert [collection._action_candidates_by_key[entry[0]]["media_type"] for entry in collection._entries] == ["tv"]
    collection._switch_section("hidden")
    assert [collection._action_candidates_by_key[entry[0]]["media_type"] for entry in collection._entries] == ["movie"]
    next(button for button in collection.cards.findChildren(QPushButton) if button.text() == "Вернуть").click()
    assert not collection._entries
    assert get_title_state(movie) == "available"
    assert get_title_state(series) == "watchlist"
    window.shutdown_background_workers()
