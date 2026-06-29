"""Прогоняет локальный SQL-поиск по всем сериалам из dataset.json."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from time import perf_counter


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apis import imdb_sql as sql_search
from storage import data as storage_data
from config import constant


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SQL search across all saved titles.")
    parser.add_argument(
        "--country",
        default="Россия",
        help="Country hint used during ranking.",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Path to dataset.json. Defaults to the project constant path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit how many titles to process.",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Print every result instead of only failures and weak matches.",
    )
    parser.add_argument(
        "--weak-score",
        type=float,
        default=1.5,
        help="Print results with score above this threshold even when found.",
    )
    return parser.parse_args()


def pick_title(movie: dict, fallback: str) -> str:
    main_info = movie.get("main_info", {})
    return str(main_info.get("title", fallback)).strip()


def pick_year(movie: dict) -> str:
    main_info = movie.get("main_info", {})
    year = main_info.get("year")
    return "" if year is None else str(year)


def run_all_titles() -> None:
    args = parse_args()
    if args.dataset:
        constant.FILE_NAME = str(Path(args.dataset))
    data = storage_data.load_dataset()
    titles = list(data.items())
    if args.limit is not None:
        titles = titles[: max(args.limit, 0)]

    total = len(titles)
    if total == 0:
        print("dataset.json пуст.")
        return

    found = 0
    not_found = 0
    weak = 0
    started = perf_counter()
    print(f"SQL test started: {total} titles")

    for index, (dataset_title, movie) in enumerate(titles, start=1):
        title = pick_title(movie, dataset_title)
        year = pick_year(movie)
        result = sql_search.search_title_in_sql(title, args.country)

        if result["ok"] is False:
            not_found += 1
            print(f"{index}/{total} NOT FOUND | {title} | {result['error']} | {result['details']}")
            continue

        found += 1
        data_row = result["data"]
        score = float(data_row.get("match", {}).get("score", 0))
        best_title = data_row.get("title") or ""
        best_year = data_row.get("year")
        best_rating = data_row.get("imdb_rating")
        best_votes = data_row.get("imdb_votes")

        is_weak = score > args.weak_score
        if is_weak:
            weak += 1

        if args.show_all or is_weak:
            print(
                f"{index}/{total} OK | {title} -> {best_title} ({best_year}) | "
                f"rating {best_rating} | votes {best_votes} | score {score}"
            )

    elapsed = perf_counter() - started
    print(
        f"SUMMARY | total={total} found={found} not_found={not_found} weak={weak} "
        f"time={elapsed:.1f}s"
    )


if __name__ == "__main__":
    run_all_titles()
