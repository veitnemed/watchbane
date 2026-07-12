"""Собирает текущее состояние приложения для экранов меню."""

from storage import data as storage_data
from storage import profiles


def get_menu_state():
    """Возвращает датасет и количество просмотренных записей."""
    data = storage_data.load_dataset()
    movies_counter = len(data)
    return data, movies_counter


def get_candidate_summary_view() -> dict:
    """Returns compact candidate-pool counters for top-level console screens."""
    from candidates import service as candidate_service

    return candidate_service.get_console_candidate_summary_view()


def get_profile_summary_line() -> str:
    """Return compact active data profile status for the main console screen."""
    profile = profiles.get_active_profile()
    return f"Активный профиль данных: {profile}"
