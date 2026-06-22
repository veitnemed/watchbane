"""Содержит действия интерфейса, которые запускаются из пунктов меню."""

import json
import os
import copy
from datetime import datetime
from pathlib import Path

from config import constant
from common import format_score as format
from candidates import candidate_pool
from candidates import country_schema
from candidates import genre_schema
from candidates import service as candidate_service
from candidates import tmdb_country_options
from candidates import tmdb_genre_options
from dataset import dataset_stats
from dataset import genre_import
from dataset import genre_stats
from dataset.dataset_records import update_dataset_record
from apis import imdb_sql as sql_search
from dataset import title_resolve
from model import linear_regression_train
from model import model
from ui.console import candidate_pool_ui
from ui.console import request
from ui.console import title_presenters
from storage import data as storage_data
from storage import files as storage_files
from dataset import storage_movie
from ui.console import ui
from common import valid


def _parse_user_score(value) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _try_parse_score(value) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _build_sorted_score_rows(data: dict) -> list[dict]:
    rows = []
    for dataset_title, movie in data.items():
        main_info = movie.get("main_info", {})
        title = main_info.get("title") or dataset_title
        score = _parse_user_score(main_info.get("user_score"))
        rows.append({
            "title": title,
            "score": score,
            "year": main_info.get("year"),
        })
    rows.sort(key=lambda row: (row["score"], str(row["title"]).casefold()))
    return rows


def build_linear_distribution_items(items: list[dict]) -> list[dict]:
    """Возвращает draft-строки с proposed_score без изменения dataset."""
    if len(items) == 0:
        return []

    scores = [_parse_user_score(item.get("score", item.get("user_score"))) for item in items]
    min_score = min(scores)
    max_score = max(scores)
    step = 0.0 if len(items) == 1 else (max_score - min_score) / (len(items) - 1)

    draft_items = []
    for index, item in enumerate(items, start=1):
        old_score = _parse_user_score(item.get("score", item.get("user_score")))
        proposed_score = old_score if len(items) == 1 else min_score + step * (index - 1)
        proposed_score = round(proposed_score, 4)
        draft_items.append({
            "position": index,
            "title": item["title"],
            "old_score": old_score,
            "proposed_score": proposed_score,
            "delta": round(proposed_score - old_score, 4),
        })
    return draft_items


def build_linear_distribution_draft(items: list[dict], created_at: str | None = None) -> dict:
    """Собирает JSON-структуру draft линейного распределения."""
    draft_items = build_linear_distribution_items(items)
    old_scores = [item["old_score"] for item in draft_items]
    return {
        "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
        "method": "linear_distribution",
        "min_score": min(old_scores) if old_scores else None,
        "max_score": max(old_scores) if old_scores else None,
        "count": len(draft_items),
        "items": draft_items,
    }


def save_linear_distribution_draft(draft: dict, drafts_dir: str | None = None) -> str:
    """Сохраняет draft JSON и возвращает путь к файлу."""
    target_dir = drafts_dir or constant.RATING_ORDER_DRAFTS_DIR
    os.makedirs(target_dir, exist_ok=True)
    file_name = f"rating_order_draft_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    file_path = os.path.join(target_dir, file_name)
    with open(file_path, "w", encoding="UTF-8") as file:
        json.dump(draft, file, ensure_ascii=False, indent=4)
    return file_path


def print_linear_distribution_preview(draft: dict, draft_path: str) -> None:
    """Печатает preview созданного draft."""
    changed_items = [item for item in draft["items"] if abs(item["delta"]) > 0]
    print(f"Draft сохранен: {draft_path}")
    print(f"Обработано записей: {draft['count']}")
    print(f"Оценок изменится в draft: {len(changed_items)}")
    print(f"min_score / max_score: {draft['min_score']} / {draft['max_score']}")

    print("\nTop-10 изменений по модулю delta:")
    top_changes = sorted(draft["items"], key=lambda item: abs(item["delta"]), reverse=True)[:10]
    if len(top_changes) == 0:
        print("Нет записей.")
        return
    for item in top_changes:
        print(
            f"{item['position']}) {item['title']} | "
            f"{item['old_score']} -> {item['proposed_score']} | "
            f"delta: {item['delta']:+.4f}"
        )


def create_linear_distribution_draft(rows: list[dict]) -> str:
    """Создает draft линейного распределения оценок и печатает preview."""
    draft = build_linear_distribution_draft(rows)
    draft_path = save_linear_distribution_draft(draft)
    print_linear_distribution_preview(draft, draft_path)
    return draft_path


def get_rating_order_draft_files(drafts_dir: str | None = None) -> list[Path]:
    """Возвращает draft-файлы от новых к старым."""
    target_dir = Path(drafts_dir or constant.RATING_ORDER_DRAFTS_DIR)
    if target_dir.exists() is False:
        return []
    draft_files = [
        path for path in target_dir.glob("rating_order_draft_*.json")
        if path.is_file()
    ]
    draft_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return draft_files


def load_rating_order_draft(path: str | Path) -> dict | None:
    """Загружает draft JSON."""
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            draft = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None
    return draft if isinstance(draft, dict) else None


def _find_dataset_title_in_data(data: dict, title: str) -> str | None:
    expected = str(title).strip().lower()
    for dataset_title in data.keys():
        if dataset_title.strip().lower() == expected:
            return dataset_title
    return None


def validate_rating_order_draft(draft: dict, data: dict) -> tuple[bool, str, list[dict]]:
    """Проверяет структуру draft и соответствие текущему dataset."""
    if draft.get("method") != "linear_distribution":
        return False, "Некорректный draft: method должен быть linear_distribution.", []
    items = draft.get("items")
    if isinstance(items, list) is False or len(items) == 0:
        return False, "Некорректный draft: отсутствует items.", []

    validated_items = []
    for item in items:
        if isinstance(item, dict) is False:
            return False, "Некорректный draft: item должен быть объектом.", []
        for field in ("title", "old_score", "proposed_score"):
            if field not in item:
                return False, f"Некорректный draft: отсутствует поле {field}.", []

        dataset_title = _find_dataset_title_in_data(data, item["title"])
        if dataset_title is None:
            return False, f"В dataset отсутствует запись из draft: {item['title']}", []

        current_score = _parse_user_score(data[dataset_title].get("main_info", {}).get("user_score"))
        old_score = _try_parse_score(item["old_score"])
        if old_score is None:
            return False, f"Некорректный old_score для {item['title']}.", []
        if abs(current_score - old_score) > 0.0001:
            return False, "Dataset изменился после создания draft. Создайте новый draft.", []

        proposed_score = _try_parse_score(item["proposed_score"])
        if proposed_score is None or valid.is_correct_score(str(proposed_score)) is False:
            return False, f"Некорректный proposed_score для {item['title']}.", []

        validated_item = dict(item)
        validated_item["title"] = dataset_title
        validated_item["old_score"] = old_score
        validated_item["proposed_score"] = proposed_score
        validated_item["delta"] = round(proposed_score - old_score, 4)
        validated_items.append(validated_item)

    return True, "", validated_items


def calculate_rating_order_loo_mae(data: dict) -> float | None:
    """Считает LOO MAE для draft-сценария без сохранения весов и metrics."""
    if linear_regression_train.is_method_available(linear_regression_train.BENCHMARK_METHOD) is False:
        return None
    return linear_regression_train.calculate_linear_loo_mae(
        data=data,
        method=linear_regression_train.BENCHMARK_METHOD,
        start_weights=storage_data.load_weights(),
        alpha=linear_regression_train.BENCHMARK_RIDGE_ALPHA,
        l1_ratio=0.5,
        max_iter=5000,
    )


def build_dataset_with_draft_scores(data: dict, items: list[dict]) -> dict:
    """Возвращает копию dataset с proposed_score из draft."""
    draft_data = copy.deepcopy(data)
    for item in items:
        draft_data[item["title"]]["main_info"]["user_score"] = item["proposed_score"]
    return draft_data


def build_rating_order_draft_preview(draft_path: str, data: dict, items: list[dict]) -> dict:
    """Собирает preview применения draft и LOO MAE до/после."""
    draft_data = build_dataset_with_draft_scores(data, items)
    current_loo_mae = calculate_rating_order_loo_mae(data)
    draft_loo_mae = calculate_rating_order_loo_mae(draft_data)
    changed_items = [item for item in items if abs(item["delta"]) > 0.0001]
    return {
        "draft_path": draft_path,
        "count": len(items),
        "changed_count": len(changed_items),
        "current_loo_mae": current_loo_mae,
        "draft_loo_mae": draft_loo_mae,
        "items": items,
    }


def _format_optional_loo(value: float | None) -> str:
    if value is None:
        return "не рассчитан"
    return f"{value:.4f}"


def print_rating_order_draft_apply_preview(preview: dict) -> None:
    """Печатает preview применения draft."""
    current_loo_mae = preview["current_loo_mae"]
    draft_loo_mae = preview["draft_loo_mae"]
    print(f"Draft: {preview['draft_path']}")
    print(f"Записей в draft: {preview['count']}")
    print(f"Оценок изменится: {preview['changed_count']}")
    print(f"current_loo_mae: {_format_optional_loo(current_loo_mae)}")
    print(f"draft_loo_mae: {_format_optional_loo(draft_loo_mae)}")
    if current_loo_mae is not None and draft_loo_mae is not None:
        delta = draft_loo_mae - current_loo_mae
        if abs(delta) < 0.00005:
            print("Разница LOO MAE: без изменений")
        elif delta < 0:
            print(f"Разница LOO MAE: улучшение {delta:.4f}")
        else:
            print(f"Разница LOO MAE: ухудшение +{delta:.4f}")

    print("\nTop-10 изменений по модулю delta:")
    top_changes = sorted(preview["items"], key=lambda item: abs(item["delta"]), reverse=True)[:10]
    for item in top_changes:
        print(
            f"{item.get('position', '-')}) {item['title']} | "
            f"{item['old_score']} -> {item['proposed_score']} | "
            f"delta: {item['delta']:+.4f}"
        )


def apply_rating_order_draft_items(items: list[dict]) -> dict:
    """Применяет draft через update_dataset_record()."""
    updated = 0
    skipped = 0
    errors = []
    for item in items:
        if abs(item["delta"]) <= 0.0001:
            skipped += 1
            continue
        result = update_dataset_record(
            item["title"],
            {"main_info": {"user_score": item["proposed_score"]}},
            source_name="rating_order_draft",
        )
        if result.ok:
            updated += 1
        else:
            skipped += 1
            errors.append(result)
    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


def choose_rating_order_draft_file() -> Path | None:
    """Показывает список draft-файлов и возвращает выбранный путь."""
    draft_files = get_rating_order_draft_files()
    if len(draft_files) == 0:
        print("Draft-файлы распределения оценок не найдены.")
        return None

    print("\nDraft-файлы распределения оценок:\n")
    for idx, file_path in enumerate(draft_files, start=1):
        changed_at = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{idx}) {file_path.name} | {changed_at}")
    print("0) Назад")

    selected = request.loop_input(
        text="\nВыберите draft >> ",
        funcs_list=[lambda value: value.isdigit() and 0 <= int(value) <= len(draft_files)],
    )
    if selected == "0":
        return None
    return draft_files[int(selected) - 1]


def apply_rating_order_draft_flow(input_func=input) -> bool:
    """Выбирает, проверяет и применяет draft распределения оценок после LOO preview."""
    draft_path = choose_rating_order_draft_file()
    if draft_path is None:
        return False

    draft = load_rating_order_draft(draft_path)
    if draft is None:
        print("Некорректный draft JSON.")
        return False

    data = storage_data.load_dataset()
    ok, message, items = validate_rating_order_draft(draft, data)
    if ok is False:
        print(message)
        return False

    preview = build_rating_order_draft_preview(str(draft_path), data, items)
    print_rating_order_draft_apply_preview(preview)
    answer = input_func("\nПрименить draft к dataset? [y/N] ").strip().casefold()
    if answer not in {"y", "yes", "д", "да"}:
        print("Применение отменено.")
        return False

    storage_files.create_backup()
    result = apply_rating_order_draft_items(items)
    print("\nDraft применён.")
    print(f"Обновлено записей: {result['updated']}")
    print(f"Пропущено записей: {result['skipped']}")
    print(f"Применённый draft: {draft_path}")
    print(f"LOO MAE до: {_format_optional_loo(preview['current_loo_mae'])}")
    print(f"LOO MAE после: {_format_optional_loo(preview['draft_loo_mae'])}")
    if len(result["errors"]) > 0:
        print("Часть записей не обновлена:")
        for error in result["errors"]:
            print(f"- {error.title}: {error.message}")
    print("Оценки изменены. Запустите LOO обучение отдельно.")
    return True


def show_all_movies():
    """Показывает все фильмы из датасета."""
    data = storage_data.load_dataset()
    if len(data) == 0:
        print('Датасет пуст!')
        return

    rows = _build_sorted_score_rows(data)
    for idx, row in enumerate(rows, start=1):
        year_text = f" | год: {row['year']}" if row.get("year") not in (None, "") else ""
        print(f"{idx}) {row['title']} | user_score: {row['score']}{year_text}")

    open_scores_actions_menu(rows)


def open_scores_actions_menu(rows: list[dict]) -> None:
    """Открывает действия после просмотра оценок."""
    print("\n 5 >> Линейное распределение оценок")
    print(" 6 >> Изменить оценку user_score")
    print(" 7 >> Изменить название")
    print(" 8 >> Главное меню")
    print(" 9 >> Применить draft распределения оценок\n")

    command = request.loop_input(
        text=">> ",
        funcs_list=[lambda value: value in {"5", "6", "7", "8", "9"}],
    )
    if command == "5":
        create_linear_distribution_draft(rows)
    elif command == "6":
        change_user_score_from_rows(rows)
    elif command == "7":
        rename_movie_record()
    elif command == "9":
        apply_rating_order_draft_flow()


def change_user_score_from_rows(rows: list[dict]) -> None:
    """Меняет user_score через безопасный update-service."""
    selected_index = request.loop_input(
        text="Номер записи >> ",
        funcs_list=[lambda value: value.isdigit() and 1 <= int(value) <= len(rows)],
    )
    row = rows[int(selected_index) - 1]
    new_score = request.loop_input(
        text=f"Новая оценка user_score для {row['title']} >> ",
        funcs_list=[valid.is_correct_score],
    )
    result = update_dataset_record(
        row["title"],
        {"main_info": {"user_score": valid.parse_float(new_score)}},
        source_name="scores_menu",
    )
    print(result.message)


def get_predict(weights: dict) -> None:
    """Запрашивает признаки и показывает прогноз модели."""
    defaults = request.request_api_defaults()
    if defaults is None:
        return

    title = defaults["main_info"]["title"]
    features = request.request_predict_features(defaults)
    score = model.predict_score(features, weights)
    print(f'Оценка модели для {title}: {score}')


def request_object() -> None:
    """Запрашивает фильм и добавляет его в датасет."""
    ui.clean_terminal()

    defaults = request.request_api_defaults(confirm_genres=True)
    if defaults is None:
        return

    movie_request = request.request_all_scores(defaults)
    result = storage_movie.add_movie(movie_request, print_message=False)
    print(result.message)


def mark_candidate_as_watched() -> None:
    """Переносит кандидата из пула в основной датасет через обычный сценарий добавления."""
    ui.clean_terminal()
    selected = candidate_pool_ui.choose_existing_criteria()
    if selected is None:
        return

    criteria_name, criteria = selected
    watched_view = candidate_service.get_mark_watched_view(criteria_name)
    candidates = watched_view["candidates"]

    print(f"\nПулл кандидатов: {criteria_name}")
    print(f"Страна: {criteria.get('country')}")
    for line in watched_view["lines"]:
        print(line)
    print("")

    if len(candidates) == 0:
        print("Для этого набора критериев кандидатов пока нет.")
        return

    for idx, candidate in enumerate(candidates, start=1):
        title = candidate.get("title") or "Без названия"
        year = candidate.get("year") or "?"
        description = request.short_text(candidate.get("description"), 50) or "без описания"
        print(f"{idx}) {title} ({year})")
        print(f"   Описание: {description}")

    selected_index = request.loop_input(
        text="\nНомер просмотренного кандидата >> ",
        funcs_list=[lambda value: value.isdigit() and 1 <= int(value) <= len(candidates)]
    )
    candidate = candidates[int(selected_index) - 1]

    print("")
    transfer_payload = title_resolve.build_candidate_transfer_payload(candidate)
    defaults = transfer_payload["defaults"]
    meta_payload = transfer_payload["meta_payload"]
    if candidate_service.is_pool_candidate_incomplete(candidate):
        print("Кандидат неполный: нет KP/IMDb данных.")
        print("Можно продолжить вручную, но проверь raw_scores.\n")
    movie_request = request.request_all_scores(defaults)
    result = storage_movie.add_movie(
        movie_request,
        meta_payload=meta_payload,
        pool_candidate=candidate,
        print_message=False,
    )
    print(result.message)


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
    model.reset_weights()
    print('Веса сброшены на значения по умолчанию.')


def votes_impact():
    """Показывает влияние количества голосов на популярность."""
    data = storage_data.load_meta()
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
    data = storage_data.load_dataset()
    if len(data) == 0:
        print('Датасет пуст!')
        return

    groups = [
        ("Количественные", [constant.BIAS_FEATURE] + constant.COMPUTED_SCORES),
        ("Вайб", constant.TAGS_VIBE),
        ("Жанры", constant.GENRE),
    ]

    feature_rows = {}
    for feature in constant.FEATURES:
        weights_without_feature = model.selection_weights_without_feature(data, feature, weights)
        error_without_feature = model.mean_absolute_error(data, weights_without_feature)
        feature_rows[feature] = {
            "label": constant.FIELD_LABELS.get(feature, feature),
            "error_without_feature": error_without_feature,
            "delta": error_without_feature - full_error,
        }

    from model import linear_regression_train

    print('Оценка вклада признаков\n')
    print(f"Метод обучения для benchmark: {linear_regression_train.BENCHMARK_METHOD_LABEL}")
    print(f"Текущая ошибка полной модели: {round(full_error * 10, 2)} %\n")

    for group_title, features in groups:
        rows = [
            (feature, feature_rows[feature])
            for feature in features
            if feature in feature_rows
        ]
        rows.sort(key=lambda item: item[1]["delta"], reverse=True)

        print(group_title)
        print('-' * len(group_title))

        if len(rows) == 0:
            print('Нет признаков.\n')
            continue

        for feature, row in rows:
            print(
                f"{row['label']} ({feature}) | "
                f"ошибка без признака: {row['error_without_feature'] * 10:.2f} % | "
                f"вклад: {row['delta']:.4f}"
            )

        group_delta = sum(row["delta"] for _, row in rows)
        group_avg = group_delta / len(rows)
        print(f"Итого по группе: {group_delta:.4f}")
        print(f"Средний вклад: {group_avg:.4f}\n")


def show_data_info():
    """Показывает сводку по датасету."""
    data = storage_data.load_dataset()
    for line in dataset_stats.build_dataset_info_lines(data):
        print(line)


def rename_movie_record() -> None:
    """Переименовывает запись в основном датасете и meta."""
    ui.clean_terminal()
    titles = storage_data.get_all_titles()
    if len(titles) == 0:
        print("Датасет пуст!")
        return

    print("Текущие записи:\n")
    for idx, title in enumerate(titles, start=1):
        print(f"{idx}) {title}")

    old_title = request.loop_input(
        text="\nСтарое название >> ",
        funcs_list=[valid.is_correct_title]
    )
    new_title = request.loop_input(
        text="Новое название >> ",
        funcs_list=[valid.is_correct_title]
    )

    if storage_data.rename_movie_title(old_title, new_title):
        print("Название записи обновлено.")
    else:
        print("Переименование не выполнено.")


def load_genre_markup():
    """Загружает жанровую разметку для текущего датасета с подтверждением."""
    ui.clean_terminal()
    result = genre_import.apply_genre_markup()
    print(f"\nОбработано записей: {result['total']}")
    print(f"Подтверждено: {result['updated']}")
    print(f"Пропущено: {result['skipped']}")
    print(f"Не найдено: {len(result['not_found'])}")
    print(f"Ошибок API: {len(result['errors'])}")


def show_api_features():
    """Ищет сериал через API и печатает полный JSON найденного объекта."""
    title = request.loop_input(
        text='Название сериала >> ',
        funcs_list=[valid.is_correct_title]
    )
    result = title_resolve.fetch_series_raw(title, "Россия")

    if result["ok"] is False:
        print(f'Сериал не найден в списке API: {result["details"]}')
        return

    print('\nСериал найден в списке API.\n')
    for line in title_resolve.format_series_lines(result["data"]):
        print(line)


def print_sql_title_result(data: dict) -> None:
    """Печатает компактную карточку результата SQL-поиска."""
    title_presenters.print_sql_title_result(data)


def search_sql_title_by_name() -> None:
    """Ищет тайтл в локальной SQLite-базе IMDb по названию."""
    title = request.loop_input(
        text="Название >> ",
        funcs_list=[lambda value: str(value).strip() != ""]
    )
    country = request.loop_input_with_default(
        text="Страна [Россия] >> ",
        funcs_list=[lambda value: str(value).strip() != ""],
        default_value="Россия"
    )
    result = sql_search.search_title_in_sql(title, country)

    if result["ok"] is False:
        print(f"Тайтл не найден: {result['details'] or result['error']}")
        return

    print_sql_title_result(result["data"])


def show_dataset_genres() -> None:
    """Показывает все жанры текущего датасета через API."""
    ui.clean_terminal()
    genre_stats.show_dataset_genres()


def collect_candidate_pool() -> None:
    """Собирает пул кандидатов по сохраненным критериям."""
    ui.clean_terminal()
    selected = candidate_pool_ui.choose_or_create_criteria()
    if selected is None:
        print("Критерии не выбраны.")
        return

    criteria_name, criteria = selected
    print(f"\nЗапуск подбора по критериям: {criteria_name}")
    result = candidate_pool.collect_candidates(criteria_name, criteria)

    print("\nСбор пула кандидатов завершён.")
    print(f"Набор критериев: {result['criteria_name']}")
    print(f"Нужно было собрать: {result['target_count']}")
    print(f"Новых кандидатов добавлено: {result['added']}")
    print(f"Совпадений уже в JSON: {result['duplicates']}")
    print(f"Уже есть в основном датасете: {result['watched_skipped']}")
    print(f"Проверено объектов API: {result['scanned']}")
    print(f"Последняя страница: {result['last_page']}")
    print(f"Текущий размер пула: {result['pool_size']}")

    if result.get("api_unavailable"):
        print("API сейчас недоступен. Общий пул сохранён без изменений.")

    if result["reached_end"]:
        print("Выдача API закончилась раньше, чем набралось нужное количество.")

    if len(result["errors"]) > 0:
        print("Ошибки API/сети:")
        for error in result["errors"]:
            print(f"- {error}")


def _parse_bounded_int(value: str, default: int, min_value: int, max_value: int) -> int:
    try:
        number = int(str(value or "").strip())
    except ValueError:
        number = default
    return max(min_value, min(number, max_value))


def _parse_optional_bounded_int(value: str, min_value: int, max_value: int) -> int | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        number = int(text)
    except ValueError:
        return None
    return max(min_value, min(number, max_value))


def _parse_optional_bounded_float(value: str, min_value: float, max_value: float) -> float | None:
    text = str(value or "").strip().replace(",", ".")
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return max(min_value, min(number, max_value))


def _parse_iso_country_code(value: str) -> str | None:
    country = str(value or "").strip().upper()
    if len(country) == 2 and country.isascii() and country.isalpha():
        return country
    return None


def _print_tmdb_country_options(output_func=print) -> None:
    options = tmdb_country_options.country_options()
    parts = [
        f"{index}. {option['label']}"
        for index, option in enumerate(options, start=1)
    ]
    output_func("Список:")
    for start in range(0, len(parts), 5):
        output_func("; ".join(parts[start:start + 5]))


def request_tmdb_country_codes(input_func=input, output_func=print) -> list[str]:
    output_func("Введите номера стран, по которым будет производиться поиск:")
    _print_tmdb_country_options(output_func=output_func)
    while True:
        answer = input_func(">> ").strip()
        countries = tmdb_country_options.parse_country_indexes(answer)
        if countries is None or len(countries) == 0:
            output_func("Введите номера стран из списка через запятую, например: 1 или 1,2,3.")
            continue
        return countries


def _fit_title(title: str, width: int = 32) -> str:
    """Ограничивает ширину названия, чтобы строка Top-20 не переносилась в узкой консоли."""
    text = str(title or "Без названия")
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text.ljust(width)


def _print_tmdb_candidate_top(candidates: list, limit: int = 20) -> None:
    print("\nTop-20 TMDb candidate_pool:\n")
    for index, candidate in enumerate(candidates[:limit], start=1):
        final_score = float(candidate.get("final_score") or 0)
        country_score = float(candidate.get("country_score") or 0)
        print(
            f"{index:>2}. {_fit_title(candidate.get('title'))} | "
            f"final={final_score:.3f} | "
            f"country={country_score:.2f} | "
            f"TMDb={candidate.get('tmdb_rating') or '-'}/{candidate.get('tmdb_votes') or 0} | "
            f"IMDb={candidate.get('imdb_rating') or '-'}/{candidate.get('imdb_votes') or 0}"
        )


def _print_tmdb_candidate_test_details(candidates: list, limit: int = 5) -> None:
    print("\nКандидаты test-run:\n")
    for index, candidate in enumerate(candidates[:limit], start=1):
        print(f"{index}. {candidate.get('title') or 'Без названия'}")
        print(f"   TMDb: {candidate.get('tmdb_score') or candidate.get('tmdb_rating') or '-'} / {candidate.get('tmdb_votes') or 0}")
        print(f"   IMDb: {candidate.get('imdb_score') or candidate.get('imdb_rating') or '-'} / {candidate.get('imdb_votes') or 0}")
        print(f"   KP: {candidate.get('kp_status') or 'not_requested'}")
        print(f"   KP score: {candidate.get('kp_score') or candidate.get('kp_rating') or '-'} / {candidate.get('kp_votes') or 0}")
        print(f"   signals: {', '.join(candidate.get('signals') or []) or 'нет'}\n")


def _print_tmdb_candidate_stats(result: dict) -> None:
    stats = result.get("stats") or {}
    discover_filters = stats.get("discover_filters") or {}
    print("\nСтатистика TMDb candidate_pool:")
    print("TMDb Discover filters:")
    print(f"Минимальный год: {discover_filters.get('year_min') if discover_filters.get('year_min') is not None else 'не важно'}")
    print(f"Максимальный год: {discover_filters.get('year_max') if discover_filters.get('year_max') is not None else 'не важно'}")
    print(f"Минимальный TMDb рейтинг: {discover_filters.get('min_tmdb_score') if discover_filters.get('min_tmdb_score') is not None else 'не важно'}")
    print(f"Минимум голосов TMDb: {discover_filters.get('min_tmdb_votes') if discover_filters.get('min_tmdb_votes') is not None else 'не важно'}")
    print(f"Include жанры (TMDb): {tmdb_genre_options.describe_filter_value(discover_filters.get('with_genres'))}")
    print(f"Exclude жанры (TMDb): {tmdb_genre_options.describe_filter_value(discover_filters.get('without_genres'))}")
    print(f"Найдено через TMDb Discover: {stats.get('discover_total', 0)}")
    print(f"Удалено дублей: {stats.get('duplicates_removed', 0)}")
    print(f"Пропущено уже просмотренных: {stats.get('watched_skipped', 0)}")
    print(f"Запрошено TMDb Details: {stats.get('details_requested', 0)}")
    print(f"TMDb Details ошибок сети: {stats.get('tmdb_details_errors', 0)}")
    print(f"TMDb Details пропущено после ошибок: {stats.get('tmdb_details_skipped_after_errors', 0)}")
    print(f"С IMDb ID: {stats.get('has_imdb_id', 0)}")
    print(f"Найдено в IMDb dataset: {stats.get('found_in_imdb_sql', 0)}")
    print(f"KP найдено в кэше: {stats.get('kp_cache_hit', 0)}")
    print(f"KP API запросов: {stats.get('kp_api_requested', 0)}")
    print(f"KP API найдено: {stats.get('kp_api_found', 0)}")
    print(f"KP API не найдено: {stats.get('kp_api_not_found', 0)}")
    print(f"KP API отклонено match-check: {stats.get('kp_api_rejected_by_match', 0)}")
    print(f"KP API ошибок: {stats.get('kp_api_errors', 0)}")
    print(f"KP API пропущено после ошибок: {stats.get('kp_api_skipped_after_errors', 0)}")
    print(f"KP API пропущено из-за кэша: {stats.get('kp_api_skipped_cache', 0)}")
    print(f"KP ожидает добора из-за лимита: {stats.get('kp_pending_limit', 0)}")
    print(f"Неполных кандидатов по KP: {stats.get('kp_incomplete_candidates', 0)}")
    print(f"Полностью обогащённых кандидатов: {stats.get('complete_candidates', 0)}")
    print(f"Прошли country_score: {stats.get('country_passed', 0)}")
    print(f"Отклонено adult/titleType: {stats.get('adult_title_type_rejected', 0)}")
    print(f"Итоговых кандидатов: {stats.get('final_candidates', 0)}")


def _tmdb_mode_label(mode: str) -> str:
    labels = {
        "quality": "поиск по популярным",
        "hidden_gems": "поиск по недооценённым",
    }
    return labels.get(mode, mode)


def _parse_tmdb_genre_indexes(value: str, options: list[dict] | None = None) -> list[int] | None:
    text = str(value or "").strip()
    if text in {"", "0"}:
        return []
    options = options or tmdb_genre_options.TV_GENRE_OPTIONS
    indexes = []
    for part in text.replace(",", " ").split():
        try:
            index = int(part)
        except ValueError:
            return None
        if index < 1 or index > len(options):
            return None
        if index not in indexes:
            indexes.append(index)
    return indexes


def _print_tmdb_genre_options(options: list[dict], output_func=print) -> None:
    for index, option in enumerate(options, start=1):
        output_func(f" {index} >> {option['label']}")


def _input_tmdb_genre_ids(
    label: str,
    options: list[dict],
    *,
    allow_all: bool = False,
    input_func=input,
    output_func=print,
) -> list[int]:
    while True:
        answer = input_func(f"{label} [0] >> ").strip()
        if allow_all and answer.casefold() in {"все", "all", "*"}:
            return [int(option["id"]) for option in options]
        indexes = _parse_tmdb_genre_indexes(answer, options)
        if indexes is None:
            if allow_all:
                output_func("Введите номера жанров через запятую, например: 1,2,3, или все.")
            else:
                output_func("Введите номера жанров через запятую, например: 1,2,3")
            continue
        return tmdb_genre_options.genre_ids_from_indexes(indexes, options)


def _input_tmdb_include_mode(input_func=input, output_func=print) -> str:
    output_func("\nКак применять выбранные жанры (TMDb)?")
    output_func(" 1 >> Любой из выбранных жанров — шире поиск")
    output_func(" 2 >> Все выбранные жанры одновременно — строже поиск")
    while True:
        answer = input_func("Выбор [1] >> ").strip()
        if answer in {"", "1"}:
            return tmdb_genre_options.MODE_OR
        if answer == "2":
            return tmdb_genre_options.MODE_AND
        output_func("Выберите 1 или 2.")


def request_tmdb_discover_genre_filters(input_func=input, output_func=print) -> tuple[str | None, str | None]:
    output_func(f"\n{tmdb_genre_options.TMDB_DISCOVER_GENRE_TITLE}")
    output_func("Выбери жанры, которые должны попасть в поиск:")
    output_func(" 0 >> без include-фильтра")
    _print_tmdb_genre_options(tmdb_genre_options.INCLUDE_TV_GENRE_OPTIONS, output_func)
    output_func("\nВвод через запятую, например 1,2,3.")
    include_ids = _input_tmdb_genre_ids(
        "Include жанры",
        tmdb_genre_options.INCLUDE_TV_GENRE_OPTIONS,
        input_func=input_func,
        output_func=output_func,
    )

    include_mode = tmdb_genre_options.MODE_OR
    if len(include_ids) > 1:
        include_mode = _input_tmdb_include_mode(input_func=input_func, output_func=output_func)
    with_genres = tmdb_genre_options.build_filter_value(include_ids, mode=include_mode)
    include_labels = ", ".join(tmdb_genre_options.labels_from_ids(include_ids)) if include_ids else "без фильтра"
    mode_label = "любой из выбранных" if include_mode == tmdb_genre_options.MODE_OR else "все выбранные одновременно"
    output_func(f"Include жанры (TMDb): {include_labels}")
    if len(include_ids) > 1:
        output_func(f"Режим: {mode_label}")

    output_func(f"\n{tmdb_genre_options.TMDB_EXCLUDE_LABEL}")
    output_func("Выбери жанры, которые нужно исключить:")
    output_func(" 0 >> без exclude-фильтра")
    output_func(" все >> все перечисленные exclude-жанры")
    _print_tmdb_genre_options(tmdb_genre_options.EXCLUDE_TV_GENRE_OPTIONS, output_func)
    output_func("\nВвод через запятую, например 1,2,3,4. Можно ввести все.")
    exclude_ids = _input_tmdb_genre_ids(
        "Exclude жанры",
        tmdb_genre_options.EXCLUDE_TV_GENRE_OPTIONS,
        allow_all=True,
        input_func=input_func,
        output_func=output_func,
    )
    without_genres = tmdb_genre_options.build_filter_value(exclude_ids, mode=tmdb_genre_options.MODE_OR)
    exclude_labels = ", ".join(tmdb_genre_options.labels_from_ids(exclude_ids)) if exclude_ids else "без фильтра"
    output_func(f"Exclude жанры (TMDb): {exclude_labels}")
    return with_genres, without_genres


def ask_auto_import_choice(input_func=input, output_func=print) -> bool:
    """Спрашивает, нужно ли сразу импортировать TMDb result в общий пул."""
    while True:
        answer = str(
            input_func("Импортировать результат в общий пул кандидатов? [Y/n] >> ")
        ).strip().casefold()
        if answer in {"", "y", "yes", "д", "да"}:
            return True
        if answer in {"n", "no", "н"}:
            return False
        output_func("Неверный ввод. Используйте Enter/Y для импорта или N для отмены.")


def _print_tmdb_import_stats(stats: dict, output_func=print) -> None:
    """Печатает статистику импорта TMDb result в общий candidate pool."""
    skipped_watched = stats.get("skipped_watched", stats.get("watched_skipped", 0))
    skipped_duplicates = stats.get("skipped_duplicates", stats.get("duplicates", 0))

    output_func(f"Прочитано: {stats.get('read', 0)}")
    output_func(f"Добавлено новых: {stats.get('added', 0)}")
    output_func(f"Обновлено существующих: {stats.get('updated', 0)}")
    output_func(f"Пропущено already watched: {skipped_watched}")
    output_func(f"Пропущено как дубли: {skipped_duplicates}")
    output_func(f"Ошибок: {stats.get('errors', 0)}")
    output_func(f"Размер пула до импорта: {stats.get('pool_size_before', 0)}")
    output_func(f"Размер пула после импорта: {stats.get('pool_size_after', stats.get('pool_size', 0))}")
    output_func(f"criteria_name: {stats.get('criteria_name') or '-'}")


def maybe_auto_import_tmdb_result(
    result_path,
    criteria_name: str,
    *,
    input_func=input,
    output_func=print,
    import_func=None,
):
    """Предлагает авто-импорт сохранённого TMDb result в общий candidate pool."""
    if ask_auto_import_choice(input_func=input_func, output_func=output_func) is False:
        output_func("Импорт отменён. Result сохранён, его можно импортировать позже через управление пуллами.")
        return None

    if import_func is None:
        def import_func(result_path, criteria_name=None):
            return candidate_service.import_tmdb_result_to_pool(result_path, criteria_name=criteria_name)

    try:
        import_result = import_func(result_path, criteria_name=criteria_name)
    except Exception as error:
        output_func(f"Авто-импорт не выполнен: {error}")
        output_func("Result сохранён, его можно импортировать позже через управление пуллами.")
        return None

    if isinstance(import_result, dict) and "stats" in import_result:
        if import_result.get("ok") is False:
            error_text = import_result.get("error") or "неизвестная ошибка"
            output_func(f"Авто-импорт не выполнен: {error_text}")
            output_func("Result сохранён, его можно импортировать позже через управление пуллами.")
            return import_result
        stats = import_result["stats"]
    else:
        stats = import_result

    if isinstance(stats, dict) is False or stats.get("ok") is False:
        error_text = stats.get("error") if isinstance(stats, dict) else "неизвестная ошибка"
        output_func(f"Авто-импорт не выполнен: {error_text}")
        output_func("Result сохранён, его можно импортировать позже через управление пуллами.")
        return stats

    output_func("\nИмпорт TMDb result завершён.")
    _print_tmdb_import_stats(stats, output_func=output_func)
    return stats


def run_tmdb_candidate_pool_flow(is_test_run: bool = False) -> None:
    """Запускает новый TMDb candidate_pool v1 без смешивания со старым общим пулом."""
    from pathlib import Path

    from apis import imdb_sql as sql_search

    ui.clean_terminal()
    print("TMDb candidate_pool v1\n")
    country_codes = request_tmdb_country_codes(input_func=input, output_func=print)
    if len(country_codes) > 1:
        print("Пока один запуск TMDb candidate_pool поддерживает одну страну. Выберите один номер.")
        return
    country = country_codes[0]

    print("\nРежим:")
    print("1 >> Поиск по популярным")
    print("2 >> Поиск по недооценённым")
    mode_answer = input("Выбор [1] >> ").strip()
    if mode_answer in ("", "1"):
        mode = "quality"
    elif mode_answer == "2":
        mode = "hidden_gems"
    else:
        print("Ошибка: выберите 1 или 2.")
        return

    criteria_answer = input("\nНазвание пулла / criteria_name [auto] >> ").strip()

    if is_test_run:
        pages = 1
        details_answer = input("\nСколько кандидатов детально обработать в test-run [5] >> ").strip()
        details_limit = _parse_bounded_int(details_answer, default=5, min_value=1, max_value=300)
    else:
        pages_answer = input("\nСколько страниц TMDb Discover? По умолчанию 3: ").strip()
        pages = _parse_bounded_int(pages_answer, default=3, min_value=1, max_value=20)
        details_answer = input("Сколько кандидатов отправить в TMDb Details? По умолчанию 50: ").strip()
        details_limit = _parse_bounded_int(details_answer, default=50, min_value=1, max_value=300)

    year_min = _parse_optional_bounded_int(input("\nМинимальный год [не важно] >> ").strip(), 1900, constant.NOW_YEAR)
    year_max = _parse_optional_bounded_int(input("Максимальный год [не важно] >> ").strip(), 1900, constant.NOW_YEAR)
    min_tmdb_score = _parse_optional_bounded_float(input("Минимальный TMDb рейтинг [не важно] >> ").strip(), 0.0, 10.0)
    min_tmdb_votes = _parse_optional_bounded_int(input("Минимум голосов TMDb [не важно] >> ").strip(), 0, 10_000_000)
    with_genres, without_genres = request_tmdb_discover_genre_filters(input_func=input, output_func=print)
    criteria_name = criteria_answer or candidate_service.build_tmdb_criteria_name(
        country,
        mode,
        year_min=year_min,
        min_tmdb_score=min_tmdb_score,
    )

    print("\nБудет запущен TMDb candidate_pool v1:\n")
    print(f"Название пулла: {criteria_name}")
    print(f"Страна: {country}")
    print(f"Режим: {_tmdb_mode_label(mode)}")
    if is_test_run:
        print("Режим запуска: тестовый прогон")
    print(f"Страниц TMDb Discover: {pages}")
    print(f"Лимит TMDb Details: {details_limit}")
    print(f"Минимальный год: {year_min if year_min is not None else 'не важно'}")
    print(f"Максимальный год: {year_max if year_max is not None else 'не важно'}")
    print(f"Минимальный TMDb рейтинг: {min_tmdb_score if min_tmdb_score is not None else 'не важно'}")
    print(f"Минимум голосов TMDb: {min_tmdb_votes if min_tmdb_votes is not None else 'не важно'}")
    print(f"Include жанры (TMDb): {tmdb_genre_options.describe_filter_value(with_genres)}")
    print(f"Exclude жанры (TMDb): {tmdb_genre_options.describe_filter_value(without_genres)}")
    print("KP API: включён после локального KP cache, при ошибке сбор продолжается без KP.")
    if is_test_run:
        print("\nПлан тестового режима:")
        print(f"Лимит TMDb Details: {details_limit}")
        print(f"Будет детально обработано не больше {details_limit} кандидатов.")
        print("Основной candidate_pool_RU_quality.json не будет перезаписан.")

    confirmation = input("\nПродолжить? [y/N]: ").strip().casefold()
    if confirmation not in {"y", "yes", "д", "да"}:
        print("Операция отменена.")
        return

    if Path(sql_search.DEFAULT_DB_PATH).is_file() is False:
        print("Ошибка: не найдена локальная IMDb SQLite база. Проверь путь в настройках.")
        return

    try:
        result = candidate_service.build_tmdb_candidate_pool(
            country=country,
            pages=pages,
            details_limit=details_limit,
            mode=mode,
            criteria_name=criteria_name,
            year_min=year_min,
            year_max=year_max,
            min_tmdb_score=min_tmdb_score,
            min_tmdb_votes=min_tmdb_votes,
            with_genres=with_genres,
            without_genres=without_genres,
        )
        if is_test_run:
            print("Сохранение test candidate_pool: Ожидание")
            save_result = candidate_service.save_tmdb_build_result(result, is_test_run=True)
            print("Сохранение test candidate_pool: Успешно")
        else:
            print("Сохранение candidate_pool: Ожидание")
            save_result = candidate_service.save_tmdb_build_result(result, is_test_run=False)
            print("Сохранение candidate_pool: Успешно")
        json_path = save_result["json_path"]
        csv_path = save_result["csv_path"]
    except RuntimeError as error:
        text = str(error)
        if "TMDB_TOKEN" in text:
            print("Ошибка: не найден TMDB_TOKEN. Проверь .env / переменные окружения.")
        elif "TMDB" in text or "getaddrinfo" in text or "подключиться" in text:
            print("Ошибка доступа к TMDb. Если кэш есть, проверь, может ли генератор работать из кэша.")
            print(text)
        else:
            print(f"Ошибка: {text}")
        return
    except OSError as error:
        print(f"Ошибка файловой системы: {error}")
        return

    if is_test_run:
        print("\nТестовый прогон завершён.")
        print(f"Основной candidate_pool_{country}_{mode}.json не изменялся.")
        print(f"Файл тестового результата: {json_path}")
        stats = result.get("stats") or {}
        print("\nТестовый режим:")
        print(f"Найдено через TMDb Discover: {stats.get('discover_total', 0)}")
        print(f"Лимит TMDb Details: {details_limit}")
        print(f"Будет детально обработано не больше {details_limit} кандидатов.")
    else:
        print("\nTMDb candidate_pool v1 готов.")
    if is_test_run is False:
        print(f"TMDb result сохранён: {json_path}")
        maybe_auto_import_tmdb_result(json_path, criteria_name)
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    _print_tmdb_candidate_stats(result)

    kp_debug = result.get("kp_debug")
    if isinstance(kp_debug, dict):
        from candidates import kp_tmdb_build_debug

        for line in kp_tmdb_build_debug.format_kp_debug_lines(kp_debug):
            print(line)
        debug_path = json_path.with_name(f"{json_path.stem}_kp_debug.json")
        if debug_path.is_file():
            print(f"KP debug JSON: {debug_path}")

    candidates = result.get("candidates") or []
    if len(candidates) > 0:
        if is_test_run:
            _print_tmdb_candidate_test_details(candidates)
        else:
            _print_tmdb_candidate_top(candidates)
    else:
        print("Итоговый список кандидатов пуст.")


def show_tmdb_dataset_genre_diagnostics() -> None:
    """Показывает и сохраняет распределение TMDb TV-жанров по текущему dataset."""
    from candidates.tmdb_candidate_pool import (
        build_tmdb_genre_distribution_report,
        save_tmdb_genre_distribution_report,
    )

    ui.clean_terminal()
    dataset = storage_data.load_dataset()
    meta = storage_data.load_meta()
    if len(dataset) == 0:
        print("Dataset пуст. Диагностика жанров недоступна.")
        return

    print("TMDb genre distribution for dataset:\n")
    print("Будут выполнены TMDb details/search запросы с использованием локального кэша, если он есть.")
    answer = input("Продолжить? [y/N] ").strip().casefold()
    if answer not in {"y", "yes", "д", "да"}:
        print("Операция отменена.")
        return

    def print_progress(event: dict) -> None:
        index = event.get("index")
        total = event.get("total")
        title = event.get("title") or "-"
        year = event.get("year") or "-"
        status = event.get("status")
        if status == "start":
            print(f"[{index}/{total}] {title} ({year}): поиск TMDb...")
            return

        if status == "matched":
            genres = ", ".join(event.get("genres") or []) or "жанры пустые"
            print(f"[{index}/{total}] {title} ({year}): найдено, жанры={genres}")
        elif status == "error":
            print(f"[{index}/{total}] {title} ({year}): ошибка {event.get('error')}")
        elif status == "stopped":
            print(f"\n{event.get('error')}")
            print("Проверьте доступ к TMDb/VPN/сеть и запустите диагностику позже.")
        else:
            print(f"[{index}/{total}] {title} ({year}): не найдено")

    try:
        report = build_tmdb_genre_distribution_report(dataset, meta, progress_callback=print_progress)
        report_path = save_tmdb_genre_distribution_report(report)
    except RuntimeError as error:
        print(f"Ошибка TMDb: {error}")
        return
    except OSError as error:
        print(f"Ошибка файловой системы: {error}")
        return

    print("\nTMDb genre distribution for dataset:\n")
    if report["genre_counts"]:
        for genre_name, count in report["genre_counts"].items():
            print(f"{genre_name}: {count}")
    else:
        print("Жанры не найдены.")

    print("\nИтог:")
    print(f"Обработано записей: {report['total_dataset_items']}")
    print(f"Фактически проверено: {report.get('processed', report['total_dataset_items'])}")
    print(f"Найдено в TMDb: {report['matched']}")
    print(f"Не найдено: {report['unmatched']}")
    print(f"Без жанров: {len(report.get('empty_genre_items') or [])}")
    if report.get("stopped_early"):
        print(f"Остановлено досрочно: {report.get('stop_reason')}")

    if report["unmatched_items"]:
        print("\nНе найдено:")
        for item in report["unmatched_items"]:
            year = item.get("year") or "-"
            print(f"- {item.get('title')} ({year})")

    if report.get("empty_genre_items"):
        print("\nTMDb найден, но genres пустые:")
        for item in report["empty_genre_items"]:
            year = item.get("year") or "-"
            print(f"- {item.get('title')} ({year})")

    print(f"\nОтчёт сохранён: {report_path}")


def import_tmdb_result_to_common_pool_flow() -> None:
    """Импортирует отдельный TMDb v1 result JSON в общий candidate_pool после подтверждения."""
    ui.clean_terminal()
    files_view = candidate_service.get_tmdb_import_files_view()
    if files_view["is_empty"]:
        print("TMDb result JSON в data/candidate_pool не найдены.")
        return

    files = files_view["files"]
    print("TMDb result JSON:\n")
    for index, path in enumerate(files, start=1):
        print(f"{index} >> {path.name}")

    selected = request.loop_input(
        text="\nВыберите файл для импорта >> ",
        funcs_list=[lambda value: value.isdigit() and 1 <= int(value) <= len(files)]
    )
    result_path = files[int(selected) - 1]

    preview = candidate_service.load_tmdb_result_import_preview(result_path)
    if preview["ok"] is False:
        print(f"Не удалось прочитать файл: {preview.get('error')}")
        return

    default_criteria_name = preview["default_criteria_name"]
    criteria_answer = input(f"criteria_name [{default_criteria_name}] >> ").strip()
    criteria_name = criteria_answer or default_criteria_name
    if criteria_name == "":
        print("criteria_name не должен быть пустым.")
        return

    print("\nPreview импорта TMDb result:")
    print(f"Файл: {result_path}")
    print(f"Кандидатов в файле: {preview['candidate_count']}")
    print("Будет добавлено/обновлено в общий пул после дедупликации.")
    print("Источник: tmdb_imdb_kp_v1")
    print(f"criteria_name: {criteria_name}")

    answer = input("\nИмпортировать в общий candidate_pool? [y/N] ").strip().casefold()
    if answer not in {"y", "yes", "д", "да"}:
        print("Импорт отменён.")
        return

    import_result = candidate_service.import_tmdb_result_to_pool(result_path, criteria_name=criteria_name)
    if import_result["ok"] is False:
        print(f"Импорт не выполнен: {import_result.get('error')}")
        return

    stats = import_result["stats"]
    print("\nИмпорт TMDb result завершён.")
    print(f"Прочитано: {stats['read']}")
    print(f"Добавлено новых: {stats['added']}")
    print(f"Обновлено существующих: {stats['updated']}")
    print(f"Пропущено already watched: {stats['watched_skipped']}")
    print(f"Пропущено как дубли: {stats['duplicates']}")
    print(f"Ошибок: {stats['errors']}")
    print(f"Текущий размер общего пула: {stats.get('pool_size', 0)}")


def edit_candidate_pool_filters() -> None:
    """Редактирует фильтры сохраненного набора критериев пула."""
    ui.clean_terminal()
    selected = candidate_pool_ui.choose_existing_criteria()
    if selected is None:
        return

    criteria_name, criteria = selected
    print(f"\nФильтрация для пула: {criteria_name}")
    print("Жанры для top prediction (по сохранённым данным pool). Это не запускает новый TMDb Discover.")
    print(f"Текущий KP: {criteria.get('min_kp', 'не важно')}")
    print(f"Текущие жанры (saved pool): {', '.join(criteria.get('genres', [])) or 'не важно'}")
    print(f"Исключить жанры (saved pool): {', '.join(criteria.get('excluded_genres', [])) or 'не важно'}\n")

    updated = candidate_pool_ui.update_criteria_filters(criteria_name, criteria)
    print("\nФильтрация обновлена в candidate_criteria.json.")
    print("Filters сохраняются как defaults для top prediction по уже сохранённым кандидатам (Enter = default).")
    print("Ручной ввод в top prediction действует только на текущий запуск.")
    print("Filters не пересобирают pool, не делают новый TMDb-запрос и не удаляют кандидатов из candidate_pool.json.")
    print(f"KP: {updated.get('min_kp', 'не важно')}")
    print(f"Жанры (saved pool): {', '.join(updated.get('genres', [])) or 'не важно'}")
    print(f"Жанры исключить (saved pool): {', '.join(updated.get('excluded_genres', [])) or 'не важно'}")


def show_candidate_pool() -> None:
    """Показывает кандидатов выбранного пула в консоли."""
    ui.clean_terminal()
    selected = candidate_pool_ui.choose_existing_criteria()
    if selected is None:
        return

    criteria_name, criteria = selected
    candidates = candidate_service.get_pool_view(criteria_name)
    pool_stats_view = candidate_service.get_pool_stats_view(criteria_name=criteria_name)

    print(f"\nПул кандидатов: {criteria_name}")
    print(f"Страна: {criteria.get('country')}")
    for line in pool_stats_view["lines"]:
        print(line)
    print("")

    if len(candidates) == 0:
        print("Для этого набора критериев кандидатов пока нет.")
        return

    for idx, candidate in enumerate(candidates, start=1):
        title = candidate.get("title") or "Без названия"
        year = candidate.get("year") or "?"
        kp_score = candidate.get("kp_score")
        imdb_score = candidate.get("imdb_score")
        kp_votes = candidate.get("kp_votes")
        genres = ", ".join(genre_schema.candidate_genres_for_display(candidate)) or "нет"
        description = request.short_text(candidate.get("description"), 80) or "без описания"
        kp_status = candidate.get("kp_status")
        is_complete = candidate.get("is_complete")

        kp_score_label = kp_score if kp_score is not None else "-"
        imdb_score_label = imdb_score if imdb_score is not None else "-"
        kp_votes_label = kp_votes if kp_votes is not None else "-"

        print(f"{idx}) {title} ({year})")
        print(f"   KP: {kp_score_label} | IMDb: {imdb_score_label} | KP votes: {kp_votes_label}")
        if kp_status is not None or is_complete is not None:
            complete_label = "yes" if is_complete is True else "no"
            print(f"   KP status: {kp_status or 'unknown'} | complete: {complete_label}")
        print(f"   Жанры: {genres}")
        print(f"   Описание: {description}\n")


def show_global_candidate_top() -> None:
    """Показывает топ кандидатов из общего пула по предикту без вайб-тегов."""
    ui.clean_terminal()
    top_view = candidate_service.get_global_top_prediction_view()
    if top_view["is_empty"]:
        print("Общий пул кандидатов пуст.")
        return

    print("")
    for line in top_view["lines"]:
        print(line)

    filters = _request_prediction_candidate_filters(top_view["candidates"])
    filter_view = candidate_service.get_prediction_filter_view(top_view["candidates"], filters)
    if filter_view["filtered_count"] == 0:
        print("\nПо выбранным фильтрам кандидатов не найдено.")
        return

    ready_candidates = filter_view["ready_candidates"]
    incomplete_candidates = filter_view["incomplete_candidates"]
    skipped_incomplete = filter_view["skipped_incomplete_count"]

    print(f"\nПосле выбранного фильтра: {filter_view['filtered_count']}")
    print(f"Готовых к предикту: {filter_view['ready_count']}")
    print(f"Пропущено неполных: {skipped_incomplete}")
    if skipped_incomplete > 0:
        print("\nНеполные кандидаты не участвовали в обычном предикте.")
        print("Причина: нет части KP/IMDb данных или is_complete=false.")
        print("Чтобы попробовать добрать KP-данные, запусти:")
        print("10 >> Добрать KP для неполных кандидатов")
        print("\nНеполные кандидаты:\n")
        _print_incomplete_candidates_preview(incomplete_candidates, limit=5)

    if len(ready_candidates) == 0:
        print("\nНет готовых кандидатов для предикта.")
        print("Можно изменить фильтры или запустить добор KP для неполных кандидатов.")
        return

    top_n_value = request.loop_input(
        text="\nТоп N из общего пула >> ",
        funcs_list=[valid.is_correct_top_n]
    )
    top_n = min(int(top_n_value), len(ready_candidates))

    weights = storage_data.load_weights()
    scored_candidates = candidate_pool.rank_candidates_by_predict(ready_candidates, weights)
    scored_candidates = candidate_pool.dedupe_ranked_predictions_by_title_identity(scored_candidates)
    top_n = min(top_n, len(scored_candidates))

    print(f"\nТоп {top_n} из общего пула:\n")
    for index, row in enumerate(scored_candidates[:top_n], start=1):
        _print_prediction_candidate_card(index, row)


def _print_candidate_contribution_group(title: str, rows: list, limit: int) -> None:
    print(f"   {title}:")
    if len(rows) == 0:
        print("   нет")
        return

    for idx, row in enumerate(rows[:limit], start=1):
        print(
            f"   {idx}. {row['label']} ({row['feature']}): "
            f"{row['impact']:+.4f} = {row['value']:.4f} * {row['weight']:+.4f}"
        )


def _print_incomplete_candidates_preview(candidates: list, limit: int = 5) -> None:
    if len(candidates) == 0:
        return

    preview = candidates[:limit]
    for index, candidate in enumerate(preview, start=1):
        title = candidate.get("title") or "Без названия"
        year = candidate.get("year") or "?"
        kp_status = candidate.get("kp_status") or "unknown"
        complete_label = "yes" if candidate.get("is_complete") is True else "no"
        print(f"{index}. {title} ({year}) | KP status: {kp_status} | complete: {complete_label}")

    remaining = len(candidates) - len(preview)
    if remaining > 0:
        print(f"\n...и ещё {remaining}")


def _format_card_list(value) -> str:
    if isinstance(value, str):
        return value.strip() or "нет данных"
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value if str(item or "").strip()]
        return ", ".join(items) if items else "нет данных"
    if value in (None, ""):
        return "нет данных"
    return str(value)


def _format_card_score(value) -> str:
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return str(value)


def _print_prediction_candidate_card(index: int, candidate: dict) -> None:
    title = candidate.get("title") or candidate.get("name") or candidate.get("title_ru") or "Без названия"
    year = candidate.get("year") or "?"
    countries = country_schema.candidate_country_for_display(candidate)
    genres = genre_schema.candidate_genres_for_display(candidate)
    description = candidate_pool.format_candidate_description(candidate, limit=200)
    predict = candidate.get("predict_score", candidate.get("predict"))
    try:
        predict_label = f"{float(predict):.2f}"
    except (TypeError, ValueError):
        predict_label = "-"

    print(f"{index}. {title} ({year})")
    print(f"   Рейтинг: KP: {_format_card_score(candidate.get('kp_score'))} / IMDb: {_format_card_score(candidate.get('imdb_score'))}")
    print(f"   Страна: {_format_card_list(countries)}")
    print(f"   Жанр: {_format_card_list(genres)}")
    print(f"   Описание: {description}")
    print(f"   Прогноз: {predict_label}\n")


def _parse_optional_csv_list(value: str) -> list[str]:
    values = []
    for item in str(value or "").split(","):
        text = item.strip()
        if text != "":
            values.append(text)
    return values


def _format_prediction_default(value) -> str:
    if value in (None, ""):
        return "не важно"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if len(value) > 0 else "не важно"
    return str(value)


def _input_optional_prediction_int(label: str, default, min_value: int, max_value: int):
    answer = input(f"{label} [{_format_prediction_default(default)}] >> ").strip()
    if answer == "":
        return default
    return _parse_optional_bounded_int(answer, min_value, max_value)


def _input_optional_prediction_float(label: str, default, min_value: float, max_value: float):
    answer = input(f"{label} [{_format_prediction_default(default)}] >> ").strip()
    if answer == "":
        return default
    return _parse_optional_bounded_float(answer, min_value, max_value)


def _input_optional_prediction_csv_list(label: str, default: list) -> list[str]:
    answer = input(f"{label} [{_format_prediction_default(default)}] >> ").strip()
    if answer == "":
        return list(default or [])
    return _parse_optional_csv_list(answer)


def _choose_prediction_criteria_name() -> str | None:
    all_criteria = candidate_pool.load_candidate_criteria()
    criteria_names = sorted(all_criteria.keys())
    if len(criteria_names) == 0:
        return None

    print("\nВыбрать набор criteria_name?")
    print(" 0 >> Все")
    for idx, name in enumerate(criteria_names, start=1):
        print(f" {idx} >> {candidate_pool.build_criteria_label(name, all_criteria[name])}")

    selected = request.loop_input(
        text="\nВыбор [0] >> ",
        funcs_list=[lambda value: value == "" or (value.isdigit() and 0 <= int(value) <= len(criteria_names))]
    )
    if selected in {"", "0"}:
        return None
    return criteria_names[int(selected) - 1]


def _choose_prediction_source(candidates: list) -> str | None:
    sources = sorted({
        str(candidate.get("source") or "").strip()
        for candidate in candidates
        if str(candidate.get("source") or "").strip() != ""
    })
    if len(sources) == 0:
        return None

    print("\nВыбрать source?")
    print(" 0 >> Все")
    for idx, source in enumerate(sources, start=1):
        print(f" {idx} >> {source}")

    selected = request.loop_input(
        text="\nSource [0] >> ",
        funcs_list=[lambda value: value == "" or (value.isdigit() and 0 <= int(value) <= len(sources))]
    )
    if selected in {"", "0"}:
        return None
    return sources[int(selected) - 1]


def _request_prediction_candidate_filters(candidates: list) -> dict:
    print("\nФильтр кандидатов перед предиктом:")
    print("Жанры для top prediction (по сохранённым данным pool).")
    print("Жанры (saved pool / KP-IMDb-TMDb data).")
    print("Это не пересобирает pool и не делает новый TMDb-запрос.")
    print("Enter = оставить saved default.\n")

    criteria_name = _choose_prediction_criteria_name()
    defaults_view = candidate_service.get_prediction_filter_defaults_view(criteria_name)
    defaults = defaults_view["defaults"]
    if defaults_view["has_defaults"]:
        print(f"\nDefaults из criteria '{criteria_name}':")
        for line in defaults_view["lines"]:
            print(f"  {line}")

    genre_options_view = candidate_service.get_prediction_genre_options_view(criteria_name)
    if genre_options_view["count"] > 0:
        print("\nДоступные жанры для top prediction (по сохранённым данным pool):")
        print(", ".join(genre_options_view["genres"]))
    else:
        print("\nДоступные жанры для top prediction (по сохранённым данным pool): нет данных")

    source = _choose_prediction_source(candidates)
    country_answer = input(f"\nСтрана [{_format_prediction_default(defaults.get('country'))}] >> ").strip()
    country = country_answer or defaults.get("country")
    year_min = _input_optional_prediction_int(
        "Минимальный год",
        defaults.get("year_min"),
        1900,
        constant.NOW_YEAR,
    )
    year_max = _input_optional_prediction_int(
        "Максимальный год",
        defaults.get("year_max"),
        1900,
        constant.NOW_YEAR,
    )
    include_genres = _input_optional_prediction_csv_list(
        "Включить жанры (saved pool) через запятую",
        defaults.get("include_genres") or [],
    )
    exclude_genres = _input_optional_prediction_csv_list(
        "Исключить жанры (saved pool) через запятую",
        defaults.get("exclude_genres") or [],
    )
    min_kp_score = _input_optional_prediction_float(
        "Минимальный KP",
        defaults.get("min_kp_score"),
        0.0,
        10.0,
    )
    min_kp_votes = _input_optional_prediction_int(
        "Минимум голосов KP",
        defaults.get("min_kp_votes"),
        0,
        10_000_000,
    )
    min_imdb_score = _input_optional_prediction_float(
        "Минимальный IMDb",
        defaults.get("min_imdb_score"),
        0.0,
        10.0,
    )
    min_imdb_votes = _input_optional_prediction_int(
        "Минимум голосов IMDb",
        defaults.get("min_imdb_votes"),
        0,
        10_000_000,
    )
    only_complete_default = defaults.get("only_complete", True)
    only_complete_label = "Y/n" if only_complete_default is True else "y/N"
    only_complete_answer = input(f"Только complete-кандидаты? [{only_complete_label}] >> ").strip().casefold()
    if only_complete_answer == "":
        only_complete = only_complete_default is True
    elif only_complete_answer in {"n", "no", "н", "нет"}:
        only_complete = False
    else:
        only_complete = only_complete_answer in {"y", "yes", "д", "да"}

    return {
        "criteria_name": criteria_name,
        "source": source,
        "country": country,
        "year_min": year_min,
        "year_max": year_max,
        "include_genres": include_genres,
        "exclude_genres": exclude_genres,
        "min_kp_score": min_kp_score,
        "min_kp_votes": min_kp_votes,
        "min_imdb_score": min_imdb_score,
        "min_imdb_votes": min_imdb_votes,
        "only_complete": only_complete,
    }


def show_candidate_contributions() -> None:
    """Показывает вклады признаков для топа кандидатов из общего пула."""
    ui.clean_terminal()
    candidates = candidate_service.get_pool_view()
    if len(candidates) == 0:
        print("Общий пул кандидатов пуст.")
        return

    contribution_view = candidate_service.get_contribution_ready_view(candidates)
    ready_candidates = contribution_view["ready_candidates"]
    skipped_incomplete = contribution_view["skipped_count"]

    if len(ready_candidates) == 0:
        print("Нет кандидатов, готовых для расчёта вкладов.")
        if skipped_incomplete > 0:
            print(f"В pool есть {skipped_incomplete} неполных кандидатов.")
            print("Чтобы попробовать добрать KP-данные, запусти:")
            print("10 >> Добрать KP для неполных кандидатов")
        return

    if skipped_incomplete > 0:
        print(f"Неполные кандидаты ({skipped_incomplete}) не участвуют в расчёте вкладов.")

    top_n_value = request.loop_input(
        text="Сколько кандидатов показать >> ",
        funcs_list=[valid.is_correct_top_n]
    )
    top_n = min(int(top_n_value), len(ready_candidates))

    contribution_limit_value = input("Сколько вкладов показывать на знак [10] >> ").strip()
    try:
        contribution_limit = int(contribution_limit_value or 10)
    except ValueError:
        contribution_limit = 10
    contribution_limit = max(1, min(contribution_limit, 30))

    weights = storage_data.load_weights()
    reports = candidate_pool.build_contribution_reports_for_ready_candidates(ready_candidates, weights)
    reports.sort(key=lambda row: row["predict"], reverse=True)

    print("\nВклады для кандидатов")
    print("Примечание: предикт считается без вайб-тегов, потому что у кандидатов их ещё нет.\n")

    for idx, report in enumerate(reports[:top_n], start=1):
        criteria_name = report.get("criteria_name") or "без критерия"
        print(f"{idx}. {report['title']} ({report['year']})")
        print(f"   Критерий: {criteria_name}")
        print(f"   Прогноз модели: {report['predict']:.4f}")
        _print_candidate_contribution_group(
            "Топ положительных вкладов",
            report["positive"],
            contribution_limit,
        )
        _print_candidate_contribution_group(
            "Топ отрицательных вкладов",
            report["negative"],
            contribution_limit,
        )
        print("")


def retry_kp_for_incomplete_candidates() -> None:
    """Запускает повторный добор KP-данных для неполных кандидатов общего пула."""
    ui.clean_terminal()
    retry_view = candidate_service.get_retry_kp_view()
    if retry_view["is_empty"]:
        print("Общий пул кандидатов пуст.")
        return

    print("Добор KP для неполных кандидатов\n")
    print(f"Неполных кандидатов всего: {retry_view['incomplete_count']}")
    if retry_view["incomplete_count"] == 0:
        print("Добор не требуется.")
        return

    criteria_options = retry_view["criteria_options"]
    print("\nНабор критериев:")
    print(" 0 >> Все неполные кандидаты")
    for idx, option in enumerate(criteria_options, start=1):
        print(f" {idx} >> {option['label']} | incomplete={option['incomplete_count']}")

    selected = request.loop_input(
        text="\nВыбор [0] >> ",
        funcs_list=[lambda value: value == "" or (value.isdigit() and 0 <= int(value) <= len(criteria_options))]
    )
    criteria_name = None
    if selected != "" and selected != "0":
        criteria_name = criteria_options[int(selected) - 1]["criteria_name"]

    scoped_view = candidate_service.get_retry_kp_view(criteria_name=criteria_name)
    scoped_incomplete = scoped_view["incomplete_candidates"]
    if len(scoped_incomplete) == 0:
        print("Для выбранного набора неполных кандидатов нет.")
        return

    limit_answer = input("Лимит попыток [10] >> ").strip()
    try:
        limit = int(limit_answer or 10)
    except ValueError:
        limit = 10
    limit = max(1, min(limit, len(scoped_incomplete)))
    selected_candidates = scoped_incomplete[:limit]

    print("\nБудет запущен добор KP:")
    print(f"Критерий: {criteria_name or 'все'}")
    print(f"Неполных найдено: {len(scoped_incomplete)}")
    print(f"Попыток будет выполнено: {limit}")
    print("\nПервые кандидаты на добор:\n")
    _print_incomplete_candidates_preview(selected_candidates, limit=limit)
    answer = input("\nЗапустить добор KP для этих кандидатов? [y/N] ").strip().casefold()
    if answer not in {"y", "yes", "д", "да"}:
        print("Добор KP отменён.")
        return

    result = candidate_service.retry_kp_enrichment_in_pool(
        limit=limit,
        criteria_name=criteria_name,
    )
    stats = result["stats"]

    print("\nДобор KP завершён.")
    print(f"Неполных найдено: {stats['incomplete_found']}")
    print(f"Попыток выполнено: {stats['attempted']}")
    print(f"KP найден: {stats['kp_found']}")
    print(f"KP не найден: {stats['kp_not_found']}")
    print(f"Ошибок API: {stats['api_errors']}")
    print(f"Стали complete: {stats['became_complete']}")
    print(f"Остались incomplete: {stats['remaining_incomplete']}")


def delete_candidate_pool() -> None:
    """Удаляет набор критериев и связанные с ним объекты из общего пула."""
    ui.clean_terminal()
    selected = candidate_pool_ui.choose_existing_criteria()
    if selected is None:
        return

    criteria_name, _ = selected
    answer = input(f"\nУдалить пулл '{criteria_name}'? yes >> ").strip().lower()
    if answer != "yes":
        print("Удаление отменено.")
        return

    delete_result = candidate_service.delete_candidate_pool_criteria(criteria_name)
    if delete_result["deleted_criteria"] is False:
        print("Пулл не найден.")
        return

    print("Пулл удалён.")
    print(f"Удалено кандидатов из общего пула: {delete_result['deleted_candidates']}")


def show_suspicious_candidate_duplicates() -> None:
    """Показывает подозрительно похожие дубли в общем пуле."""
    ui.clean_terminal()
    duplicates_view = candidate_service.get_suspicious_duplicates_view()
    if duplicates_view["is_empty"]:
        print("Подозрительных дублей в общем пуле не найдено.")
        return

    print("Подозрительные дубли в общем пуле:\n")
    for idx, pair in enumerate(duplicates_view["pairs"], start=1):
        left = pair["left"]
        right = pair["right"]
        print(f"{idx}) Похожесть: {pair['ratio']:.2f}")
        print(
            f"   A: {left.get('title')} ({left.get('year')}) "
            f"| критерий: {left.get('criteria_name')}"
        )
        print(
            f"   B: {right.get('title')} ({right.get('year')}) "
            f"| критерий: {right.get('criteria_name')}"
        )
        print("")
