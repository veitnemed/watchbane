"""Genre statistics and catalog for watched dataset (TMDb metadata)."""

from collections import Counter

from dataset.analytics.helpers import collect_analytics_entry_items
from storage import data as storage_data


def get_dataset_title(dataset_title: str, movie: dict) -> str:
    """Возвращает название сериала из записи датасета."""
    return str(movie.get("main_info", {}).get("title", dataset_title)).strip()


def _genre_labels_from_entry(movie: dict, meta: dict | None) -> list[str]:
    for item in collect_analytics_entry_items([("", movie, meta or {})]):
        genres = item.get("genres") or []
        if genres:
            return list(genres)
    return []


def count_genres_from_dataset(data: dict, meta: dict | None = None) -> dict:
    """Считает жанры по TMDb metadata watched dataset."""
    meta = meta if isinstance(meta, dict) else storage_data.load_meta()
    genre_counter = Counter()
    without_genres = []

    for dataset_title, movie in data.items():
        title = get_dataset_title(dataset_title, movie)
        meta_obj = meta.get(dataset_title) if isinstance(meta, dict) else None
        genres = _genre_labels_from_entry(movie, meta_obj if isinstance(meta_obj, dict) else None)
        if len(genres) == 0:
            without_genres.append(title)
            continue
        for genre in genres:
            genre_counter[genre] += 1

    return {
        "genre_counter": genre_counter,
        "without_genres": without_genres,
    }


def print_genre_report(result: dict) -> None:
    """Печатает отчет по жанрам текущего датасета."""
    genre_counter = result["genre_counter"]

    print("\nЖАНРЫ (TMDb metadata)")
    print("=" * 50)
    if len(genre_counter) == 0:
        print("Жанры не найдены.")
    else:
        for genre, count in genre_counter.most_common():
            print(f"{genre}: {count}")

    print("\nИТОГО")
    print("=" * 50)
    print(f"Жанров: {len(genre_counter)}")
    print(f"Без TMDb-жанров: {len(result['without_genres'])}")

    if len(result["without_genres"]) > 0:
        print("\nБез жанров:")
        for title in result["without_genres"]:
            print(f"- {title}")


def show_dataset_genres() -> None:
    """Показывает жанры текущего датасета из TMDb metadata."""
    data = storage_data.load_dataset()
    if len(data) == 0:
        print("Датасет пуст.")
        return

    result = count_genres_from_dataset(data)
    print_genre_report(result)


def build_dataset_genre_catalog() -> list[dict]:
    """Возвращает уникальные TMDb-жанры, встречающиеся в watched dataset."""
    data = storage_data.load_dataset()
    meta = storage_data.load_meta()
    result = count_genres_from_dataset(data, meta)
    items = []
    for index, (label, count) in enumerate(result["genre_counter"].most_common(), start=1):
        items.append(
            {
                "index": index,
                "label": label,
                "count": count,
            }
        )
    return items


def show_dataset_genre_catalog() -> None:
    """Печатает каталог TMDb-жанров, найденных в watched dataset."""
    items = build_dataset_genre_catalog()

    print("\nЖАНРЫ WATCHED (TMDb)")
    print("=" * 50)
    if len(items) == 0:
        print("TMDb-жанры не найдены.")
        return

    for item in items:
        print(f"{item['index']}) {item['label']} — {item['count']}")

    print("\nИТОГО")
    print("=" * 50)
    print(f"Уникальных жанров: {len(items)}")
