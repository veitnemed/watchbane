"""Содержит действия интерфейса, которые запускаются из пунктов меню."""

import json
import os
import copy
from datetime import datetime
from pathlib import Path

from config import constant
from common import format_score as format
from candidates import candidate_pool
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
    candidates = candidate_pool.get_candidates_by_criteria(criteria_name)

    print(f"\nПулл кандидатов: {criteria_name}")
    print(f"Страна: {criteria.get('country')}")
    print(f"Кандидатов: {len(candidates)}\n")

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
    if candidate_pool.is_candidate_incomplete(candidate):
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
    print(f"Найдено через TMDb Discover: {stats.get('discover_total', 0)}")
    print(f"Удалено дублей: {stats.get('duplicates_removed', 0)}")
    print(f"Пропущено уже просмотренных: {stats.get('watched_skipped', 0)}")
    print(f"Запрошено TMDb Details: {stats.get('details_requested', 0)}")
    print(f"С IMDb ID: {stats.get('has_imdb_id', 0)}")
    print(f"Найдено в IMDb dataset: {stats.get('found_in_imdb_sql', 0)}")
    print(f"KP найдено в кэше: {stats.get('kp_cache_hit', 0)}")
    print(f"KP API запросов: {stats.get('kp_api_requested', 0)}")
    print(f"KP API найдено: {stats.get('kp_api_found', 0)}")
    print(f"KP API не найдено: {stats.get('kp_api_not_found', 0)}")
    print(f"KP API отклонено match-check: {stats.get('kp_api_rejected_by_match', 0)}")
    print(f"KP API ошибок: {stats.get('kp_api_errors', 0)}")
    print(f"KP API пропущено из-за кэша: {stats.get('kp_api_skipped_cache', 0)}")
    print(f"KP ожидает добора из-за лимита: {stats.get('kp_pending_limit', 0)}")
    print(f"Неполных кандидатов по KP: {stats.get('kp_incomplete_candidates', 0)}")
    print(f"Полностью обогащённых кандидатов: {stats.get('complete_candidates', 0)}")
    print(f"Прошли country_score: {stats.get('country_passed', 0)}")
    print(f"Отклонено adult/titleType: {stats.get('adult_title_type_rejected', 0)}")
    print(f"Итоговых кандидатов: {stats.get('final_candidates', 0)}")


def _tmdb_mode_label(mode: str) -> str:
    labels = {
        "quality": "лучшие по качеству",
        "hidden_gems": "скрытые находки",
    }
    return labels.get(mode, mode)


def run_tmdb_candidate_pool_flow() -> None:
    """Запускает новый TMDb candidate_pool v1 без смешивания со старым общим пулом."""
    from pathlib import Path

    from apis import imdb_sql as sql_search
    from candidates.tmdb_candidate_pool import (
        build_candidate_pool,
        save_candidate_pool_result,
        save_candidate_pool_test_result,
    )

    ui.clean_terminal()
    print("TMDb candidate_pool v1\n")
    print("Страна:")
    print("1 >> Россия RU")
    print("2 >> Ввести код страны вручную")
    country_answer = input("Выбор [1] >> ").strip()
    if country_answer == "":
        country = "RU"
    elif country_answer == "1":
        country = "RU"
    elif country_answer == "2":
        country = _parse_iso_country_code(
            input("Введите код страны ISO-2, например KR, US, GB, DE: ")
        )
        if country is None:
            print("Ошибка: введите корректный двухбуквенный код ISO-2 латиницей.")
            return
    else:
        print("Ошибка: выберите 1 или 2.")
        return

    print("\nРежим:")
    print("1 >> Лучшие по качеству")
    print("2 >> Скрытые находки")
    mode_answer = input("Выбор [1] >> ").strip()
    if mode_answer in ("", "1"):
        mode = "quality"
    elif mode_answer == "2":
        mode = "hidden_gems"
    else:
        print("Ошибка: выберите 1 или 2.")
        return

    print("\nРежим запуска:")
    print("1 >> Обычный")
    print("2 >> Тестовый прогон без перезаписи основного файла")
    run_mode_answer = input("Выбор [1] >> ").strip()
    if run_mode_answer in ("", "1"):
        is_test_run = False
    elif run_mode_answer == "2":
        is_test_run = True
    else:
        print("Ошибка: выберите 1 или 2.")
        return

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

    print("\nБудет запущен TMDb candidate_pool v1:\n")
    print(f"Страна: {country}")
    print(f"Режим: {_tmdb_mode_label(mode)}")
    print(f"Режим запуска: {'тестовый прогон' if is_test_run else 'обычный'}")
    print(f"Страниц TMDb Discover: {pages}")
    print(f"Лимит TMDb Details: {details_limit}")
    print(f"Минимальный год: {year_min if year_min is not None else 'не важно'}")
    print(f"Максимальный год: {year_max if year_max is not None else 'не важно'}")
    print(f"Минимальный TMDb рейтинг: {min_tmdb_score if min_tmdb_score is not None else 'не важно'}")
    print(f"Минимум голосов TMDb: {min_tmdb_votes if min_tmdb_votes is not None else 'не важно'}")
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
        result = build_candidate_pool(
            country=country,
            pages=pages,
            details_limit=details_limit,
            mode=mode,
            year_min=year_min,
            year_max=year_max,
            min_tmdb_score=min_tmdb_score,
            min_tmdb_votes=min_tmdb_votes,
        )
        if is_test_run:
            print("Сохранение test candidate_pool: Ожидание")
            json_path, csv_path = save_candidate_pool_test_result(result)
            print("Сохранение test candidate_pool: Успешно")
        else:
            print("Сохранение candidate_pool: Ожидание")
            json_path, csv_path = save_candidate_pool_result(result)
            print("Сохранение candidate_pool: Успешно")
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
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    _print_tmdb_candidate_stats(result)

    candidates = result.get("candidates") or []
    if len(candidates) > 0:
        if is_test_run:
            _print_tmdb_candidate_test_details(candidates)
        else:
            _print_tmdb_candidate_top(candidates)
    else:
        print("Итоговый список кандидатов пуст.")


def import_tmdb_result_to_common_pool_flow() -> None:
    """Импортирует отдельный TMDb v1 result JSON в общий candidate_pool после подтверждения."""
    import json

    from candidates.tmdb_candidate_pool import (
        import_tmdb_result_to_common_pool,
        list_tmdb_result_files,
        tmdb_import_default_criteria_name,
    )

    ui.clean_terminal()
    files = list_tmdb_result_files()
    if len(files) == 0:
        print("TMDb result JSON в data/candidate_pool не найдены.")
        return

    print("TMDb result JSON:\n")
    for index, path in enumerate(files, start=1):
        print(f"{index} >> {path.name}")

    selected = request.loop_input(
        text="\nВыберите файл для импорта >> ",
        funcs_list=[lambda value: value.isdigit() and 1 <= int(value) <= len(files)]
    )
    result_path = files[int(selected) - 1]

    try:
        with open(result_path, "r", encoding="utf-8-sig") as file:
            result = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Не удалось прочитать файл: {error}")
        return

    candidates = result.get("candidates") if isinstance(result, dict) else []
    if isinstance(candidates, list) is False:
        print("В файле нет списка candidates.")
        return

    default_criteria_name = tmdb_import_default_criteria_name(result) or ""
    criteria_answer = input(f"criteria_name [{default_criteria_name}] >> ").strip()
    criteria_name = criteria_answer or default_criteria_name
    if criteria_name == "":
        print("criteria_name не должен быть пустым.")
        return

    print("\nPreview импорта TMDb result:")
    print(f"Файл: {result_path}")
    print(f"Кандидатов в файле: {len(candidates)}")
    print("Будет добавлено/обновлено в общий пул после дедупликации.")
    print("Источник: tmdb_imdb_kp_v1")
    print(f"criteria_name: {criteria_name}")

    answer = input("\nИмпортировать в общий candidate_pool? [y/N] ").strip().casefold()
    if answer not in {"y", "yes", "д", "да"}:
        print("Импорт отменён.")
        return

    stats = import_tmdb_result_to_common_pool(result_path, criteria_name=criteria_name)
    if stats.get("ok") is False:
        print(f"Импорт не выполнен: {stats.get('error')}")
        return

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
    print(f"Текущий KP: {criteria.get('min_kp', 'не важно')}")
    print(f"Текущие жанры: {', '.join(criteria.get('genres', [])) or 'не важно'}")
    print(f"Исключить жанры: {', '.join(criteria.get('excluded_genres', [])) or 'не важно'}\n")

    updated = candidate_pool_ui.update_criteria_filters(criteria_name, criteria)
    print("Фильтрация обновлена.")
    print(f"KP: {updated.get('min_kp', 'не важно')}")
    print(f"Жанры: {', '.join(updated.get('genres', [])) or 'не важно'}")
    print(f"Жанры исключить: {', '.join(updated.get('excluded_genres', [])) or 'не важно'}")


def show_candidate_pool() -> None:
    """Показывает кандидатов выбранного пула в консоли."""
    ui.clean_terminal()
    selected = candidate_pool_ui.choose_existing_criteria()
    if selected is None:
        return

    criteria_name, criteria = selected
    candidates = candidate_pool.get_candidates_by_criteria(criteria_name)

    print(f"\nПул кандидатов: {criteria_name}")
    print(f"Страна: {criteria.get('country')}")
    print(f"Кандидатов: {len(candidates)}\n")

    if len(candidates) == 0:
        print("Для этого набора критериев кандидатов пока нет.")
        return

    for idx, candidate in enumerate(candidates, start=1):
        title = candidate.get("title") or "Без названия"
        year = candidate.get("year") or "?"
        kp_score = candidate.get("kp_score")
        imdb_score = candidate.get("imdb_score")
        kp_votes = candidate.get("kp_votes")
        genres = ", ".join(candidate.get("genres", [])) or "нет"
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
    candidates = candidate_pool.get_all_candidates()
    if len(candidates) == 0:
        print("Общий пул кандидатов пуст.")
        return

    filters = _request_prediction_candidate_filters(candidates)
    filtered_candidates = candidate_pool.filter_saved_candidates_for_prediction(candidates, filters)
    if len(filtered_candidates) == 0:
        print("\nПо выбранным фильтрам кандидатов не найдено.")
        return

    ready_candidates = [
        candidate for candidate in filtered_candidates
        if candidate_pool.is_candidate_ready_for_prediction(candidate)
    ]
    incomplete_candidates = [
        candidate for candidate in filtered_candidates
        if candidate_pool.is_candidate_incomplete(candidate)
    ]
    skipped_incomplete = len(filtered_candidates) - len(ready_candidates)

    print(f"\nКандидатов всего в pool: {len(candidates)}")
    print(f"После выбранного фильтра: {len(filtered_candidates)}")
    print(f"Готовых к предикту: {len(ready_candidates)}")
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

    print(f"\nТоп {top_n} из общего пула:\n")
    for row in scored_candidates[:top_n]:
        print(f"{row['title']} ({row['year']}): {row['predict']:.2f}")


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


def _parse_optional_csv_list(value: str) -> list[str]:
    values = []
    for item in str(value or "").split(","):
        text = item.strip()
        if text != "":
            values.append(text)
    return values


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
    print("\nФильтр кандидатов перед предиктом:\n")
    criteria_name = _choose_prediction_criteria_name()
    source = _choose_prediction_source(candidates)
    country = input("\nСтрана [не важно] >> ").strip() or None
    year_min = _parse_optional_bounded_int(input("Минимальный год [не важно] >> ").strip(), 1900, constant.NOW_YEAR)
    year_max = _parse_optional_bounded_int(input("Максимальный год [не важно] >> ").strip(), 1900, constant.NOW_YEAR)
    include_genres = _parse_optional_csv_list(input("Включить жанры через запятую [не важно] >> ").strip())
    exclude_genres = _parse_optional_csv_list(input("Исключить жанры через запятую [не важно] >> ").strip())
    min_kp_score = _parse_optional_bounded_float(input("Минимальный KP [не важно] >> ").strip(), 0.0, 10.0)
    min_kp_votes = _parse_optional_bounded_int(input("Минимум голосов KP [не важно] >> ").strip(), 0, 10_000_000)
    min_imdb_score = _parse_optional_bounded_float(input("Минимальный IMDb [не важно] >> ").strip(), 0.0, 10.0)
    min_imdb_votes = _parse_optional_bounded_int(input("Минимум голосов IMDb [не важно] >> ").strip(), 0, 10_000_000)
    min_tmdb_score = _parse_optional_bounded_float(input("Минимальный TMDb [не важно] >> ").strip(), 0.0, 10.0)
    min_tmdb_votes = _parse_optional_bounded_int(input("Минимум голосов TMDb [не важно] >> ").strip(), 0, 10_000_000)
    only_complete_answer = input("Только complete-кандидаты? [Y/n] >> ").strip().casefold()
    only_complete = only_complete_answer not in {"n", "no", "н", "нет"}

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
        "min_tmdb_score": min_tmdb_score,
        "min_tmdb_votes": min_tmdb_votes,
        "only_complete": only_complete,
    }


def show_candidate_contributions() -> None:
    """Показывает вклады признаков для топа кандидатов из общего пула."""
    ui.clean_terminal()
    candidates = candidate_pool.get_all_candidates()
    if len(candidates) == 0:
        print("Общий пул кандидатов пуст.")
        return

    top_n_value = request.loop_input(
        text="Сколько кандидатов показать >> ",
        funcs_list=[valid.is_correct_top_n]
    )
    top_n = min(int(top_n_value), len(candidates))

    contribution_limit_value = input("Сколько вкладов показывать на знак [10] >> ").strip()
    try:
        contribution_limit = int(contribution_limit_value or 10)
    except ValueError:
        contribution_limit = 10
    contribution_limit = max(1, min(contribution_limit, 30))

    weights = storage_data.load_weights()
    reports = [
        candidate_pool.candidate_feature_contributions(candidate, weights)
        for candidate in candidates
    ]
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
    pool = candidate_pool.load_candidate_pool()
    if len(pool) == 0:
        print("Общий пул кандидатов пуст.")
        return

    all_incomplete = candidate_pool.get_incomplete_candidates(pool)
    print("Добор KP для неполных кандидатов\n")
    print(f"Неполных кандидатов всего: {len(all_incomplete)}")
    if len(all_incomplete) == 0:
        print("Добор не требуется.")
        return

    all_criteria = candidate_pool.load_candidate_criteria()
    criteria_names = sorted(all_criteria.keys())
    print("\nНабор критериев:")
    print(" 0 >> Все неполные кандидаты")
    for idx, name in enumerate(criteria_names, start=1):
        scoped_count = len(candidate_pool.get_incomplete_candidates(pool, criteria_name=name))
        print(f" {idx} >> {candidate_pool.build_criteria_label(name, all_criteria[name])} | incomplete={scoped_count}")

    selected = request.loop_input(
        text="\nВыбор [0] >> ",
        funcs_list=[lambda value: value == "" or (value.isdigit() and 0 <= int(value) <= len(criteria_names))]
    )
    criteria_name = None
    if selected != "" and selected != "0":
        criteria_name = criteria_names[int(selected) - 1]

    scoped_incomplete = candidate_pool.get_incomplete_candidates(pool, criteria_name=criteria_name)
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

    stats = candidate_pool.retry_kp_enrichment_for_pool(
        limit=limit,
        criteria_name=criteria_name,
    )

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

    result = candidate_pool.delete_criteria_and_candidates(criteria_name)
    if result["deleted_criteria"] is False:
        print("Пулл не найден.")
        return

    print("Пулл удалён.")
    print(f"Удалено кандидатов из общего пула: {result['deleted_candidates']}")


def show_suspicious_candidate_duplicates() -> None:
    """Показывает подозрительно похожие дубли в общем пуле."""
    ui.clean_terminal()
    pairs = candidate_pool.find_suspicious_duplicates()
    if len(pairs) == 0:
        print("Подозрительных дублей в общем пуле не найдено.")
        return

    print("Подозрительные дубли в общем пуле:\n")
    for idx, pair in enumerate(pairs, start=1):
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

