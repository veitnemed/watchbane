from dataset.genre_stats import build_dataset_genre_catalog


def test_build_dataset_genre_catalog_uses_tmdb_labels(monkeypatch) -> None:
    monkeypatch.setattr(
        "dataset.genres.stats.storage_data.load_dataset",
        lambda: {
            "Show": {
                "main_info": {"title": "Show", "user_score": 8.0, "year": 2020, "country": "US"},
                "raw_scores": {"tmdb_score": 7.5},
            }
        },
    )
    monkeypatch.setattr(
        "dataset.genres.stats.storage_data.load_meta",
        lambda: {"Show": {"genres": ["Drama", "Crime"]}},
    )

    items = build_dataset_genre_catalog()

    labels = {item["label"] for item in items}
    assert "Drama" in labels
    assert "Crime" in labels


def test_genre_stats_uses_dataset_named_catalog() -> None:
    import inspect

    import dataset.genre_stats as genre_stats

    source = inspect.getsource(genre_stats)
    assert hasattr(genre_stats, "build_dataset_genre_catalog")
    assert hasattr(genre_stats, "show_dataset_genre_catalog")
    assert "build_model_genre_catalog" not in source
    assert "show_model_genres" not in source
