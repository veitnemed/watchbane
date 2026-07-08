"""Console menu for safe data profile and sandbox operations."""

from __future__ import annotations

from functools import partial

from common import valid
from storage import profiles
from ui.console import request
from ui.console import ui

SANDBOX_CONFIRMATION = "RESET SANDBOX"


def _print_active_status() -> None:
    description = profiles.describe_active_profile()
    print(f"Активный профиль: {description['profile']}")
    print(f"Путь: {description['data_dir']}")


def show_active_dataset() -> None:
    """Print active profile and data root."""
    _print_active_status()


def create_sandbox() -> None:
    """Create the sandbox profile without switching implicitly."""
    existed = profiles.SANDBOX_PROFILE in profiles.list_profiles()
    try:
        profiles.create_sandbox_profile()
    except Exception as error:
        print(f"Не удалось создать песочницу: {error}")
        return
    if existed:
        print("Песочница уже существует.")
    else:
        print("Песочница создана.")
    print(f"Путь: {profiles.get_profile_data_dir(profiles.SANDBOX_PROFILE)}")
    print("Активный профиль не изменён. Чтобы войти в песочницу, выбери пункт 3.")


def switch_to_sandbox() -> None:
    """Switch active data paths to sandbox."""
    if profiles.SANDBOX_PROFILE not in profiles.list_profiles():
        print("Песочница ещё не создана. Сначала выбери `Создать песочницу`.")
        return
    try:
        profiles.set_active_profile(profiles.SANDBOX_PROFILE)
    except Exception as error:
        print(f"Не удалось переключиться на песочницу: {error}")
        return
    _print_active_status()


def switch_to_main() -> None:
    """Return active data paths to the main dataset."""
    try:
        profiles.set_active_profile(profiles.MAIN_PROFILE)
    except Exception as error:
        print(f"Не удалось вернуться к основному датасету: {error}")
        return
    _print_active_status()


def _confirm_sandbox_reset(action: str) -> bool:
    print(f"\n{action} песочницу можно только после backup.")
    answer = input(f"Введите {SANDBOX_CONFIRMATION} для подтверждения >> ").strip()
    return answer == SANDBOX_CONFIRMATION


def reset_sandbox() -> None:
    """Reset sandbox after explicit confirmation and backup."""
    if profiles.SANDBOX_PROFILE not in profiles.list_profiles():
        print("Песочница не найдена.")
        return
    if _confirm_sandbox_reset("Сбросить") is False:
        print("Сброс отменён.")
        return

    try:
        backup_path = profiles.reset_profile(profiles.SANDBOX_PROFILE)
    except Exception as error:
        print(f"Сброс отменён: {error}")
        return
    print("Песочница сброшена в пустое состояние.")
    print(f"Backup: {backup_path}")


def delete_sandbox() -> None:
    """Delete inactive sandbox after explicit confirmation and backup."""
    if profiles.SANDBOX_PROFILE not in profiles.list_profiles():
        print("Песочница не найдена.")
        return
    if profiles.get_active_profile() == profiles.SANDBOX_PROFILE:
        print("Нельзя удалить активную песочницу. Сначала вернись к основному датасету.")
        return
    if _confirm_sandbox_reset("Удалить") is False:
        print("Удаление отменено.")
        return

    try:
        backup_path = profiles.delete_profile(profiles.SANDBOX_PROFILE)
    except Exception as error:
        print(f"Удаление отменено: {error}")
        return
    print("Песочница удалена.")
    print(f"Backup: {backup_path}")


def show_active_data_files() -> None:
    """Print important paths used by the active profile."""
    description = profiles.describe_active_profile()
    print(f"Активный профиль: {description['profile']}\n")
    for label, path in description["files"].items():
        print(f"{label}: {path}")


def open_data_profiles_menu() -> None:
    """Open safe data profile management menu."""
    while True:
        ui.clean_terminal()
        ui.show_data_profiles_menu()

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 7)])
        if command == "0":
            return
        if command == "1":
            show_active_dataset()
        elif command == "2":
            create_sandbox()
        elif command == "3":
            switch_to_sandbox()
        elif command == "4":
            reset_sandbox()
        elif command == "5":
            switch_to_main()
        elif command == "6":
            delete_sandbox()
        elif command == "7":
            show_active_data_files()

        ui.press_enter()
