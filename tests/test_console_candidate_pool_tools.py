import inspect

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


def test_candidate_pool_tools_keep_interface_compatibility() -> None:
    assert interface_funcs.collect_candidate_pool is candidate_pool_tools.collect_candidate_pool
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
    assert "candidate_pool_tools.collect_candidate_pool" in import_source
    assert "candidate_pool_tools.clean_common_pool_duplicates" in cleanup_source
    assert "candidate_pool_tools.show_candidate_poster_diagnostics" in cleanup_source
    assert "candidate_pool_tools.show_title_candidate_duplicates" in cleanup_source


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


def test_global_menu_is_maintenance_first() -> None:
    menu_source = inspect.getsource(ui.show_global_menu)
    pool_screen_source = inspect.getsource(ui.show_candidate_pool_menu)

    assert "1 >> Обслуживание" in menu_source
    assert "2 >> Просмотренное" in menu_source
    assert "3 >> Candidate pool" in menu_source
    assert "1 >> Собрать TMDb pool" not in pool_screen_source
    assert "5 >> Импорт / сбор pool" in pool_screen_source
