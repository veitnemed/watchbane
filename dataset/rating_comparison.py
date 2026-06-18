"""Interactive user_score refinement through pairwise rating comparisons."""

import json
import random
from datetime import datetime
from pathlib import Path

from data_work import storage
from dataset.dataset_records import update_dataset_record
from ui import ui


MIN_COMPARISON_RECORDS = 2
SNAPSHOT_PATH = Path("config/rating_comparison_last_snapshot.json")


def _to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def get_scored_records(dataset: dict | None = None) -> list[dict]:
    """Returns dataset records that have a valid user_score."""
    if dataset is None:
        dataset = storage.load_dataset()

    records = []
    for title, movie in dataset.items():
        main_info = movie.get("main_info", {})
        score = _to_float(main_info.get("user_score"))
        if score is None:
            continue
        records.append({
            "title": main_info.get("title") or title,
            "score": score,
        })

    records.sort(key=lambda item: item["score"], reverse=True)
    return records


def build_score_snapshot(old_scores: dict, new_scores: dict) -> dict:
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": "rating_comparison",
        "old_scores": old_scores,
        "new_scores": new_scores,
    }


def save_rating_comparison_snapshot(old_scores: dict, new_scores: dict) -> str:
    snapshot = build_score_snapshot(old_scores, new_scores)
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as file:
        json.dump(snapshot, file, ensure_ascii=False, indent=4)
    return str(SNAPSHOT_PATH)


def build_change_stats(old_scores: dict, new_scores: dict) -> dict:
    diffs = [
        abs(float(new_scores[title]) - float(old_score))
        for title, old_score in old_scores.items()
        if title in new_scores
    ]
    changed_diffs = [diff for diff in diffs if diff > 0]
    changed_count = len(changed_diffs)
    return {
        "total_scored": len(old_scores),
        "changed_count": changed_count,
        "mean_abs_change": sum(changed_diffs) / changed_count if changed_count > 0 else 0,
        "max_change": max(changed_diffs) if changed_count > 0 else 0,
        "over_0_5": sum(1 for diff in changed_diffs if diff > 0.5),
        "over_1_0": sum(1 for diff in changed_diffs if diff > 1.0),
    }


def print_change_preview(stats: dict) -> None:
    print("\nПроверка изменений:")
    print(f"Всего оценённых записей: {stats['total_scored']}")
    print(f"Изменится оценок: {stats['changed_count']}")
    print(f"Среднее изменение: {stats['mean_abs_change']:.3f}")
    print(f"Максимальное изменение: {stats['max_change']:.3f}")
    print(f"Больше 0.5: {stats['over_0_5']}")
    print(f"Больше 1.0: {stats['over_1_0']}")
    if stats["max_change"] > 1.0:
        print("\nВнимание: оценки меняются сильно.")
        print("Возможно, стоит уменьшить диапазон min/max или провести больше сравнений.")


def apply_rating_comparison_scores(
    old_scores: dict,
    new_scores: dict,
    *,
    ask_confirmation: bool = True,
    input_func=input,
) -> dict:
    """Shows preview, writes snapshot, and safely applies user_score patches."""
    stats = build_change_stats(old_scores, new_scores)
    print_change_preview(stats)
    snapshot_path = save_rating_comparison_snapshot(old_scores, new_scores)

    if ask_confirmation:
        answer = input_func("\nПрименить новые оценки? да/нет >> ").strip().casefold()
        if answer not in {"да", "д", "yes", "y"}:
            print("Изменения не применены.")
            print(f"Snapshot сохранён как preview: {snapshot_path}")
            return {
                "ok": False,
                "applied": 0,
                "snapshot_path": snapshot_path,
                "stats": stats,
                "reason": "cancelled",
            }

    applied = 0
    errors = []
    for title, old_score in old_scores.items():
        if title not in new_scores:
            continue
        new_score = float(new_scores[title])
        if abs(new_score - float(old_score)) == 0:
            continue

        result = update_dataset_record(
            title,
            {"main_info": {"user_score": new_score}},
            source_name="rating_comparison",
        )
        if result.ok:
            applied += 1
        else:
            errors.append({
                "title": title,
                "reason": result.reason,
                "message": result.message,
            })

    if len(errors) > 0:
        print("\nЧасть оценок не применена:")
        for error in errors:
            print(f"- {error['title']}: {error['reason']} | {error['message']}")
    else:
        print("\nОценки применены.")
    print(f"Snapshot сохранён: {snapshot_path}")
    print("После изменения оценок рекомендуется запустить LOO обучение.")

    return {
        "ok": len(errors) == 0,
        "applied": applied,
        "snapshot_path": snapshot_path,
        "stats": stats,
        "errors": errors,
        "reason": "applied" if len(errors) == 0 else "partial_error",
    }


def ask_rounds(amount_records: int, input_func=input) -> int:
    max_rounds = amount_records - 1
    while True:
        answer = input_func(f"Введите количество сравнений (1-{max_rounds}) >> ").strip()
        try:
            rounds = int(answer)
        except ValueError:
            print("Некорректный ввод.")
            continue
        if 1 <= rounds <= max_rounds:
            return rounds
        print(f"Значение должно быть от 1 до {max_rounds}.")


def run_comparison_rounds(records: list[dict], rounds: int, *, rng=None, input_func=input) -> tuple[dict, int]:
    if rng is None:
        rng = random

    records = [dict(record) for record in records]
    comparisons = min(rounds, len(records) - 1)
    available_indexes = list(range(len(records) - 1))
    swaps = 0

    for step in range(comparisons):
        distance = rng.randint(1, 2)
        valid_indexes = [index for index in available_indexes if index + distance < len(records)]
        if len(valid_indexes) == 0:
            distance = 1
            valid_indexes = list(available_indexes)
        index = rng.choice(valid_indexes)
        available_indexes.remove(index)

        first = records[index]
        second = records[index + distance]
        reverse_order = rng.randint(1, 2) == 2

        ui.clean_terminal()
        print(f"Раунд {step + 1}/{comparisons}:\n")
        print("Какой сериал нравится больше?\n")
        if reverse_order:
            print(f"1. {second['title']}")
            print(f"2. {first['title']}")
        else:
            print(f"1. {first['title']}")
            print(f"2. {second['title']}")

        while True:
            answer = input_func(">> ").strip()
            if answer in {"1", "2"}:
                break
            print("Некорректный ввод.")

        lower_ranked_selected = answer == ("1" if reverse_order else "2")
        if lower_ranked_selected:
            records[index]["score"], records[index + distance]["score"] = (
                records[index + distance]["score"],
                records[index]["score"],
            )
            swaps += 1

    return {record["title"]: record["score"] for record in records}, swaps


def start_rating_comparison(input_func=input) -> bool:
    records = get_scored_records()
    if len(records) < MIN_COMPARISON_RECORDS:
        print(f"Для rating comparison нужно минимум {MIN_COMPARISON_RECORDS} оценённые записи.")
        return False

    old_scores = {record["title"]: record["score"] for record in records}
    rounds = ask_rounds(len(records), input_func=input_func)
    new_scores, swaps = run_comparison_rounds(records, rounds, input_func=input_func)
    print(f"\nСравнений с перестановкой оценок: {swaps}")
    apply_rating_comparison_scores(old_scores, new_scores, input_func=input_func)
    return True
