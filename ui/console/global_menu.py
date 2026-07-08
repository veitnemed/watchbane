"""Thin console route facade for top-level menu sections."""

from ui.console import maintenance_menu
from ui.console import data_profiles_menu
from ui.console import dev_gui
from ui.console import pool_menu
from ui.console import reference_menu
from ui.console import search_hub_menu
from ui.console import watched_menu


def open_maintenance_menu() -> None:
    """Open maintenance-first console section."""
    maintenance_menu.open_maintenance_menu()


def open_watched_menu() -> None:
    """Open watched dataset section."""
    watched_menu.open_watched_menu()


def open_candidate_pool_menu() -> None:
    """Open candidate pool section."""
    pool_menu.open_candidate_pool_menu()


def open_search_menu() -> None:
    """Open read-only search section."""
    search_hub_menu.open_search_menu()


def open_reference_menu() -> None:
    """Open reference data section."""
    reference_menu.open_reference_menu()


def open_data_profiles_menu() -> None:
    """Open safe data profile management section."""
    data_profiles_menu.open_data_profiles_menu()


def open_dev_gui_empty_candidate_pool() -> None:
    """Launch GUI with dev startup cleanup for candidate pool testing."""
    return_code = dev_gui.launch_gui_with_empty_candidate_pool()
    if return_code != 0:
        print(f"GUI exited with code {return_code}.")


def open_data_menu() -> None:
    """Compatibility wrapper for the old watched data menu name."""
    watched_menu.open_watched_menu()


def open_extra_menu() -> None:
    """Compatibility wrapper for the old extra menu name."""
    maintenance_menu.open_maintenance_menu()


def open_genres_menu() -> None:
    """Compatibility wrapper for the old genres menu name."""
    reference_menu.open_reference_menu()


def open_tags_menu() -> None:
    """Compatibility wrapper for the old tags menu name."""
    reference_menu.open_tags_menu()


def open_candidate_pool_management_menu() -> None:
    """Compatibility wrapper for the old pool management submenu name."""
    pool_menu.open_candidate_pool_import_menu()


def open_candidate_pool_diagnostics_menu() -> None:
    """Compatibility wrapper for the old pool diagnostics submenu name."""
    pool_menu.open_candidate_pool_cleanup_menu()
