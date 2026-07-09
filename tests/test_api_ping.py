import inspect
from urllib.error import URLError

from apis import tmdb_api
from ui.console import interface_funcs
from ui.console import maintenance_menu
from ui.console import ui


def test_tmdb_check_api_available_ok(monkeypatch) -> None:
    monkeypatch.setattr(tmdb_api, "load_tmdb_credentials", lambda: ("bearer", "test-token"))
    monkeypatch.setattr(tmdb_api, "tmdb_get", lambda path, token=None: {"images": {}})

    result = tmdb_api.check_api_available()

    assert result["ok"] is True
    assert result["data"] is True
    assert isinstance(result["elapsed_ms"], float)


def test_tmdb_check_api_available_missing_token(monkeypatch) -> None:
    monkeypatch.setattr(
        tmdb_api,
        "load_tmdb_credentials",
        lambda: (_ for _ in ()).throw(RuntimeError("TMDb credentials not found.")),
    )

    result = tmdb_api.check_api_available()

    assert result["ok"] is False
    assert result["error"] == "missing_token"
    assert "TMDb credentials" in result["details"]


def test_tmdb_get_supports_api_key_query_auth(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.headers.get("Authorization")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(tmdb_api, "load_tmdb_credentials", lambda: ("api_key", "test-key"))
    monkeypatch.setattr(tmdb_api, "urlopen", fake_urlopen)

    result = tmdb_api.tmdb_get("/configuration", params={"language": "ru-RU"})

    assert result == {"ok": True}
    assert "api_key=test-key" in captured["url"]
    assert "language=ru-RU" in captured["url"]
    assert captured["authorization"] is None


def test_tmdb_get_retries_timeout_and_records_diagnostics(monkeypatch) -> None:
    calls = {"count": 0}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_opener(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise URLError(TimeoutError("timed out"))
        return FakeResponse()

    diagnostics = tmdb_api.TmdbRequestDiagnostics()
    monkeypatch.setattr(tmdb_api, "load_tmdb_credentials", lambda: ("bearer", "test-token"))

    result = tmdb_api.tmdb_get(
        "/configuration",
        opener=fake_opener,
        timeout=3,
        retries=1,
        diagnostics=diagnostics,
    )

    assert result == {"ok": True}
    assert calls["count"] == 2
    assert diagnostics.request_timeout_count == 1
    assert diagnostics.request_retry_count == 1


def test_tmdb_request_diagnostics_reports_outliers() -> None:
    diagnostics = tmdb_api.TmdbRequestDiagnostics(outlier_threshold_ms=100)

    diagnostics.record_request(25)
    diagnostics.record_request(125)
    diagnostics.record_retry()

    summary = diagnostics.as_dict()
    assert summary["request_outlier_count"] == 1
    assert summary["request_retry_count"] == 1
    assert summary["max_request_ms"] == 125
    assert summary["p95_request_ms"] == 125


def test_ping_external_apis_prints_status(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "apis.kp_api.check_api_available",
        lambda: {"ok": True, "data": True},
    )
    monkeypatch.setattr(
        "apis.tmdb_api.check_api_available",
        lambda: {"ok": False, "error": "missing_token", "details": "TMDb credentials not found."},
    )

    interface_funcs.ping_external_apis()
    output = capsys.readouterr().out

    assert "Пинг внешних API" in output
    assert "Kinopoisk API" in output
    assert "TMDb API" in output
    assert "Статус: OK" in output
    assert "Статус: Ошибка" in output


def test_maintenance_diagnostics_menu_has_api_ping_item() -> None:
    menu_source = inspect.getsource(ui.show_maintenance_diagnostics_menu)
    handler_source = inspect.getsource(maintenance_menu.open_maintenance_diagnostics_menu)
    func_source = inspect.getsource(interface_funcs.ping_external_apis)

    assert "1 >> Пинг API" in menu_source
    assert "ping_external_apis" in handler_source
    assert "Kinopoisk API" in func_source
    assert "TMDb API" in func_source
