"""Genre statistics and catalog for watched dataset."""

from collections import Counter

from config import constant
from config import genre_tags
from storage import data as storage_data


def get_dataset_title(dataset_title: str, movie: dict) -> str:
    """Возвращает название сериала из записи датасета."""
    return str(movie.get("main_info", {}).get("title", dataset_title)).strip()


def _genre_labels_from_movie(movie: dict) -> list[str]:
    genre_section = movie.get(constant.GENRE_SECTION, {})
    if not isinstance(genre_section, dict):
        return []

    labels: list[str] = []
    for feature in constant.GENRE:
        if genre_section.get(feature) != 1:
            continue
        label = constant.FIELD_LABELS.get(feature, feature)
        text = str(label).strip()
        if text and text not in labels:
            labels.append(text)
    return labels


def count_genres_from_dataset(data: dict) -> dict:
    """Считает жанры по локальной жанровой разметке watched dataset."""
    genre_counter = Counter()
    without_genres = []

    for dataset_title, movie in data.items():
        title = get_dataset_title(dataset_title, movie)
        genres = _genre_labels_from_movie(movie)
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

    print("\nЖАНРЫ")
    print("=" * 50)
    if len(genre_counter) == 0:
        print("Жанры не найдены.")
    else:
        for genre, count in genre_counter.most_common():
            print(f"{genre}: {count}")

    print("\nИТОГО")
    print("=" * 50)
    print(f"Жанров: {len(genre_counter)}")
    print(f"Без жанровой разметки: {len(result['without_genres'])}")

    if len(result["without_genres"]) > 0:
        print("\nБез жанров:")
        for title in result["without_genres"]:
            print(f"- {title}")


def show_dataset_genres() -> None:
    """Показывает все жанры текущего датасета из локальной разметки."""
    data = storage_data.load_dataset()
    if len(data) == 0:
        print("Датасет пуст.")
        return

    result = count_genres_from_dataset(data)
    print_genre_report(result)


def build_dataset_genre_catalog() -> list[dict]:
    """Возвращает жанровые признаки dataset с русскими подписями из config/genre_tags.json."""
    tags = genre_tags.load_genre_tags()
    items = []
    for index, (feature, settings) in enumerate(sorted(tags.items()), start=1):
        label_ru = str(settings.get("label") or feature).strip()
        items.append(
            {
                "index": index,
                "feature": feature,
                "label_ru": label_ru,
                "translation": str(settings.get("translation") or "").strip(),
                "source": str(settings.get("source") or "").strip(),
            }
        )
    return items


def show_dataset_genre_catalog() -> None:
    """Печатает каталог жанровых признаков dataset (has_*) с переводом на русский."""
    items = build_dataset_genre_catalog()

    print("\nЖАНРЫ DATASET")
    print("=" * 50)
    if len(items) == 0:
        print("Жанровые признаки не заданы.")
        return

    for item in items:
        print(f"{item['index']}) {item['feature']} — {item['label_ru']}")

    print("\nИТОГО")
    print("=" * 50)
    print(f"Признаков: {len(items)}")
