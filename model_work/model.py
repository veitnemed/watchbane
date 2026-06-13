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


def make_group_weights(weights: dict, features: list) -> dict:
    """Оставляет веса только выбранных признаков и нормализует их."""
    group_weights = {}
    for feature in features:
        group_weights[feature] = weights.get(feature, 0)

    total_weight = sum(group_weights.values())
    if total_weight > 0:
        return normalize_weights(group_weights)

    if len(group_weights) == 0:
        return {}

    equal_weight = 1 / len(group_weights)
    return {
        feature: equal_weight
        for feature in group_weights
    }


def print_feature_group_mae(data: list, weights: dict) -> dict:
    """Печатает MAE полной модели, модели без vibe-тегов и модели только на vibe-тегах."""
    data = iter_movies(data)
    if len(data) == 0:
        print("Датасет пуст.")
        return {}

    vibe_features = constant.TAGS_VIBE
    other_features = [
        feature for feature in constant.FEATURES
        if feature not in vibe_features
    ]

    full_mae = mean_absolute_error(data, weights)
    without_vibe_weights = make_group_weights(weights, other_features)
    only_vibe_weights = make_group_weights(weights, vibe_features)

    without_vibe_mae = mean_absolute_error(data, without_vibe_weights)
    only_vibe_mae = mean_absolute_error(data, only_vibe_weights)

    print("\nОЦЕНКА ВКЛАДОВ")
    print("=" * 50)
    print(f"MAE vibe + остальное: {full_mae:.4f} ({full_mae * 10:.2f}%)")
    print(f"MAE без vibe tags: {without_vibe_mae:.4f} ({without_vibe_mae * 10:.2f}%)")
    print(f"MAE только vibe tags: {only_vibe_mae:.4f} ({only_vibe_mae * 10:.2f}%)")
    print("")
    print(f"Признаков без vibe tags: {len(other_features)}")
    print(f"Vibe tags: {len(vibe_features)}")

    return {
        "full_mae": full_mae,
        "without_vibe_mae": without_vibe_mae,
        "only_vibe_mae": only_vibe_mae,
    }

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
    for idx in range(length_data):
        train_data = data.copy()
        test_movie = train_data.pop(idx)

        user_score = get_user_score(test_movie)
        new_weights = fit_weights(train_data)
        features = get_features(test_movie)
        predict = predict_score(features, new_weights)
        signed_error = predict - user_score
        abs_error = abs(signed_error)
        result.append({
            "abs_error": abs_error,
            "signed_error": signed_error,
            "title": get_movie_title(test_movie),
            "user_score": user_score,
            "predict": predict,
            "weights": new_weights,
            "features": features,
        })
        mean_error += abs_error / length_data

    print_error_report("LEAVE-ONE-OUT", result, top_n)

    print('Средняя абсолютная ошибка:', round(mean_error, 2))
    return mean_error


def top_prediction_errors(data: list, weights: dict, top_n: int):
    """Печатает топ ошибок модели на текущих обученных весах."""
    data = iter_movies(data)

    if len(data) == 0:
        print("Датасет пуст.")
        return 0

    rows = []
    mean_error = 0
    for movie in data:
        user_score = get_user_score(movie)
        features = get_features(movie)
        predict = predict_score(features, weights)
        signed_error = predict - user_score
        abs_error = abs(signed_error)
        rows.append({
            "abs_error": abs_error,
            "signed_error": signed_error,
            "title": get_movie_title(movie),
            "user_score": user_score,
            "predict": predict,
            "weights": weights,
            "features": features,
        })
        mean_error += abs_error / len(data)

    print_error_report("ОШИБКИ НА ТЕКУЩИХ ВЕСАХ", rows, top_n)
    print('Средняя абсолютная ошибка:', round(mean_error, 2))
    return mean_error


def split_error_rows(rows: list, top_n: int) -> tuple:
    """Делит ошибки на топ завышений и топ занижений."""
    overestimated = sorted(
        [row for row in rows if row["signed_error"] > 0],
        key=lambda row: row["signed_error"],
        reverse=True
    )[:top_n]
    underestimated = sorted(
        [row for row in rows if row["signed_error"] < 0],
        key=lambda row: row["signed_error"]
    )[:top_n]
    return overestimated, underestimated


def print_error_report(title: str, rows: list, top_n: int) -> None:
    """Печатает краткую и полную информацию по топу ошибок."""
    overestimated, underestimated = split_error_rows(rows, top_n)

    print(f"\n{title}")
    print("=" * 50)

    print("\n# КРАТКАЯ ИНФОРМАЦИЯ")
    print_short_error_group("МОДЕЛЬ ЗАВЫШАЕТ", overestimated)
    print_short_error_group("МОДЕЛЬ ЗАНИЖАЕТ", underestimated)

    print("\n# ПОЛНАЯ ИНФОРМАЦИЯ")
    print_full_error_group("МОДЕЛЬ ЗАВЫШАЕТ", overestimated)
    print_full_error_group("МОДЕЛЬ ЗАНИЖАЕТ", underestimated)


def print_short_error_group(title: str, rows: list) -> None:
    """Печатает короткий список ошибок."""
    print(f"\n{title}")

    if len(rows) == 0:
        print("Нет объектов.")
        return

    for idx, row in enumerate(rows, start=1):
        print(
            f"{idx}. {row['title']} "
            f"({row['user_score']:.1f}) -> {row['predict']:.1f} "
            f"| ошибка {row['signed_error']:+.2f}"
        )


def print_full_error_group(title: str, rows: list) -> None:
    """Печатает подробности ошибок с ограничением до 4 признаков."""
    print(f"\n{title}")

    if len(rows) == 0:
        print("Нет объектов.")
        return

    for idx, row in enumerate(rows, start=1):
        print(f"\n{idx}. {row['title']}")
        print(f"Моя оценка: {row['user_score']:.2f}")
        print(f"Оценка модели: {row['predict']:.2f}")
        print(f"Ошибка: {row['signed_error']:+.2f}")
        print("Вклад параметров:")

        impacts = []
        for feature, value in row["features"].items():
            impact = value * row["weights"][feature]
            impacts.append((abs(impact), impact, feature))

        for _, impact, feature in sorted(impacts, reverse=True)[:4]:
            print(f"{feature}: {impact:+.2f}")


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


