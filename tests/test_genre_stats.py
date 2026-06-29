from dataset.genre_stats import build_dataset_genre_catalog


def test_build_dataset_genre_catalog_uses_russian_labels() -> None:
    items = build_dataset_genre_catalog()

    assert len(items) >= 9
    labels = {item["feature"]: item["label_ru"] for item in items}
    assert labels["has_drama"] == "Драма"
    assert labels["has_crime"] == "Криминал"
    assert labels["has_romance"] == "Романтика"


def test_genre_stats_uses_dataset_named_catalog() -> None:
    import inspect

    import dataset.genre_stats as genre_stats

    source = inspect.getsource(genre_stats)
    assert hasattr(genre_stats, "build_dataset_genre_catalog")
    assert hasattr(genre_stats, "show_dataset_genre_catalog")
    assert "build_model_genre_catalog" not in source
    assert "show_model_genres" not in source
