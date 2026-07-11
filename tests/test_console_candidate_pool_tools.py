import inspect
from pathlib import Path

from ui.console import candidate_pool_tools
from ui.console import interface_funcs
from ui.console import pool_menu
from ui.console import tmdb_pool_tools
from ui.console import ui


def test_global_menu_prints_candidate_summary(capsys) -> None:
    ui.show_global_menu(
        7,
        candidate_summary={
            "line": "Candidate pool: 3 | complete: 2 | posters: 1 | need posters: 1",
        },
    )

    output = capsys.readouterr().out

    assert "Candidate pool: 3 | complete: 2 | posters: 1 | need posters: 1" in output
    assert "3 >> Candidate pool" in output
    assert "7 >> Dev GUI: empty candidate pool on startup" in output


def test_console_dev_gui_launcher_sets_candidate_clear_env(monkeypatch) -> None:
    from storage import runtime
    from ui.console import dev_gui

    captured = {}

    class Result:
        returncode = 0

    def fake_run(command, cwd=None, env=None, check=None):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["check"] = check
        return Result()

    monkeypatch.setenv(runtime.DEV_EMPTY_PROFILE_ENV, "1")
    monkeypatch.setattr(
        dev_gui,
        "prepare_empty_candidate_pool_runtime",
        lambda: Path("tmp/dev_gui/empty_candidate_pool"),
    )
    monkeypatch.setattr(dev_gui.subprocess, "run", fake_run)

    return_code = dev_gui.launch_gui_with_empty_candidate_pool()

    assert return_code == 0
    assert captured["command"][-1] == "start_app.py"
    assert captured["cwd"].name == "watchbane"
    assert captured["check"] is False
    assert captured["env"]["WATCHBANE_DATA_DIR"] == str(Path("tmp/dev_gui/empty_candidate_pool"))
    assert captured["env"][runtime.DEV_CLEAR_CANDIDATES_ENV] == "1"
    assert runtime.DEV_EMPTY_PROFILE_ENV not in captured["env"]


def test_console_dev_gui_prepares_isolated_runtime(monkeypatch, tmp_path) -> None:
    from ui.console import dev_gui

    repo_root = tmp_path / "repo"
    source_data = tmp_path / "source-data"
    (source_data / "watched").mkdir(parents=True)
    (source_data / "cache").mkdir()
    (source_data / "logs").mkdir()
    (source_data / "backups").mkdir()
    (source_data / "watched" / "titles.json").write_text("[]", encoding="utf-8")
    (source_data / "cache" / "large.bin").write_text("cache", encoding="utf-8")
    (source_data / "logs" / "session.log").write_text("log", encoding="utf-8")
    (source_data / "backups" / "copy.zip").write_text("backup", encoding="utf-8")

    monkeypatch.setattr(dev_gui, "_repo_root", lambda: repo_root)
    monkeypatch.setattr(
        dev_gui.profiles,
        "describe_active_profile",
        lambda: {"data_dir": source_data},
    )

    runtime_root = dev_gui.prepare_empty_candidate_pool_runtime()

    assert runtime_root == repo_root / "tmp" / "dev_gui" / "empty_candidate_pool"
    assert (runtime_root / "data" / "watched" / "titles.json").read_text(encoding="utf-8") == "[]"
    assert (runtime_root / "data" / "cache").exists() is False
    assert (runtime_root / "data" / "logs").exists() is False
    assert (runtime_root / "data" / "backups").exists() is False


def test_console_app_routes_dev_gui_command(monkeypatch) -> None:
    from ui.console import console_app

    commands = iter(["7", "0"])
    calls = {"dev_gui": 0, "press_enter": 0}

    monkeypatch.setattr(console_app.storage_files, "init_all_dates", lambda: None)
    monkeypatch.setattr(console_app.ui, "clean_terminal", lambda: None)
    monkeypatch.setattr(console_app.menu_state, "get_menu_state", lambda: ({}, 0))
    monkeypatch.setattr(console_app.menu_state, "get_candidate_summary_view", lambda: "")
    monkeypatch.setattr(console_app.menu_state, "get_profile_summary_line", lambda: "")
    monkeypatch.setattr(console_app.ui, "show_global_menu", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(console_app.request, "loop_input", lambda **_kwargs: next(commands))

    def fake_launch() -> None:
        calls["dev_gui"] += 1

    def fake_press_enter() -> None:
        calls["press_enter"] += 1

    monkeypatch.setattr(console_app.global_menu, "open_dev_gui_empty_candidate_pool", fake_launch)
    monkeypatch.setattr(console_app.ui, "press_enter", fake_press_enter)

    console_app.run_console_app()

    assert calls == {"dev_gui": 1, "press_enter": 1}


def test_candidate_pool_tools_keep_interface_compatibility() -> None:
    assert interface_funcs.show_candidate_pool is candidate_pool_tools.show_candidate_pool
    assert interface_funcs.clean_common_pool_duplicates is candidate_pool_tools.clean_common_pool_duplicates
    assert interface_funcs.purge_pool_dataset_title_matches is candidate_pool_tools.purge_pool_dataset_title_matches
    assert (
        interface_funcs.download_candidate_pool_preview_posters
        is candidate_pool_tools.download_candidate_pool_preview_posters
    )


def test_candidate_pool_menus_route_to_scenario_module() -> None:
    pool_menu_source = inspect.getsource(pool_menu.open_candidate_pool_menu)
    import_source = inspect.getsource(pool_menu.open_candidate_pool_import_menu)
    cleanup_source = inspect.getsource(pool_menu.open_candidate_pool_cleanup_menu)

    assert "candidate_pool_tools.show_candidate_pool" in pool_menu_source
    assert "tmdb_pool_tools.run_tmdb_candidate_pool_flow" in import_source
    assert "candidate_pool_tools.collect_candidate_pool" not in import_source
    assert "candidate_pool_tools.clean_common_pool_duplicates" in cleanup_source
    assert "candidate_pool_tools.show_candidate_poster_diagnostics" in cleanup_source
    assert "candidate_pool_tools.start_candidate_pool_preview_poster_job" in cleanup_source
    assert "candidate_pool_tools.show_candidate_pool_preview_poster_job_status" in cleanup_source
    assert "candidate_pool_tools.show_candidate_pool_preview_poster_job_log" in cleanup_source
    assert "candidate_pool_tools.stop_candidate_pool_preview_poster_job" in cleanup_source
    assert "candidate_pool_tools.show_title_candidate_duplicates" in cleanup_source


def test_candidate_pool_menu_shows_background_poster_actions(capsys) -> None:
    ui.show_candidate_pool_cleanup_menu()

    output = capsys.readouterr().out

    assert "8 >> Запустить фоновую загрузку preview-постеров" in output
    assert "9 >> Статус фоновой загрузки preview-постеров" in output
    assert "10 >> Лог фоновой загрузки preview-постеров" in output
    assert "11 >> Остановить фоновую загрузку preview-постеров" in output


def test_candidate_pool_tool_starts_background_poster_job(monkeypatch, capsys) -> None:
    from posters import download_job

    monkeypatch.setattr(candidate_pool_tools.ui, "clean_terminal", lambda: None)
    monkeypatch.setattr(
        download_job,
        "start_job",
        lambda job_name: {"ok": True, "job_name": job_name, "pid": 123},
    )

    candidate_pool_tools.start_candidate_pool_preview_poster_job()

    output = capsys.readouterr().out
    assert "Загрузка запущена в фоне." in output
    assert "PID: 123" in output


def test_candidate_pool_cleanup_menu_handles_keyboard_interrupt(monkeypatch, capsys) -> None:
    commands = iter(["8", "0"])

    monkeypatch.setattr(pool_menu.ui, "clean_terminal", lambda: None)
    monkeypatch.setattr(pool_menu.ui, "show_candidate_pool_cleanup_menu", lambda: None)
    monkeypatch.setattr(pool_menu.ui, "press_enter", lambda: None)
    monkeypatch.setattr(pool_menu.request, "loop_input", lambda **_kwargs: next(commands))
    monkeypatch.setattr(
        candidate_pool_tools,
        "start_candidate_pool_preview_poster_job",
        lambda: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    pool_menu.open_candidate_pool_cleanup_menu()

    output = capsys.readouterr().out
    assert "Действие прервано. Возвращаюсь в меню." in output


def test_candidate_pool_cleanup_menu_handles_keyboard_interrupt_on_press_enter(monkeypatch, capsys) -> None:
    commands = iter(["9", "0"])
    press_calls = {"count": 0}

    def press_enter_once() -> None:
        press_calls["count"] += 1
        if press_calls["count"] == 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(pool_menu.ui, "clean_terminal", lambda: None)
    monkeypatch.setattr(pool_menu.ui, "show_candidate_pool_cleanup_menu", lambda: None)
    monkeypatch.setattr(pool_menu.ui, "press_enter", press_enter_once)
    monkeypatch.setattr(pool_menu.request, "loop_input", lambda **_kwargs: next(commands))
    monkeypatch.setattr(candidate_pool_tools, "show_candidate_pool_preview_poster_job_status", lambda: None)

    pool_menu.open_candidate_pool_cleanup_menu()

    output = capsys.readouterr().out
    assert "Возвращаюсь в меню." in output


def test_tmdb_pool_tools_keep_interface_compatibility() -> None:
    assert interface_funcs.run_tmdb_candidate_pool_flow is tmdb_pool_tools.run_tmdb_candidate_pool_flow
    assert (
        interface_funcs.import_tmdb_result_to_common_pool_flow
        is tmdb_pool_tools.import_tmdb_result_to_common_pool_flow
    )
    assert (
        interface_funcs.show_tmdb_dataset_genre_diagnostics
        is tmdb_pool_tools.show_tmdb_dataset_genre_diagnostics
    )
    assert interface_funcs.request_tmdb_country_codes is tmdb_pool_tools.request_tmdb_country_codes
    assert (
        interface_funcs.request_tmdb_discover_genre_filters
        is tmdb_pool_tools.request_tmdb_discover_genre_filters
    )


def test_tmdb_pool_menus_route_to_scenario_module() -> None:
    import_source = inspect.getsource(pool_menu.open_candidate_pool_import_menu)
    cleanup_source = inspect.getsource(pool_menu.open_candidate_pool_cleanup_menu)

    assert "tmdb_pool_tools.run_tmdb_candidate_pool_flow" in import_source
    assert "tmdb_pool_tools.import_tmdb_result_to_common_pool_flow" in import_source
    assert "tmdb_pool_tools.show_tmdb_dataset_genre_diagnostics" not in cleanup_source


def test_tmdb_flow_passes_tmdb_only_build_kwargs(monkeypatch, capsys) -> None:
    answers = iter([
        "1",
        "1",
        "1",
        "1",
        "1",
        "",
        "",
        "",
        "",
        "",
        "",
        "y",
    ])
    build_kwargs = {}

    def fake_build(**kwargs):
        build_kwargs.update(kwargs)
        return {
            "stats": {
                "source": "tmdb",
                "source_version": 2,
                "discover_total": 0,
                "duplicates_removed": 0,
                "watched_skipped": 0,
                "details_requested": 0,
            },
            "candidates": [],
        }

    monkeypatch.setattr(tmdb_pool_tools.ui, "clean_terminal", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(tmdb_pool_tools.candidate_service, "build_tmdb_candidate_pool", fake_build)
    monkeypatch.setattr(
        tmdb_pool_tools.candidate_service,
        "save_tmdb_build_result",
        lambda _result, is_test_run=False: {
            "json_path": type("P", (), {"with_name": lambda self, _name: self, "is_file": lambda self: False})(),
            "csv_path": "out.csv",
        },
    )
    monkeypatch.setattr(tmdb_pool_tools, "maybe_auto_import_tmdb_result", lambda *_args, **_kwargs: None)

    tmdb_pool_tools.run_tmdb_candidate_pool_flow()

    assert build_kwargs["country"] == "RU"
    assert build_kwargs["media_type"] == "tv"
    assert build_kwargs["pages"] == 1
    assert build_kwargs["details_limit"] == 1
    assert "enrichment_mode" not in build_kwargs
    assert "kp_top_limit" not in build_kwargs
    output = capsys.readouterr().out
    assert "TMDb-only candidate_pool v2" in output


def test_tmdb_flow_passes_movie_media_type(monkeypatch, capsys) -> None:
    answers = iter([
        "2",
        "1",
        "1",
        "1",
        "1",
        "",
        "",
        "",
        "",
        "",
        "",
        "y",
    ])
    build_kwargs = {}

    def fake_build(**kwargs):
        build_kwargs.update(kwargs)
        return {
            "media_type": "movie",
            "settings": {"media_type": "movie"},
            "stats": {
                "source": "tmdb",
                "source_version": 2,
                "discover_total": 0,
                "duplicates_removed": 0,
                "watched_skipped": 0,
                "details_requested": 0,
            },
            "candidates": [],
        }

    monkeypatch.setattr(tmdb_pool_tools.ui, "clean_terminal", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(tmdb_pool_tools.candidate_service, "build_tmdb_candidate_pool", fake_build)
    monkeypatch.setattr(
        tmdb_pool_tools.candidate_service,
        "save_tmdb_build_result",
        lambda _result, is_test_run=False: {
            "json_path": type("P", (), {"with_name": lambda self, _name: self, "is_file": lambda self: False})(),
            "csv_path": "out.csv",
        },
    )
    monkeypatch.setattr(tmdb_pool_tools, "maybe_auto_import_tmdb_result", lambda *_args, **_kwargs: None)

    tmdb_pool_tools.run_tmdb_candidate_pool_flow()

    assert build_kwargs["media_type"] == "movie"
    output = capsys.readouterr().out
    assert "Тип: фильмы" in output


def test_global_menu_is_maintenance_first() -> None:
    menu_source = inspect.getsource(ui.show_global_menu)
    pool_screen_source = inspect.getsource(ui.show_candidate_pool_menu)

    assert "1 >> Обслуживание" in menu_source
    assert "2 >> Просмотренное" in menu_source
    assert "3 >> Candidate pool" in menu_source
    assert "1 >> Собрать TMDb pool" not in pool_screen_source
    assert "5 >> Импорт / сбор pool" in pool_screen_source
