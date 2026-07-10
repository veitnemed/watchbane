from dataset.genres.stats import build_dataset_genre_catalog


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


def test_genre_stats_module_exports_catalog() -> None:
    import dataset.genres.stats as genre_stats

    assert hasattr(genre_stats, "build_dataset_genre_catalog")
    assert hasattr(genre_stats, "show_dataset_genre_catalog")
