from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton,QLabel
from desktop.story.view import StorySearchView


def test_keyboard_examples_compact_results_and_secondary_controls(qtbot, monkeypatch):
    from candidates import story_service
    monkeypatch.setattr(story_service, "get_pool_view", lambda: [{
        "title": "Fixture", "tmdb_id": 155, "media_type": "movie",
        "overview": "Узник планирует побег из тюрьмы и готовит подкоп.",
    }])
    view=StorySearchView();qtbot.addWidget(view.widget);view.widget.resize(1280,1000);view.widget.show();view.widget.activateWindow()
    assert not view.options.isVisible() and view.examples.isVisible() and view.catalog_button.isVisible()
    qtbot.waitUntil(view.widget.isActiveWindow)
    view.query.setFocus();qtbot.keyClick(view.query,Qt.Key.Key_Tab)
    assert view.search_button.hasFocus()
    sample=view.examples.findChildren(QPushButton)[0];sample.setFocus();qtbot.keyClick(sample,Qt.Key.Key_Space)
    qtbot.waitUntil(lambda:view._worker is None)
    assert view.query.text()=='побег из тюрьмы'
    assert not view.heading.isVisible() and not view.examples.isVisible()
    assert view.cards_layout.count()>1
    first=view.cards_layout.itemAt(0).widget()
    assert first.mapTo(view.widget,first.rect().topLeft()).y()<320
    more=next(b for b in first.findChildren(QPushButton) if b.text()=='Полный сюжет')
    more.setFocus();qtbot.keyClick(more,Qt.Key.Key_Space);assert more.isChecked()
    qtbot.keyClick(view.widget,Qt.Key.Key_L,Qt.KeyboardModifier.ControlModifier)
    assert view.query.hasFocus() and view.query.selectedText()==view.query.text()
    assert not view.options.isVisible()
    qtbot.keyClick(view.widget,Qt.Key.Key_Escape)
    assert not view.options.isVisible() and view.query.hasFocus()
    view.query.setText('без убийств');qtbot.keyClick(view.query,Qt.Key.Key_Return)
    qtbot.waitUntil(lambda:view._worker is None)
    assert 'Отрицания' in view.status.text() and view.cards_layout.count()==1
    view.query.clear();qtbot.keyClick(view.query,Qt.Key.Key_Return)
    qtbot.waitUntil(lambda:view._worker is None)
    assert view.heading.isVisible() and view.examples.isVisible()


def test_old_collection_and_settings_remain_reachable(qtbot):
    from desktop.shell.main_window import WatchedMoviesWindow
    window=WatchedMoviesWindow(initial_size=(1280,1000));qtbot.addWidget(window);window.show()
    registry=window._tab_registry;tabs=window._main_tabs
    assert not tabs.isTabVisible(tabs.indexOf(registry._specs['settings'].view.widget))
    assert not tabs.isTabVisible(tabs.indexOf(registry._specs['filters'].view.widget))
    registry.focus('watched');assert tabs.currentWidget() is registry._specs['watched'].view.widget
    registry.focus('story');view=registry._specs['story'].view
    assert tabs.count()==2
    assert [tabs.tabText(i) for i in range(tabs.count())]==['Поиск','Коллекция']
    registry.focus('settings');registry.focus('filters');registry.focus('candidates')
    assert tabs.currentWidget() is registry._specs['story'].view.widget
    window.shutdown_background_workers()


def test_poster_is_existing_local_image_or_network_free_placeholder(qtbot,tmp_path,monkeypatch):
    import requests
    from PyQt6.QtGui import QImage,QColor
    from candidates.story_search import StoryDocument
    from desktop.candidates import presenters
    monkeypatch.setattr(requests.Session,'request',lambda *a,**k: (_ for _ in ()).throw(AssertionError('No network')))
    view=StorySearchView();qtbot.addWidget(view.widget)
    doc=StoryDocument('x','Original fixture','Story','movie','synthetic')
    view._records={'x':{'title':'Original fixture'}}
    path=tmp_path/'poster.png';picture=QImage(40,80,QImage.Format.Format_RGB32);picture.fill(QColor('#426b82'));picture.save(str(path))
    monkeypatch.setattr(presenters,'resolve_local_poster_path_for_candidate',lambda _:str(path))
    poster=view._poster(doc);qtbot.addWidget(poster)
    assert poster.pixmap() is not None and not poster.pixmap().isNull()
    monkeypatch.setattr(presenters,'resolve_local_poster_path_for_candidate',lambda _:'https://example.invalid/poster.png')
    placeholder=view._poster(doc);qtbot.addWidget(placeholder)
    assert 'Без постера' in placeholder.text()


def test_model_error_visible_and_controls_recover(qtbot,monkeypatch):
    from candidates import story_service
    monkeypatch.setattr(story_service, "get_pool_view", lambda: [{
        "title": "Fixture", "tmdb_id": 166, "media_type": "movie", "overview": "Врач лечит пациентов."
    }])
    monkeypatch.setattr(story_service,'create_story_search',lambda *a,**k: (_ for _ in ()).throw(ValueError('invalid model')))
    view=StorySearchView();qtbot.addWidget(view.widget);view.widget.show()
    view.query.setText('врач');view.search();qtbot.waitUntil(lambda:view._worker is None)
    assert 'Не удалось' in view.status.text() and view.query.isEnabled()
    assert not view.options.isVisible() and view.model_button.isEnabled()


def test_bad_model_can_retry_same_query_in_word_mode(qtbot, monkeypatch, tmp_path):
    from candidates import story_service
    monkeypatch.setenv("WATCHBANE_STORY_MODEL_DIR", str(tmp_path / "absent-model"))
    monkeypatch.setattr(story_service, "get_pool_view", lambda: [{
        "title": "Fixture", "tmdb_id": 177, "media_type": "movie", "overview": "Врач лечит пациентов."
    }])
    view = StorySearchView()
    qtbot.addWidget(view.widget)
    view.widget.show()
    view.query.setText("врач")
    view.search()
    qtbot.waitUntil(lambda: view._worker is None)
    assert view.text_search_button.isVisible() and view.cards_layout.count() == 1
    qtbot.mouseClick(view.text_search_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: view._worker is None)
    assert view.query.text() == "врач" and view.cards_layout.count() == 2
    assert "Поиск по словам" in view.scope.text() and not view.text_search_button.isVisible()
