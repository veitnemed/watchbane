"""Собирает текущее состояние приложения для экранов меню."""

from storage import data as storage_data
from model import model


def get_menu_state():
    """Возвращает датасет, веса, количество сериалов и текущую ошибку модели."""
    data = storage_data.load_dataset()
    weights = storage_data.load_weights()
    movies_counter = len(data)
    abs_error = model.mean_absolute_error(data, weights)
    return data, weights, movies_counter, abs_error
