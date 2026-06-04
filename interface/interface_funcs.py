"""Содержит действия интерфейса, которые запускаются из пунктов меню."""

from config import constant
from core import format_score as format
from model_work import model
from interface import request
from data_work import storage
from interface import ui
from core import valid


def show_all_movies():
    """Показывает все фильмы из датасета."""
    data = storage.load_dataset()
    if len(data) == 0:
        print('Датасет пуст!')
        return

    for idx, movie in enumerate(data.values()):
        main_info = movie["main_info"]
        print(f"{idx + 1}) {main_info['title']} | оценка: {main_info['user_score']}")


def get_predict(weights: dict) -> None:
    """Запрашивает признаки и показывает прогноз модели."""
    title = request.loop_input(text='Введите название: ', funcs_list=[valid.is_correct_title])

    features = {}
    for feature in constant.FEATURES:
        answer = request.loop_input(
            text=f'{feature} >> ',
            funcs_list=[valid.is_correct_score]
        )
        features[feature] = valid.parse_float(answer)

    score = model.predict_score(features, weights)
    print(f'Оценка модели для {title}: {score}')


def request_object() -> None:
    """Запрашивает фильм и добавляет его в датасет."""
    ui.clean_terminal()

    movie_request = request.request_all_scores()
    result = storage.add_movie(movie_request)

    if result:
        print('Новая запись добавлена!')
    else:
        print('Ошибка! Новая запись не добавлена')


def show_mean_error(data, weights):
    """Показывает средние ошибки модели."""
    ui.clean_terminal()
    abs_error = model.mean_absolute_error(data, weights)
    error = model.mean_error(data, weights)
    print(f'\nСредняя ошибка модели: {round(abs_error, 2)}')
    print(f'\nСреднее линейное отклонение: {round(error, 2)}')


def show_weights_model(weights):
    """Показывает веса модели."""
    ui.clean_terminal()
    print('Веса модели:\n')
    for weight, value in weights.items():
        print(f'{weight}: {round(value, 2)}')


def reset_weights_model():
    """Сбрасывает веса модели."""
    storage.save_weights(constant.DEFAULT_WEIGHTS.copy())
    print('Веса сброшены на значения по умолчанию.')


def votes_impact():
    """Показывает влияние количества голосов на популярность."""
    data = storage.load_meta()
    for title, obj in data.items():
        raw_scores = obj.get("raw_scores", obj.get("raw"))
        main_info = obj.get("main_info", {})
        year = main_info.get("year", raw_scores.get("year"))
        kp_votes, imdb_votes = raw_scores["kp_votes"], raw_scores["imdb_votes"]
        kp = format.popularity_kp(kp_votes, year)
        imdb = format.popularity_score(imdb_votes, year)
        print(f'{title} ({year})\n')
        print(f'KP: {kp_votes} -> {round(kp, 1)}')
        print(f'IMDB: {imdb_votes} -> {round(imdb, 1)}\n')


def show_feature_importance(weights, full_error):
    """Показывает влияние каждого признака."""
    ui.clean_terminal()
    data = storage.load_dataset()
    for feature in constant.FEATURES:
        weights_without_feature = model.selection_weights_without_feature(data, feature, weights)
        error_without_feature = model.mean_absolute_error(data, weights_without_feature)
        eps = error_without_feature - full_error
        print(f"Ошибка без {feature}: {round(error_without_feature * 10, 1)} %")
        print(f"Эффективность: {round(eps, 2)} \n")


def show_data_info():
    """Показывает сводку по датасету."""
    pass
