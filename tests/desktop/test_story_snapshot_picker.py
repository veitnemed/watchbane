import json
from pathlib import Path
from threading import Event, get_ident

import pytest
from PyQt6.QtCore import Qt

from desktop.story import view as story_ui


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    monkeypatch.delenv("WATCHBANE_STORY_SEED_CATALOG", raising=False)
    monkeypatch.delenv("WATCHBANE_STORY_MODEL_DIR", raising=False)


def open_view(qtbot):
    view = story_ui.StorySearchView()
    qtbot.addWidget(view.widget)
    view.widget.resize(1280, 900)
    view.widget.show()
    return view


def choose(monkeypatch, path):
    monkeypatch.setattr(story_ui.QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))


def click(qtbot, button):
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def write_snapshot(path, records):
    with path.open("w", encoding="utf-8") as out:
        for tmdb_id, title in records:
            out.write(json.dumps(dict(
                media_type="movie", tmdb_id=tmdb_id, title=title, overview="Врач лечит пациентов.",
                year=2020, language="ru-RU",
            ), ensure_ascii=False) + "\n")
    return path


def search(qtbot, view):
    view.query.setText("врач")
    click(qtbot, view.search_button)
    qtbot.waitUntil(lambda: view._worker is None)
    assert view.cards_layout.count() > 1


def test_local_snapshot_checked_off_thread_without_connecting_tmdb_or_building_index(qtbot, monkeypatch, tmp_path):
    from apis import tmdb_api
    from candidates import story_seed_snapshot, story_service
    from requests import Session

    path = write_snapshot(tmp_path / "каталог.jsonl", [(314, "Карточка из файла")])
    choose(monkeypatch, path)
    app_thread = get_ident()
    worker_threads = []
    original_loader = story_seed_snapshot.load_seed_snapshot
    started = Event()

    def loader(filename):
        worker_threads.append(get_ident())
        started.set()
        return original_loader(filename)

    def forbidden(*args, **kwargs):
        raise AssertionError("Choosing a file must not connect or load/build an index")

    view = open_view(qtbot)
    with monkeypatch.context() as scope:
        scope.setattr(story_seed_snapshot, "load_seed_snapshot", loader)
        scope.setattr(story_service, "create_story_search", forbidden)
        scope.setattr(tmdb_api, "has_tmdb_credentials", forbidden)
        scope.setattr(Session, "request", forbidden)
        click(qtbot, view.snapshot_button)
        qtbot.waitUntil(started.is_set)
        qtbot.waitUntil(lambda: view._snapshot_worker is None)
    assert worker_threads and all(thread != app_thread for thread in worker_threads)
    assert view.seed_path == str(path)
    assert view._snapshot_rows == 1 and view._worker is None
    assert "Только каталог из файла" in view.catalog_status.text()
    assert not view.catalog_button.isVisible()
    search(qtbot, view)
    assert set(view._records) == {"tmdb:movie:314"}
    assert not open_view(qtbot).seed_path  # session/view only


def test_cancel_invalid_and_repeated_selection_preserve_or_replace_only_on_success(qtbot, monkeypatch, tmp_path):
    from candidates import story_service

    monkeypatch.setattr(story_service, "get_pool_view", lambda: [{
        "title": "Карточка профиля", "tmdb_id": 711, "media_type": "movie", "overview": "Врач лечит пациентов."
    }])
    view = open_view(qtbot)
    search(qtbot, view)
    old_records = view._records
    old_card = view.cards_layout.itemAt(0).widget()
    choose(monkeypatch, "")
    click(qtbot, view.snapshot_button)
    assert view._records is old_records and view.cards_layout.itemAt(0).widget() is old_card

    invalid = tmp_path / "wrong.jsonl"
    invalid.write_text("{}\n", encoding="utf-8")
    choose(monkeypatch, invalid)
    click(qtbot, view.snapshot_button)
    qtbot.waitUntil(lambda: view._snapshot_worker is None)
    assert "Некорректная" in view.catalog_status.text()
    assert not view.seed_path and view._records is old_records and view.cards_layout.itemAt(0).widget() is old_card

    snapshot = write_snapshot(tmp_path / "catalogue.jsonl", [(314, "Карточка из файла")])
    choose(monkeypatch, snapshot)
    click(qtbot, view.snapshot_button)
    qtbot.waitUntil(lambda: view._snapshot_worker is None)
    assert view.query.text() == "врач" and view.cards_layout.count() == 1
    search(qtbot, view)
    assert set(view._records) == {"tmdb:movie:314"}

    replacement_action, clear_action = view.snapshot_menu.actions()
    choose(monkeypatch, invalid)
    replacement_action.trigger()
    qtbot.waitUntil(lambda: view._snapshot_worker is None)
    assert view.seed_path == str(snapshot) and set(view._records) == {"tmdb:movie:314"}
    assert view.cards_layout.count() == 2

    # A rewritten file can have the same path and record count. Old cards must
    # not look like they came from the newly selected contents.
    write_snapshot(snapshot, [(315, "Другая карточка из файла")])
    choose(monkeypatch, snapshot)
    replacement_action.trigger()
    qtbot.waitUntil(lambda: view._snapshot_worker is None)
    assert view.seed_path == str(snapshot) and view.cards_layout.count() == 1
    search(qtbot, view)
    assert set(view._records) == {"tmdb:movie:315"}

    clear_action.trigger()
    assert view.seed_path is None and view.catalog_button.isVisible() and view.query.text() == "врач"
    assert view.cards_layout.count() == 1 and view.snapshot_button.menu() is None
    search(qtbot, view)
    assert view._records == old_records


def test_inflight_validation_cancellation_never_switches_active_source(qtbot, monkeypatch, tmp_path):
    from candidates import story_seed_snapshot

    old = write_snapshot(tmp_path / "old.jsonl", [(800, "Старый каталог")])
    future = write_snapshot(tmp_path / "future.jsonl", [(900, "Новый каталог")])
    monkeypatch.setenv("WATCHBANE_STORY_SEED_CATALOG", str(old))
    view = open_view(qtbot)
    search(qtbot, view)
    old_records = view._records
    entered = Event()
    release = Event()
    original = story_seed_snapshot.load_seed_snapshot

    def loader(path):
        entered.set()
        assert release.wait(5)
        return original(Path(path))

    monkeypatch.setattr(story_seed_snapshot, "load_seed_snapshot", loader)
    choose(monkeypatch, future)
    view.snapshot_menu.actions()[0].trigger()
    try:
        qtbot.waitUntil(entered.is_set)
        assert view.seed_path == str(old)
        assert not view.search_button.isEnabled()
        assert not view.snapshot_button.isEnabled() and view.cancel_catalog_button.isVisible()
        click(qtbot, view.cancel_catalog_button)
    finally:
        release.set()
    qtbot.waitUntil(lambda: view._snapshot_worker is None)
    assert "Проверка отменена" in view.catalog_status.text()
    assert view.seed_path == str(old) and view._records is old_records
    assert view.search_button.isEnabled() and view.snapshot_button.isEnabled()


def test_file_with_zero_eligible_rows_retries_after_same_path_replacement(qtbot, monkeypatch, tmp_path):
    from candidates.story_seed_snapshot import load_seed_snapshot
    from candidates.title_state_service import mark_watched

    snapshot = write_snapshot(tmp_path / "active.jsonl", [(314, "Просмотрено")])
    mark_watched(load_seed_snapshot(snapshot)["tmdb:movie:314"])
    choose(monkeypatch, snapshot)
    view = open_view(qtbot)
    click(qtbot, view.snapshot_button)
    qtbot.waitUntil(lambda: view._snapshot_worker is None)
    view.query.setText("врач")
    click(qtbot, view.search_button)
    qtbot.waitUntil(lambda: view._worker is None)
    assert view._records == {} and "доступно: 0" in view.catalog_status.text()
    assert view._catalog_ready and "нет доступных описаний" in view.status.text()

    replacement = write_snapshot(tmp_path / "new.jsonl", [(315, "Не просмотрено")])
    replacement.replace(snapshot)
    search(qtbot, view)
    assert set(view._records) == {"tmdb:movie:315"} and "доступно: 1" in view.catalog_status.text()

    snapshot.unlink()
    click(qtbot, view.search_button)
    qtbot.waitUntil(lambda: view._worker is None)
    assert "недоступен или повреждён" in view.status.text()
    assert "доступно: 0" not in view.catalog_status.text()
    assert view.snapshot_button.menu() is view.snapshot_menu and view.snapshot_button.isEnabled()
