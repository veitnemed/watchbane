"""Считает прогнозы, ошибки модели и подбирает веса признаков."""

from config import constant
from core import format_score
import random as rnd


def iter_movies(data):
    """Возвращает список фильмов из датасета любого поддерживаемого формата."""
    if isinstance(data, dict):
        return list(data.values())
    return data


def get_movie_title(movie: dict) -> str:
    """Возвращает название фильма из записи датасета."""
    return movie["main_info"]["title"]


def get_user_score(movie: dict) -> float:
    """Возвращает пользовательскую оценку фильма."""
    return movie["main_info"]["user_score"]


def get_features(movie: dict) -> dict:
    """Собирает признаки фильма для модели."""
    features = {}

    for feature in movie["computed_scores"]:
        features[feature] = movie["computed_scores"][feature]

    for feature, value in format_score.tags_to_features(movie[constant.TAGS_VIBE_SECTION]).items():
        features[feature] = value

    return features


def predict_score(features: dict, weights=constant.DEFAULT_WEIGHTS) -> float:
    """Считает прогноз оценки по признакам и весам."""
    score = 0
    for key, value in weights.items():
        
        score += features[key] * value
    return score


def calc_error(movie: dict, weights=constant.DEFAULT_WEIGHTS) -> float:
    """Считает ошибку прогноза для одного фильма."""
    user_score = get_user_score(movie)
    score = predict_score(get_features(movie), weights)
    return score - user_score


def mean_absolute_error(data: list, weights=constant.DEFAULT_WEIGHTS) -> float:
    """Считает среднюю абсолютную ошибку модели."""
    movies = iter_movies(data)
    length = len(movies)
    absolute_error = 0
    if length == 0:
        return 0
    for obj in movies:
        absolute_error += abs(calc_error(obj, weights)) / length
    return absolute_error


def kp_mean_absolute_error(data: list) -> float:
    """Считает ошибку рейтинга Кинопоиска относительно личных оценок."""
    movies = iter_movies(data)
    length = len(movies)
    absolute_error = 0
    if length == 0:
        return 0
    for obj in movies:
        user_score = get_user_score(obj)
        kp_score = obj["raw_scores"]["kp_score"]
        absolute_error += abs(user_score - kp_score) / length
    return absolute_error


def mean_error(data: list, weights=constant.DEFAULT_WEIGHTS) -> float:
    """Считает среднее отклонение модели с учетом знака."""
    movies = iter_movies(data)
    length = len(movies)
    error = 0
    if length == 0:
        return 0
    for obj in movies:
        error += calc_error(obj, weights) / length
    return error

def choice_rand_features(amount: int = 2) -> list:
    """Выбирает случайные признаки модели."""
    features = list(constant.DEFAULT_WEIGHTS.keys())
    amount = min(amount, len(features))
    return rnd.sample(features, amount)


def choice_rand_fatures(amount: int = 2) -> list:
    """Вызывает выбор случайных признаков через старое имя функции."""
    return choice_rand_features(amount)


def normalize_weights(weights: dict) -> dict:
    """Нормализует веса так, чтобы их сумма была равна единице."""
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return weights.copy()

    normalized = {}
    for feature, weight in weights.items():
        normalized[feature] = weight / total_weight
    return normalized


def fit_weights_2(
        data: list,
        start_weights=constant.DEFAULT_WEIGHTS,
        score=5000,
        step: float = constant.STEP
) -> dict:
    """Подбирает веса случайными переносами веса между признаками."""
    data = iter_movies(data)
    
    if len(data) == 0:
        return start_weights.copy()

    weights = start_weights.copy()
    error = mean_absolute_error(data, weights)
    
    not_mutations = 0
    while True:
        
        f1, f2 = choice_rand_features()
        new_weights = weights.copy()

        if new_weights[f2] < step:
            continue

        new_weights[f1] += step
        new_weights[f2] -= step

        new_error = mean_absolute_error(data, new_weights)

        if new_error < error:
            
            weights = new_weights
            error = new_error
            not_mutations = 0
        not_mutations +=1
        
        if not_mutations == score:
            break
    return normalize_weights(weights)


def fit_weights_until_plateau(
        data: list,
        start_weights=constant.DEFAULT_WEIGHTS,
        score=5000,
        step: float = constant.STEP
) -> dict:
    """Подбирает веса до остановки улучшений."""
    return fit_weights_2(data, start_weights, score, step)
        
       
def fit_weights(
        data: list,
        start_weights=constant.DEFAULT_WEIGHTS,
        passes: int = 3,
        step: float = constant.STEP
) -> dict:
    """Подбирает веса перебором значений с заданным шагом."""
    data = iter_movies(data)
    
    if len(data) == 0:
        return start_weights.copy()

    weights = start_weights.copy()

    for _ in range(passes):
        for feature in weights.keys():
            best_error = mean_absolute_error(data, weights)
            best_weight = weights[feature]

            for i in range(int(1 / step) + 1):
                test_weight = i * step
                weights[feature] = test_weight

                error = mean_absolute_error(data, weights)

                if error < best_error:
                    best_error = error
                    best_weight = test_weight

            weights[feature] = best_weight

    return weights


def one_to_one_error(data: list, top_n):
    """Проверяет модель методом leave-one-out."""
    data = iter_movies(data)

    if len(data) < 2:
        print('Недостаточно данных для leave-one-out проверки')
        return 0

    length_data = len(data)
    mean_error = 0
    result = []
    all_dict = {}
    for idx in range(length_data):
        train_data = data.copy()
        test_movie = train_data.pop(idx)

        user_score = get_user_score(test_movie)
        new_weights = fit_weights(train_data)
        features = get_features(test_movie)
        predict = predict_score(get_features(test_movie), new_weights)
        error = abs(user_score - predict)
        result.append((error, get_movie_title(test_movie), round(user_score, 1), round(predict, 1),new_weights, features))
        mean_error += error / length_data

    sorted_result = sorted(result, key=lambda x: x[0], reverse=True)

    counter = 0

    for error, title, user_score, predict, new_weights,features in sorted_result:
        counter += 1
        print(f"\n{title} ({round(user_score, 2)})")
        print('Оценка модели:', round(predict, 2))
        print('Ошибка:', round(error, 2))
        print('\nВклад параметров:')
        res = []
        for k,v in features.items():
            impact = v*new_weights[k]
            res.append((impact,k))

        for k, v in sorted(res, reverse=True):
            print(f"{v}: + {round(k,2)}")

        if counter == top_n:
            break

    print('Средняя ошибка:', round(mean_error, 4))
    return mean_error


def selection_weights_without_feature(
        data: list,
        excluded_feature,
        default_weights: dict = constant.DEFAULT_WEIGHTS
):
    """Подбирает веса модели без указанного признака."""
    data = iter_movies(data)

    if len(data) == 0:
        return default_weights.copy()

    weights_select = default_weights.copy()

    if excluded_feature in weights_select:
        weights_select.pop(excluded_feature)

    features = list(weights_select.keys())

    for feature in features:
        min_error = mean_absolute_error(data, weights_select)
        min_weight = weights_select[feature]

        for i in range(int(1 / constant.STEP) + 1):
            weight = i * constant.STEP
            weights_select[feature] = weight

            error = mean_absolute_error(data, weights_select)

            if error < min_error:
                min_error = error
                min_weight = weight

        weights_select[feature] = min_weight

    return weights_select
