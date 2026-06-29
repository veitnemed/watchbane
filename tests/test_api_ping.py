import inspect

from apis import tmdb_api
from ui.console import global_menu
from ui.console import interface_funcs
from ui.console import ui


def test_tmdb_check_api_available_ok(monkeypatch) -> None:
    monkeypatch.setattr(tmdb_api, "load_tmdb_token", lambda: "test-token")
    monkeypatch.setattr(tmdb_api, "tmdb_get", lambda path, token=None: {"images": {}})

    result = tmdb_api.check_api_available()

    assert result["ok"] is True
    assert result["data"] is True
    assert isinstance(result["elapsed_ms"], float)


def test_tmdb_check_api_available_missing_token(monkeypatch) -> None:
    monkeypatch.setattr(
        tmdb_api,
        "load_tmdb_token",
        lambda: (_ for _ in ()).throw(RuntimeError("TMDB_TOKEN не найден.")),
    )

    result = tmdb_api.check_api_available()

    assert result["ok"] is False
    assert result["error"] == "missing_token"
    assert "TMDB_TOKEN" in result["details"]


def test_ping_external_apis_prints_status(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "apis.kp_api.check_api_available",
        lambda: {"ok": True, "data": True},
    )
    monkeypatch.setattr(
        "apis.tmdb_api.check_api_available",
        lambda: {"ok": False, "error": "missing_token", "details": "TMDB_TOKEN не найден."},
    )

    interface_funcs.ping_external_apis()
    output = capsys.readouterr().out

    assert "Пинг внешних API" in output
    assert "Kinopoisk API" in output
    assert "TMDb API" in output
    assert "Статус: OK" in output
    assert "Статус: Ошибка" in output


def test_extra_menu_has_api_ping_item() -> None:
    menu_source = inspect.getsource(ui.show_extra_menu)
    handler_source = inspect.getsource(global_menu.open_extra_menu)
    func_source = inspect.getsource(interface_funcs.ping_external_apis)

    assert "9 >> Пинг API" in menu_source
    assert "ping_external_apis" in handler_source
    assert "Kinopoisk API" in func_source
    assert "TMDb API" in func_source
