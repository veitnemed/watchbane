"""Собирает текущее состояние приложения для экранов меню."""

from data_work import storage
from model import model


def get_menu_state():
    """Возвращает датасет, веса, количество сериалов и текущую ошибку модели."""
    data = storage.load_dataset()
    weights = storage.load_weights()
    movies_counter = len(data)
    abs_error = model.mean_absolute_error(data, weights)
    return data, weights, movies_counter, abs_error
