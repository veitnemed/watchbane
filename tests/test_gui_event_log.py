import json

from diagnostics import gui_event_log


def test_gui_event_log_writes_jsonl(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui_event_log, "_SESSION_LOG_PATH", None)
    monkeypatch.setattr(gui_event_log, "_SESSION_ENABLED", False)

    path = gui_event_log.start_gui_event_log(tmp_path)
    gui_event_log.log_event("unit.event", value={"answer": 42})

    lines = path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]

    assert events[0]["event"] == "app.start"
    assert events[1]["event"] == "unit.event"
    assert events[1]["value"]["answer"] == 42


def test_gui_event_log_is_silent_until_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui_event_log, "_SESSION_LOG_PATH", None)
    monkeypatch.setattr(gui_event_log, "_SESSION_ENABLED", False)
    monkeypatch.delenv(gui_event_log.GUI_EVENT_LOG_ENV, raising=False)

    gui_event_log.log_event("unit.silent")
    assert list(tmp_path.iterdir()) == []
    assert gui_event_log.start_gui_event_log_if_enabled(tmp_path) is None

    monkeypatch.setenv(gui_event_log.GUI_EVENT_LOG_ENV, "1")
    path = gui_event_log.start_gui_event_log_if_enabled(tmp_path)
    assert path is not None
    assert path.exists()


def test_gui_event_log_redacts_tmdb_token_from_message_and_traceback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui_event_log, "_SESSION_LOG_PATH", None)
    monkeypatch.setattr(gui_event_log, "_SESSION_ENABLED", False)
    path = gui_event_log.start_gui_event_log(tmp_path)

    try:
        raise RuntimeError("authorization=Bearer-secret-token")
    except RuntimeError as error:
        gui_event_log.log_exception("tmdb.validation.failed", error, token="secret-token")

    raw = path.read_text(encoding="utf-8")
    assert "secret-token" not in raw
    assert "<redacted>" in raw

def test_add_title_dialogs_are_instrumented() -> None:
    import inspect

    import desktop.watched.add_title.flow as flow_module
    import desktop.watched.add_title.preview_dialog as preview_module
    import desktop.watched.add_title.search_dialog as search_module
    import desktop.watched.add_title.worker as worker_module

    assert "add_title.flow.open" in inspect.getsource(flow_module.run_add_title_flow)
    assert "add_title.search.start" in inspect.getsource(search_module.AddTitleSearchDialog._start_search)
    assert "add_title.worker.progress" in inspect.getsource(search_module.AddTitleSearchDialog._on_progress)
    assert "add_title.worker.run.error" in inspect.getsource(worker_module.AddTitleResolveWorker.run)
    assert "add_title.preview.confirm_clicked" in inspect.getsource(preview_module.AddTitlePreviewDialog._confirm_add)
