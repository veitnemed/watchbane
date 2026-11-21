import json

import pytest

from candidates.story_seed_snapshot import load_seed_snapshot, StorySeedSnapshotError
from candidates import story_service


def record(**kwargs):
    return dict(dict(media_type="movie", tmdb_id=321, title="Проверочная история",
                     overview="Врач помогает пациентам в больнице.", year=2020, language="ru-RU"), **kwargs)


def snapshot(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                    encoding="utf-8")
    return path


def test_seed_is_read_without_touching_common_pool(tmp_path, monkeypatch):
    def no_pool():
        raise AssertionError("Seed is independent of candidate pool")
    monkeypatch.setattr(story_service, "get_pool_view", no_pool)
    path = snapshot(tmp_path / "seed.jsonl", [record(poster_path="/x.jpg"),
        record(media_type="tv", language="en-US", overview="A doctor treats a patient.",
               poster_path="//other.example/image.jpg")])
    engine, records = story_service.local_story_catalog(seed_path=path)
    assert set(records) == {"tmdb:movie:321", "tmdb:tv:321"}
    assert records["tmdb:movie:321"]["poster_url"] == "https://image.tmdb.org/t/p/w342/x.jpg"
    assert "poster_url" not in records["tmdb:tv:321"]
    assert "английский" in next(d.source for d in engine.documents if d.media_type == "tv")
    assert engine.search("врач").hits[0].document.key == "tmdb:movie:321"


def test_seed_follows_existing_watchlist_visibility(tmp_path):
    from candidates import service
    from candidates.title_state_service import get_title_state
    path = snapshot(tmp_path / "seed.jsonl", [record()])
    _, records = story_service.story_catalog_snapshot(seed_path=path)
    row = records["tmdb:movie:321"]
    service.add_candidate_to_watchlist(row)
    assert get_title_state(row) == "watchlist"
    assert len(story_service.story_catalog_snapshot(seed_path=path)[0]) == 1
    service.hide_candidate(row)
    assert story_service.story_catalog_snapshot(seed_path=path)[0] == []


def test_seed_rejects_duplicates_and_refreshes_on_replace(tmp_path):
    path = snapshot(tmp_path / "seed.jsonl", [record(), record()])
    with pytest.raises(StorySeedSnapshotError, match="строка 2"):
        load_seed_snapshot(path)
    snapshot(path, [record()])
    assert set(load_seed_snapshot(path)) == {"tmdb:movie:321"}
    snapshot(tmp_path / "new.jsonl", [record(tmdb_id=678)]).replace(path)
    assert set(load_seed_snapshot(path)) == {"tmdb:movie:678"}


def test_seed_preview_search_and_save_without_import(qtbot, tmp_path, monkeypatch):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QPushButton
    from candidates.pool_service import get_pool_view
    from candidates.title_state_service import get_title_state
    from desktop.story.view import StorySearchView

    path = snapshot(tmp_path / "seed.jsonl", [record()])
    monkeypatch.setenv("WATCHBANE_STORY_SEED_CATALOG", str(path))
    view = StorySearchView()
    qtbot.addWidget(view.widget)
    view.widget.resize(1050, 800)
    view.widget.show()
    assert not view.catalog_button.isVisible()
    assert view.catalog_status.text() == "Только каталог из файла"
    view.query.setText("врач")
    qtbot.keyClick(view.query, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: view._worker is None)
    assert view.catalog_status.text() == "Только каталог из файла · доступно: 1"
    button = next(b for b in view.cards.findChildren(QPushButton) if b.text() == "Сохранить")
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert button.text() == "В коллекции"
    assert get_title_state(view._records["tmdb:movie:321"]) == "watchlist"
    assert get_pool_view() == []


def test_preview_check_validates_environment_catalog_without_import(tmp_path, monkeypatch, capsys):
    import sys
    import preview

    path = snapshot(tmp_path / "seed.jsonl", [record()])
    profile = tmp_path / "preview-profile"
    monkeypatch.setenv("WATCHBANE_STORY_SEED_CATALOG", str(path))
    monkeypatch.delenv("WATCHBANE_STORY_MODEL_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", ["preview.py", "--profile", str(profile), "--check"])
    # Register the env keys written by the entry point for restoration.
    for name in ("WATCHBANE_DATA_DIR", "WATCHBANE_INTERFACE_LANGUAGE", "WATCHBANE_DATA_LANGUAGE"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv(name, "")
    preview.main()
    assert "Validated catalogue: 1" in capsys.readouterr().out
    assert not profile.exists()


def test_publisher_sidecar_resolution_priority_and_frozen_install(tmp_path, monkeypatch):
    import sys
    from candidates.story_seed_snapshot import PUBLISHER_CATALOG, resolve_catalog

    source = tmp_path / "source"
    source.mkdir()
    launcher = source / "preview.py"
    assert resolve_catalog(launcher) is None
    assert resolve_catalog(launcher, environment_path="  ") is None
    sidecar = source / PUBLISHER_CATALOG
    sidecar.parent.mkdir()
    snapshot(sidecar, [record()])
    assert resolve_catalog(launcher) == sidecar
    # An explicit but nonexistent override fails existing validation instead of
    # hiding a user error by silently selecting the publisher's data.
    override = tmp_path / "missing.jsonl"
    assert resolve_catalog(launcher, environment_path=str(override)) == override
    assert resolve_catalog(launcher, sidecar, str(override)) == sidecar

    install = tmp_path / "Install"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(install / "Watchbane.exe"))
    assert resolve_catalog(launcher) is None
    installed = install / PUBLISHER_CATALOG
    installed.parent.mkdir(parents=True)
    snapshot(installed, [record()])
    assert resolve_catalog(launcher) == installed


def test_preview_check_validates_installed_sidecar(tmp_path, monkeypatch, capsys):
    import sys
    import preview
    from candidates.story_seed_snapshot import PUBLISHER_CATALOG

    path = tmp_path / PUBLISHER_CATALOG
    path.parent.mkdir()
    snapshot(path, [record()])
    monkeypatch.setattr(preview, "__file__", str(tmp_path / "preview.py"))
    monkeypatch.delenv("WATCHBANE_STORY_SEED_CATALOG", raising=False)
    monkeypatch.delenv("WATCHBANE_STORY_MODEL_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", ["preview.py", "--check"])
    for name in ("WATCHBANE_DATA_DIR", "WATCHBANE_INTERFACE_LANGUAGE", "WATCHBANE_DATA_LANGUAGE"):
        monkeypatch.setenv(name, "")
    preview.main()
    assert "Validated catalogue: 1" in capsys.readouterr().out
    assert not (tmp_path / ".preview-profile").exists()
    path.write_text("not JSON\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="2"):
        preview.main()
    assert "строка 1" in capsys.readouterr().err


def test_seed_observes_same_length_rewrite_even_when_mtime_is_preserved(tmp_path, monkeypatch):
    import os
    from candidates import story_seed_snapshot as seed
    original_identity = seed._identity
    monkeypatch.setattr(seed, "_identity", lambda info: original_identity(info)[:4])


    path = snapshot(tmp_path / "seed.jsonl", [record()])
    assert set(load_seed_snapshot(path)) == {"tmdb:movie:321"}
    before = path.stat()
    snapshot(path, [record(tmdb_id=678)])
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = path.stat()
    assert (after.st_ino, after.st_size, after.st_mtime_ns) == (
        before.st_ino, before.st_size, before.st_mtime_ns,
    )
    assert set(load_seed_snapshot(path)) == {"tmdb:movie:678"}


def test_seed_accepts_stable_descriptor_metadata_that_differs_from_path_stat(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from candidates import story_seed_snapshot as seed

    path = snapshot(tmp_path / "seed.jsonl", [record()])
    real_fstat = seed.os.fstat

    def windows_style_fstat(fd):
        info = real_fstat(fd)
        return SimpleNamespace(st_dev=info.st_dev + 1, st_ino=info.st_ino + 1,
                               st_size=info.st_size, st_mode=info.st_mode,
                               st_mtime_ns=info.st_mtime_ns, st_ctime_ns=info.st_ctime_ns)

    with monkeypatch.context() as patched:
        patched.setattr(seed.os, "fstat", windows_style_fstat)
        assert set(load_seed_snapshot(path)) == {"tmdb:movie:321"}
