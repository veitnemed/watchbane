"""Собирает текущее состояние приложения для экранов меню."""

from storage import data as storage_data


def get_menu_state():
    """Возвращает датасет и количество просмотренных записей."""
    data = storage_data.load_dataset()
    movies_counter = len(data)
    return data, movies_counter


def get_candidate_summary_view() -> dict:
    """Returns compact candidate-pool counters for top-level console screens."""
    from candidates import service as candidate_service

    return candidate_service.get_console_candidate_summary_view()
