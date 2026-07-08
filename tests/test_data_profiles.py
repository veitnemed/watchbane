import inspect
import sys
from pathlib import Path

import pytest

from config import constant
from storage import profiles


@pytest.fixture
def isolated_profiles(monkeypatch, tmp_path):
    constant_attrs = (
        "WATCHED_DIR",
        "CANDIDATES_DIR",
        "CACHE_DIR",
        "EXPORTS_DIR",
        "LOGS_DIR",
        "BACKUP_DIR",
        "DATA_DIR",
        "FILE_NAME",
        "CRITERIA_POOL_JSON",
        "CANDIDATE_POOL_JSON",
        "API_LOG_FILE",
        "DIR_META",
        "META_JSON",
        "DIR_TXT",
        "EDIT_EXCEL",
    )
    original_constants = {name: getattr(constant, name) for name in constant_attrs}
    module_attrs = []
    for module_name, attr_names in {
        "app.core.storage": ("WATCHLIST_JSON", "HIDDEN_JSON"),
        "posters.cache": (
            "DEFAULT_POSTER_CACHE_DIR",
            "DEFAULT_POSTER_CACHE_JSON",
            "DEFAULT_POSTER_IMAGES_DIR",
        ),
        "posters.download_images": ("DEFAULT_POSTER_IMAGES_DIR", "PREVIEW_POSTER_DIR"),
        "posters.download_job": ("DEFAULT_JOBS_DIR",),
        "posters.tmdb_overrides": ("DEFAULT_TMDB_CACHE_DIR", "DEFAULT_WATCHED_TMDB_OVERRIDES_JSON"),
        "apis.tmdb_api": ("TMDB_CACHE_DIR", "DISCOVER_CACHE_DIR", "DETAILS_CACHE_DIR", "GENRE_CACHE_DIR"),
    }.items():
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for attr_name in attr_names:
            if hasattr(module, attr_name):
                module_attrs.append((module, attr_name, getattr(module, attr_name)))

    data_root = tmp_path / "data"
    monkeypatch.setattr(constant, "APP_DATA_DIR", str(data_root))
    profiles.apply_profile_to_constants(profiles.MAIN_PROFILE)
    yield data_root

    for name, value in original_constants.items():
        setattr(constant, name, value)
    for module, attr_name, value in module_attrs:
        setattr(module, attr_name, value)


def _movie(title: str) -> dict:
    return {
        "main_info": {
            "title": title,
            "year": 2020,
            "user_score": 8.0,
        }
    }


def test_main_profile_is_active_by_default(isolated_profiles) -> None:
    assert profiles.get_active_profile() == profiles.MAIN_PROFILE
    assert profiles.get_active_data_dir() == isolated_profiles


def test_create_sandbox_profile_creates_layout_without_runtime_json_files(isolated_profiles) -> None:
    profiles.create_sandbox_profile()

    sandbox_dir = profiles.get_profile_data_dir(profiles.SANDBOX_PROFILE)

    assert sandbox_dir == isolated_profiles / "profiles" / "sandbox"
    assert sandbox_dir != isolated_profiles
    for directory in (
        sandbox_dir,
        sandbox_dir / "watched",
        sandbox_dir / "candidates",
        sandbox_dir / "cache",
        sandbox_dir / "cache" / "posters",
        sandbox_dir / "cache" / "posters" / "images",
        sandbox_dir / "exports",
        sandbox_dir / "logs",
        sandbox_dir / "backups",
    ):
        assert directory.is_dir()
    for path in (
        sandbox_dir / "watched" / "titles.json",
        sandbox_dir / "watched" / "meta.json",
        sandbox_dir / "candidates" / "pool.json",
        sandbox_dir / "candidates" / "criteria.json",
        sandbox_dir / "candidates" / "watchlist.json",
        sandbox_dir / "candidates" / "hidden.json",
        sandbox_dir / "cache" / "posters" / "posters.json",
    ):
        assert path.exists() is False
    assert (sandbox_dir / "profile.json").is_file()


def test_switch_sandbox_changes_active_profile_and_paths(isolated_profiles) -> None:
    profiles.create_sandbox_profile()
    profiles.set_active_profile(profiles.SANDBOX_PROFILE)

    assert profiles.get_active_profile() == profiles.SANDBOX_PROFILE
    assert profiles.get_active_data_dir() == isolated_profiles / "profiles" / "sandbox"
    assert Path(constant.FILE_NAME) == isolated_profiles / "profiles" / "sandbox" / "watched" / "titles.json"


def test_console_create_sandbox_does_not_switch_profile(isolated_profiles, capsys) -> None:
    from ui.console import data_profiles_menu

    data_profiles_menu.create_sandbox()

    output = capsys.readouterr().out
    assert profiles.get_active_profile() == profiles.MAIN_PROFILE
    assert "Активный профиль не изменён" in output
    assert "пункт 3" in output


def test_load_save_dataset_in_sandbox_does_not_change_main_dataset(isolated_profiles) -> None:
    from storage import data as storage_data
    from storage import runtime

    runtime.ensure_runtime_data_layout()
    storage_data.save_dataset({"Main": _movie("Main")})

    profiles.create_sandbox_profile()
    profiles.set_active_profile(profiles.SANDBOX_PROFILE)
    runtime.ensure_runtime_data_layout()
    storage_data.save_dataset({"Sandbox": _movie("Sandbox")})

    assert list(storage_data.load_dataset()) == ["Sandbox"]

    profiles.set_active_profile(profiles.MAIN_PROFILE)

    assert list(storage_data.load_dataset()) == ["Main"]
    assert (isolated_profiles / "watchbane.sqlite3").is_file()
    assert (isolated_profiles / "profiles" / "sandbox" / "watchbane.sqlite3").is_file()


def test_reset_sandbox_clears_sandbox_but_not_main(isolated_profiles) -> None:
    from storage import data as storage_data
    from storage import runtime

    runtime.ensure_runtime_data_layout()
    storage_data.save_dataset({"Main": _movie("Main")})

    profiles.create_sandbox_profile()
    profiles.set_active_profile(profiles.SANDBOX_PROFILE)
    runtime.ensure_runtime_data_layout()
    storage_data.save_dataset({"Sandbox": _movie("Sandbox")})

    backup_path = profiles.reset_profile(profiles.SANDBOX_PROFILE)

    assert backup_path.is_dir()
    assert storage_data.load_dataset() == {}

    profiles.set_active_profile(profiles.MAIN_PROFILE)

    assert list(storage_data.load_dataset()) == ["Main"]


def test_reset_main_profile_is_forbidden(isolated_profiles) -> None:
    with pytest.raises(profiles.ProfileSafetyError):
        profiles.reset_profile(profiles.MAIN_PROFILE)


def test_return_to_main_restores_main_dataset_access(isolated_profiles) -> None:
    from storage import data as storage_data
    from storage import runtime

    runtime.ensure_runtime_data_layout()
    storage_data.save_dataset({"Main": _movie("Main")})
    profiles.create_sandbox_profile()
    profiles.set_active_profile(profiles.SANDBOX_PROFILE)
    storage_data.save_dataset({"Sandbox": _movie("Sandbox")})

    profiles.set_active_profile(profiles.MAIN_PROFILE)

    assert profiles.get_active_profile() == profiles.MAIN_PROFILE
    assert list(storage_data.load_dataset()) == ["Main"]


def test_console_data_profiles_menu_uses_profile_manager_not_storage() -> None:
    from ui.console import data_profiles_menu
    from ui.console import global_menu

    source = inspect.getsource(data_profiles_menu)
    global_source = inspect.getsource(global_menu.open_data_profiles_menu)

    assert "storage_data" not in source
    assert "storage.data" not in source
    assert "profiles." in source
    assert "data_profiles_menu.open_data_profiles_menu" in global_source
