"""Собирает и сохраняет отчёт по датасету, модели и результатам экспериментов."""

from __future__ import annotations

import os
from datetime import datetime

from config import constant
from dataset import dataset_stats
from dataset import tags_work
from model import linear_regression_train
from model import model
from model import noise_experiment
from storage import data as storage_data

REPORTS_DIR_NAME = "reports"

LOO_REPORT_DETAIL_MAX_RECORDS = 150
REPORT_NOISE_DELTAS = (0.1, 0.25, 0.5, 1.5)
REPORT_NOISE_RUNS = 5
REPORT_NOISE_SEED = 42

ERROR_CARD_TOP_N = 10
ERROR_DESCRIPTION_LIMIT = 500
ERROR_IMPACT_TOP_N = 5


def _section(title: str, char: str = "=") -> list[str]:
    width = max(len(title), 60)
    return ["", title, char * width]


def _subsection(title: str) -> list[str]:
    return ["", title, "-" * min(60, max(len(title), 20))]


def _format_optional(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "не рассчитан"
    return f"{value:.{digits}f}"


def _default_loo_progress(current: int, total: int, title: str | None = None) -> None:
    title_part = f" | {title}" if title else ""
    print(f"LOO MAE: выполнено {current}/{total}{title_part}")


def _default_noise_progress(
    stage: str,
    delta_index: int,
    delta_total: int,
    delta: float,
    run_index: int,
    run_total: int,
) -> None:
    if stage == "delta":
        print(f"\nУстойчивость оценок: delta={delta:.2f} [{delta_index}/{delta_total}]")
        return
    print(f"  delta={delta:.2f}: прогон {run_index}/{run_total}")


def compute_benchmark_loo_mae(
    data: dict,
    weights: dict,
    progress_callback=None,
) -> float | None:
    """Считает LOO MAE Ridge benchmark с прогрессом (без чтения кэша)."""
    movies = model.iter_movies(data)
    if len(movies) < 2:
        return None
    if linear_regression_train.is_method_available(linear_regression_train.BENCHMARK_METHOD) is False:
        return None

    callback = progress_callback or _default_loo_progress
    return linear_regression_train.calculate_linear_loo_mae(
        data=movies,
        method=linear_regression_train.BENCHMARK_METHOD,
        start_weights=weights,
        alpha=linear_regression_train.BENCHMARK_RIDGE_ALPHA,
        l1_ratio=0.5,
        max_iter=5000,
        progress_callback=callback,
    )


def get_tag_usage(data: dict) -> dict:
    """Считает, сколько сериалов использует каждый тег."""
    usage = {feature: 0 for feature in constant.TAGS_VIBE}
    for movie in data.values():
        tags_vibe = movie.get(constant.TAGS_VIBE_SECTION, {})
        for feature in constant.TAGS_VIBE:
            if tags_vibe.get(feature, 0) > 0:
                usage[feature] += 1
    return usage


def get_genre_usage(data: dict) -> dict:
    """Считает, сколько сериалов размечено каждым жанровым признаком."""
    usage = {feature: 0 for feature in constant.GENRE}
    for movie in data.values():
        genre_section = movie.get(constant.GENRE_SECTION, {})
        for feature in constant.GENRE:
            if genre_section.get(feature, 0) > 0:
                usage[feature] += 1
    return usage


def _truncate_description(text: str | None, limit: int = ERROR_DESCRIPTION_LIMIT) -> str:
    """Нормализует пробелы и обрезает описание для карточки ошибки."""
    normalized = " ".join(str(text or "").split())
    if normalized == "":
        return ""
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def _read_tmdb_overview_from_cache(tmdb_id) -> str | None:
    """Читает overview из локального TMDb cache без сетевых запросов."""
    from apis import tmdb_api

    try:
        tmdb_id_int = int(tmdb_id)
    except (TypeError, ValueError):
        return None

    safe_language = tmdb_api.DEFAULT_LANGUAGE.replace("-", "_")
    cache_path = tmdb_api.DETAILS_CACHE_DIR / f"{tmdb_id_int}_{safe_language}.json"
    cached = tmdb_api.read_json(cache_path)
    if isinstance(cached, dict) is False:
        return None

    overview = str(cached.get("overview") or "").strip()
    return overview or None


def _movie_identity_key(title: str, year) -> str:
    from candidates.keys import normalize_key_part

    return f"{normalize_key_part(title)}|{str(year or '').strip()}"


def _load_description_lookup_cache() -> dict:
    """Загружает meta и pool один раз для блока карточек ошибок."""
    meta_by_title = {}
    for meta_title, meta_obj in storage_data.load_meta().items():
        if isinstance(meta_obj, dict):
            meta_by_title[meta_title.strip().casefold()] = meta_obj

    pool_by_identity = {}
    try:
        from candidates import candidate_pool
        from candidates import keys as candidate_keys

        pool = candidate_pool.load_candidate_pool()
        for candidate in pool.values():
            if isinstance(candidate, dict) is False:
                continue
            identity = candidate_keys.title_identity_key(candidate)
            pool_by_identity.setdefault(identity, candidate)
    except Exception:
        pass

    return {
        "meta_by_title": meta_by_title,
        "pool_by_identity": pool_by_identity,
    }


def _get_meta_from_cache(lookup_cache: dict, title: str) -> dict | None:
    meta_obj = lookup_cache["meta_by_title"].get(title.strip().casefold())
    if isinstance(meta_obj, dict):
        return meta_obj
    return storage_data.get_meta_obj(title)


def _description_from_pool_candidate(candidate: dict) -> str:
    from candidates import candidate_pool

    for field_name in ("description", "overview", "tmdb_overview", "plot", "short_description"):
        text = str(candidate.get(field_name) or "").strip()
        if text:
            return text
    formatted = candidate_pool.format_candidate_description(candidate, limit=ERROR_DESCRIPTION_LIMIT)
    if formatted == "нет данных":
        return ""
    return formatted


def resolve_movie_description(
    title: str,
    year,
    meta_obj: dict | None,
    pool_by_identity: dict,
    *,
    tmdb_cache_reader=_read_tmdb_overview_from_cache,
) -> str:
    """Возвращает описание: meta → pool → TMDb cache → fallback."""
    if isinstance(meta_obj, dict):
        meta_text = _truncate_description(meta_obj.get("description"))
        if meta_text:
            return meta_text

    identity = _movie_identity_key(title, year)
    pool_candidate = pool_by_identity.get(identity)
    if isinstance(pool_candidate, dict):
        pool_text = _truncate_description(_description_from_pool_candidate(pool_candidate))
        if pool_text:
            return pool_text

    if isinstance(meta_obj, dict):
        tmdb_id = meta_obj.get("tmdb_id")
        if tmdb_id is not None:
            tmdb_text = _truncate_description(tmdb_cache_reader(tmdb_id))
            if tmdb_text:
                return tmdb_text

    return "нет описания"


def format_biggest_error_card_lines(row: dict, description: str) -> list[str]:
    """Форматирует одну карточку «самая большая ошибка»."""
    lines = [
        f"{row['title']} ({row['user_score']:.2f})",
        f"Оценка: {row['prediction']:.2f} (ошибка: {row['error']:+.2f})",
        "Вклады:",
    ]
    for _abs_impact, impact, feature in row["top_impacts"][:ERROR_IMPACT_TOP_N]:
        label = dataset_stats.get_feature_label(feature)
        lines.append(f"  {feature} ({label}): {impact:+.2f}")
    lines.append(description)
    lines.append("")
    return lines


def collect_all_error_rows(data: dict, weights: dict) -> list[dict]:
    """Возвращает все строки ошибок модели, отсортированные по |error|."""
    rows = []
    for movie in model.iter_movies(data):
        features = model.get_features(movie)
        prediction = model.predict_score(features, weights)
        user_score = model.get_user_score(movie)
        error = prediction - user_score
        impacts = []
        for feature, weight in weights.items():
            feature_value = features.get(feature, 0)
            impact = feature_value * weight
            impacts.append((abs(impact), impact, feature))
        main_info = movie.get("main_info", {})
        rows.append({
            "title": model.get_movie_title(movie),
            "year": main_info.get("year"),
            "user_score": user_score,
            "prediction": prediction,
            "error": error,
            "abs_error": abs(error),
            "top_impacts": sorted(impacts, reverse=True)[:ERROR_IMPACT_TOP_N],
        })
    rows.sort(key=lambda row: row["abs_error"], reverse=True)
    return rows


def collect_feature_group_mae(data: dict, weights: dict) -> dict:
    """Считает MAE по группам признаков без вывода в консоль."""
    movies = model.iter_movies(data)
    if len(movies) == 0:
        return {}

    vibe_features = constant.TAGS_VIBE
    other_features = [feature for feature in constant.FEATURES if feature not in vibe_features]
    return {
        "full_mae": model.mean_absolute_error(movies, weights),
        "without_vibe_mae": model.mean_absolute_error(movies, model.make_group_weights(weights, other_features)),
        "only_vibe_mae": model.mean_absolute_error(movies, model.make_group_weights(weights, vibe_features)),
        "other_features_count": len(other_features),
        "vibe_features_count": len(vibe_features),
    }


def build_dataset_lines(data: dict) -> list[str]:
    """Подробная информация о датасете."""
    lines = _section("1. ДАТАСЕТ")
    movies_counter = len(data)
    lines.append(f"Записей в датасете: {movies_counter}")

    meta = storage_data.load_meta()
    lines.append(f"Записей в meta: {len(meta)}")

    dataset_titles = {str(key).strip().casefold() for key in data.keys()}
    meta_titles = {str(key).strip().casefold() for key in meta.keys()}
    only_dataset = sorted(dataset_titles - meta_titles)
    only_meta = sorted(meta_titles - dataset_titles)
    if only_dataset:
        lines.append(f"Только в dataset (без meta): {len(only_dataset)}")
    if only_meta:
        lines.append(f"Только в meta (без dataset): {len(only_meta)}")

    lines.extend(dataset_stats.build_dataset_info_lines(data))

    if movies_counter == 0:
        lines.append("Каталог записей пуст.")
        return lines

    lines.extend(_subsection("Каталог записей (title | year | user | KP | IMDb)"))
    sorted_movies = sorted(
        data.items(),
        key=lambda item: (
            -float(item[1].get("main_info", {}).get("user_score") or 0),
            str(item[1].get("main_info", {}).get("title") or item[0]).casefold(),
        ),
    )
    for index, (_key, movie) in enumerate(sorted_movies, start=1):
        main_info = movie.get("main_info", {})
        raw_scores = movie.get("raw_scores", {})
        title = main_info.get("title") or _key
        year = main_info.get("year", "?")
        user_score = main_info.get("user_score", "?")
        kp = raw_scores.get("kp_score", "-")
        imdb = raw_scores.get("imdb_score", "-")
        lines.append(f"{index:3}. {title} ({year}) | user={user_score} | KP={kp} | IMDb={imdb}")

    genre_usage = get_genre_usage(data)
    marked_genres = [(feature, count) for feature, count in genre_usage.items() if count > 0]
    lines.extend(_subsection("Жанровая разметка в dataset"))
    if len(marked_genres) == 0:
        lines.append("Жанровые признаки не используются.")
    else:
        for feature, count in sorted(marked_genres, key=lambda item: (-item[1], item[0])):
            label = dataset_stats.get_feature_label(feature)
            lines.append(f"  {feature} ({label}): {count}/{movies_counter}")

    tag_usage = get_tag_usage(data)
    used_tags = [(feature, count) for feature, count in tag_usage.items() if count > 0]
    lines.extend(_subsection("Vibe-теги в dataset"))
    if len(used_tags) == 0:
        lines.append("Vibe-теги не используются.")
    else:
        tags = tags_work.load_tags()
        for feature, count in sorted(used_tags, key=lambda item: (-item[1], item[0])):
            label = tags.get(feature, {}).get("label", dataset_stats.get_feature_label(feature))
            lines.append(f"  {feature} ({label}): {count}/{movies_counter}")

    return lines


def build_model_lines(data: dict, weights: dict, *, fresh_loo_mae: float | None = None) -> list[str]:
    """Метрики, baseline и вклад групп признаков."""
    lines = _section("2. МОДЕЛЬ И МЕТРИКИ")
    movies = model.iter_movies(data)
    saved_loo_mae = storage_data.get_saved_loo_mae()
    metrics = linear_regression_train.collect_loo_metrics(
        data=movies,
        weights=weights,
        loo_mae=fresh_loo_mae if fresh_loo_mae is not None else saved_loo_mae,
    )

    lines.append(f"Model MAE:  {_format_optional(metrics.get('Model MAE'))} ({_format_optional((metrics.get('Model MAE') or 0) * 10, 2)}%)")
    lines.append(f"KP_MAE:     {_format_optional(metrics.get('KP_MAE'))}")
    lines.append(f"IMDb_MAE:   {_format_optional(metrics.get('IMDb_MAE'))}")
    lines.append(f"LOO MAE:    {_format_optional(metrics.get('LOO MAE'))}")
    lines.append(f"Mean error: {_format_optional(model.mean_error(movies, weights))} (со знаком)")

    group_mae = collect_feature_group_mae(data, weights)
    if group_mae:
        lines.extend(_subsection("MAE по группам признаков"))
        lines.append(f"  Полная модель:           {_format_optional(group_mae['full_mae'])}")
        lines.append(f"  Без vibe-тегов:          {_format_optional(group_mae['without_vibe_mae'])}")
        lines.append(f"  Только vibe-теги:        {_format_optional(group_mae['only_vibe_mae'])}")
        lines.append(f"  Признаков без vibe: {group_mae['other_features_count']}, vibe tags: {group_mae['vibe_features_count']}")

    loo_mae = metrics.get("LOO MAE")
    kp_mae = metrics.get("KP_MAE")
    imdb_mae = metrics.get("IMDb_MAE")
    if loo_mae is not None and kp_mae is not None and imdb_mae is not None:
        lines.extend(_subsection("Сравнение с baseline (KP / IMDb)"))
        lines.append(f"  {linear_regression_train._format_baseline_comparison(loo_mae, kp_mae, 'KP')}")
        lines.append(f"  {linear_regression_train._format_baseline_comparison(loo_mae, imdb_mae, 'IMDb')}")
        lines.append(f"  Вывод: {linear_regression_train._baseline_result_phrase(loo_mae, kp_mae, imdb_mae)}")

    weight_sum = sum(float(weights.get(feature, 0) or 0) for feature in constant.FEATURES)
    lines.append(f"Сумма весов: {weight_sum:.4f}")

    return lines


LOO_REPORT_MAX_RECORDS = LOO_REPORT_DETAIL_MAX_RECORDS


def build_loo_per_record_lines(
    data: dict,
    weights: dict,
    *,
    fresh_loo_mae: float | None = None,
    progress_callback=None,
) -> tuple[list[str], float | None]:
    """LOO benchmark Ridge: свежий MAE и per-record ошибки. Возвращает (lines, loo_mae)."""
    lines = _section("3. LOO BENCHMARK (Ridge)")
    movies = model.iter_movies(data)
    count = len(movies)
    computed_loo_mae = fresh_loo_mae

    if count < 2:
        lines.append("Недостаточно данных: нужно минимум 2 записи.")
        return lines, None
    if linear_regression_train.is_method_available(linear_regression_train.BENCHMARK_METHOD) is False:
        lines.append(f"Недоступен {linear_regression_train.BENCHMARK_METHOD_LABEL} (sklearn не установлен).")
        return lines, None

    lines.append(f"Метод: {linear_regression_train.BENCHMARK_METHOD_LABEL}")
    lines.append(f"Alpha: {linear_regression_train.BENCHMARK_RIDGE_ALPHA}")
    lines.append(f"Записей: {count}")

    callback = progress_callback or _default_loo_progress

    if count > LOO_REPORT_DETAIL_MAX_RECORDS:
        if computed_loo_mae is None:
            computed_loo_mae = compute_benchmark_loo_mae(data, weights, progress_callback=callback)
        lines.append(f"LOO MAE: {_format_optional(computed_loo_mae)}")
        lines.append(
            f"Per-record таблица пропущена ({count} > {LOO_REPORT_DETAIL_MAX_RECORDS})."
        )
        return lines, computed_loo_mae

    loo_rows = []
    mean_abs_error = 0.0
    for index in range(count):
        train_data = movies.copy()
        test_movie = train_data.pop(index)
        title = model.get_movie_title(test_movie)
        callback(index + 1, count, title)
        trained_weights = linear_regression_train.train_ridge_for_benchmark(
            data=train_data,
            start_weights=weights,
        )
        user_score = model.get_user_score(test_movie)
        predict = model.predict_score(model.get_features(test_movie), trained_weights)
        signed_error = predict - user_score
        abs_error = abs(signed_error)
        mean_abs_error += abs_error / count
        loo_rows.append({
            "title": title,
            "user_score": user_score,
            "predict": predict,
            "signed_error": signed_error,
            "abs_error": abs_error,
        })

    computed_loo_mae = mean_abs_error
    loo_rows.sort(key=lambda row: row["abs_error"], reverse=True)
    lines.append(f"LOO MAE: {_format_optional(computed_loo_mae)}")
    lines.append("")
    for index, row in enumerate(loo_rows, start=1):
        lines.append(
            f"  {index:3}. {row['title']} | user={row['user_score']:.2f} | "
            f"LOO predict={row['predict']:.2f} | error={row['signed_error']:+.2f}"
        )
    return lines, computed_loo_mae


def build_noise_sensitivity_lines(
    data: dict,
    weights: dict,
    *,
    grid_result: dict | None = None,
) -> list[str]:
    """Шумовой эксперiment: сетка delta с LOO-метриками."""
    lines = _section("4. ТЕСТ УСТОЙЧИВОСТИ К ШУМУ")
    movies = model.iter_movies(data)
    if len(movies) < 2:
        lines.append("Недостаточно данных: нужно минимум 2 записи.")
        return lines
    if linear_regression_train.is_method_available(linear_regression_train.BENCHMARK_METHOD) is False:
        lines.append(f"Недоступен {linear_regression_train.BENCHMARK_METHOD_LABEL}.")
        return lines

    if grid_result is None:
        lines.append("Расчёт не выполнен.")
        return lines

    lines.append(f"Повторов на каждый разброс: {grid_result['runs']}")
    lines.append(f"Разброс оценки (±): {', '.join(f'{value:.2f}' for value in grid_result['deltas'])}")
    lines.append(f"LOO MAE до теста: {_format_optional(grid_result.get('original_loo_mae_before'))}")
    lines.append("")

    for result in grid_result["results_by_delta"]:
        lines.extend(_subsection(f"Delta ±{result['delta']:.2f}"))
        lines.append(f"  avg LOO на зашумленных данных: {_format_optional(result.get('avg_noisy_loo_mae'))}")
        lines.append(
            "  avg LOO на исходных после обучения на шуме: "
            f"{_format_optional(result.get('avg_original_loo_mae_after_noise_training'))}"
        )
        lines.append(
            "  диапазон LOO на исходных: "
            f"{_format_optional(result.get('min_original_loo_mae_after_noise_training'))}"
            f" .. "
            f"{_format_optional(result.get('max_original_loo_mae_after_noise_training'))}"
        )

    return lines


def build_weights_lines(weights: dict) -> list[str]:
    """Полный список весов и отличия от default."""
    lines = _section("5. ВЕСА МОДЕЛИ")
    lines.extend(_subsection("Все веса (|weight| desc)"))
    for feature, weight in sorted(weights.items(), key=lambda item: abs(float(item[1] or 0)), reverse=True):
        label = dataset_stats.get_feature_label(feature)
        default_weight = constant.DEFAULT_WEIGHTS.get(feature, 0)
        delta = float(weight or 0) - float(default_weight or 0)
        delta_text = f", delta vs default: {delta:+.4f}" if abs(delta) > 0.00005 else ""
        lines.append(f"  {feature} | {label}: {float(weight or 0):+.4f}{delta_text}")

    positive = sorted(
        ((name, float(value or 0)) for name, value in weights.items() if name != "bias" and float(value or 0) > 0),
        key=lambda item: item[1],
        reverse=True,
    )
    negative = sorted(
        ((name, float(value or 0)) for name, value in weights.items() if name != "bias" and float(value or 0) < 0),
        key=lambda item: item[1],
    )
    lines.extend(_subsection("Топ положительных весов"))
    if positive:
        for index, (name, value) in enumerate(positive[:15], start=1):
            lines.append(f"  {index}. {name}: {value:+.4f}")
    else:
        lines.append("  нет")

    lines.extend(_subsection("Топ отрицательных весов"))
    if negative:
        for index, (name, value) in enumerate(negative[:15], start=1):
            lines.append(f"  {index}. {name}: {value:+.4f}")
    else:
        lines.append("  нет")

    lines.extend(_subsection("Vibe-теги: использование и вес"))
    tag_usage = get_tag_usage(storage_data.load_dataset())
    tags = tags_work.load_tags()
    movies_counter = len(storage_data.load_dataset())
    for feature in constant.TAGS_VIBE:
        settings = tags.get(feature, {})
        label = settings.get("label", dataset_stats.get_feature_label(feature))
        used_count = tag_usage.get(feature, 0)
        weight = float(weights.get(feature, 0) or 0)
        lines.append(f"  {feature} | {label}: used {used_count}/{movies_counter}, weight {weight:+.4f}")

    return lines


def build_error_lines(data: dict, weights: dict) -> list[str]:
    """Полный анализ ошибок модели."""
    lines = _section("6. ОШИБКИ МОДЕЛИ")
    rows = collect_all_error_rows(data, weights)
    if len(rows) == 0:
        lines.append("Датасет пуст — ошибки не рассчитаны.")
        return lines

    mae = model.mean_absolute_error(data, weights)
    lines.append(f"Средняя абсолютная ошибка (MAE): {mae:.4f}")
    lines.append(f"Всего записей с ошибкой: {len(rows)}")

    lookup_cache = _load_description_lookup_cache()
    lines.extend(_subsection("САМЫЕ БОЛЬШИЕ ОШИБКИ"))
    for row in rows[:ERROR_CARD_TOP_N]:
        meta_obj = _get_meta_from_cache(lookup_cache, row["title"])
        description = resolve_movie_description(
            row["title"],
            row.get("year"),
            meta_obj,
            lookup_cache["pool_by_identity"],
        )
        lines.extend(format_biggest_error_card_lines(row, description))

    error_rows_for_split = [
        {
            "signed_error": row["error"],
            "title": row["title"],
            "user_score": row["user_score"],
            "predict": row["prediction"],
            "features": {},
            "weights": weights,
        }
        for row in rows
    ]
    overestimated, underestimated = model.split_error_rows(error_rows_for_split, top_n=len(rows))

    lines.extend(_subsection(f"Модель завышает ({len([r for r in rows if r['error'] > 0])} записей)"))
    if overestimated:
        for index, row in enumerate(overestimated[:20], start=1):
            lines.append(
                f"  {index}. {row['title']} | user={row['user_score']:.2f} -> "
                f"predict={row['predict']:.2f} | error={row['signed_error']:+.2f}"
            )
        if len(overestimated) > 20:
            lines.append(f"  ... ещё {len(overestimated) - 20} записей")
    else:
        lines.append("  нет")

    lines.extend(_subsection(f"Модель занижает ({len([r for r in rows if r['error'] < 0])} записей)"))
    if underestimated:
        for index, row in enumerate(underestimated[:20], start=1):
            lines.append(
                f"  {index}. {row['title']} | user={row['user_score']:.2f} -> "
                f"predict={row['predict']:.2f} | error={row['signed_error']:+.2f}"
            )
        if len(underestimated) > 20:
            lines.append(f"  ... ещё {len(underestimated) - 20} записей")
    else:
        lines.append("  нет")

    lines.extend(_subsection("Все записи по убыванию |error|"))
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"  {index:3}. {row['title']} | user={row['user_score']:.2f} | "
            f"model={row['prediction']:.2f} | error={row['error']:+.2f}"
        )
        impact_text = []
        for _abs_impact, impact, feature in row["top_impacts"]:
            impact_text.append(f"{feature}: {impact:+.2f}")
        lines.append(f"       топ-5 вкладов: {', '.join(impact_text)}")

    return lines


def build_train_report(
    data: dict,
    weights: dict,
    *,
    loo_lines: list[str] | None = None,
    fresh_loo_mae: float | None = None,
    noise_lines: list[str] | None = None,
) -> list[str]:
    """Собирает отчёт по датасету, модели и экспериментам."""
    lines = []
    lines.append("ОТЧЁТ ПО ДАННЫМ И МОДЕЛИ")
    lines.append("=" * 60)
    lines.append(f"Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    lines.append(f"Записей в датасете: {len(data)}")

    lines.extend(build_dataset_lines(data))
    lines.extend(build_model_lines(data, weights, fresh_loo_mae=fresh_loo_mae))
    if loo_lines is not None:
        lines.extend(loo_lines)
    else:
        loo_section, _computed = build_loo_per_record_lines(data, weights, fresh_loo_mae=fresh_loo_mae)
        lines.extend(loo_section)
    if noise_lines is not None:
        lines.extend(noise_lines)
    else:
        lines.extend(build_noise_sensitivity_lines(data, weights, grid_result=None))
    lines.extend(build_weights_lines(weights))
    lines.extend(build_error_lines(data, weights))

    lines.append("")
    lines.append("=" * 60)
    lines.append("КОНЕЦ ОТЧЁТА")
    return lines


def export_train_report() -> str:
    """Выгружает полный отчёт: тяжёлые метрики считаются заново с прогрессом в консоли."""
    data = storage_data.load_dataset()
    weights = storage_data.load_weights()
    movies_count = len(data)

    print("")
    print("=" * 58)
    print("ФОРМИРОВАНИЕ ОТЧЁТА")
    print("=" * 58)
    print(f"Записей в датасете: {movies_count}")
    print("LOO и тест устойчивости пересчитываются при выгрузке.\n")

    fresh_loo_mae = None
    loo_lines: list[str] = []
    noise_grid_result = None
    noise_lines: list[str] = []

    if movies_count >= 2 and linear_regression_train.is_method_available(
        linear_regression_train.BENCHMARK_METHOD
    ):
        print("--- LOO MAE (Ridge benchmark) ---")
        loo_lines, fresh_loo_mae = build_loo_per_record_lines(
            data,
            weights,
            progress_callback=_default_loo_progress,
        )
        if fresh_loo_mae is not None:
            print(f"LOO MAE готово: {fresh_loo_mae:.4f}\n")
        else:
            print("LOO MAE не рассчитан.\n")

        print("--- Устойчивость оценок (noise_experiment) ---")
        print(
            f"Delta: {', '.join(f'{value:.2f}' for value in REPORT_NOISE_DELTAS)} | "
            f"повторов: {REPORT_NOISE_RUNS}"
        )
        noise_grid_result = noise_experiment.run_noise_sensitivity_grid(
            data=data,
            weights=weights,
            deltas=REPORT_NOISE_DELTAS,
            runs=REPORT_NOISE_RUNS,
            seed=REPORT_NOISE_SEED,
            progress_callback=_default_noise_progress,
        )
        noise_lines = build_noise_sensitivity_lines(data, weights, grid_result=noise_grid_result)
        print("Устойчивость оценок: готово\n")
    else:
        loo_lines, fresh_loo_mae = build_loo_per_record_lines(data, weights)
        noise_lines = build_noise_sensitivity_lines(data, weights, grid_result=None)
        print("LOO / noise пропущены: мало данных или sklearn недоступен.\n")

    print("--- Сбор текстового отчёта ---")
    report_lines = build_train_report(
        data,
        weights,
        loo_lines=loo_lines,
        fresh_loo_mae=fresh_loo_mae,
        noise_lines=noise_lines,
    )

    reports_dir = os.path.join(constant.DIR_TXT, REPORTS_DIR_NAME)
    os.makedirs(reports_dir, exist_ok=True)

    file_name = "full_report_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
    file_path = os.path.join(reports_dir, file_name)

    with open(file_path, "w", encoding="UTF-8") as file:
        file.write("\n".join(report_lines))

    mae = model.mean_absolute_error(data, weights)
    print("")
    print("=" * 58)
    print("ОТЧЁТ СОХРАНЁН")
    print("=" * 58)
    print(f"Файл: {file_path}")
    print(f"Строк: {len(report_lines)}")
    print(f"Model MAE: {mae:.4f} | LOO MAE: {_format_optional(fresh_loo_mae)}")
    print("")
    print("Разделы:")
    print("  1. Датасет")
    print("  2. Модель и метрики")
    print("  3. LOO benchmark")
    print("  4. Тест устойчивости к шуму")
    print("  5. Веса модели")
    print("  6. Ошибки модели")
    print("=" * 58)
    return file_path


# Backward-compatible alias for older code expecting train_report_* filename prefix.
def get_error_rows(data: dict, weights: dict, limit: int = 10) -> list:
    """Возвращает строки с самыми большими ошибками модели."""
    return collect_all_error_rows(data, weights)[:limit]
