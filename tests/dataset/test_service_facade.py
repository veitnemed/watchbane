"""Dataset service facade tests."""

import importlib


def test_service_facade_exports_core_operations() -> None:
    import dataset.service as service

    assert hasattr(service, "add_dataset_record")
    assert hasattr(service, "update_dataset_record")
    assert hasattr(service, "delete_watched_record")
    assert hasattr(service, "resolve_title_for_add")
    assert hasattr(service, "save_add_title_record")
    assert hasattr(service, "build_score_analytics")
    assert hasattr(service, "get_dataset_stats")
    assert hasattr(service, "build_tmdb_add_defaults")


def test_dataset_package_exports_service() -> None:
    import dataset

    assert hasattr(dataset, "service")
    assert dataset.service is importlib.import_module("dataset.service")


def test_service_facade_resolve_title_data_accepts_media_type(monkeypatch) -> None:
    import dataset.service as service

    def fake_resolve(title, country, **kwargs):
        captured.update({"title": title, "country": country, **kwargs})
        return {"found": False, "media_type": kwargs.get("media_type")}

    captured = {}

    monkeypatch.setattr("dataset.resolve.service.search_tmdb_title_for_add", lambda *_args, **_kwargs: {
        "data": None,
        "error": {"error": "not_found"},
        "status": "not_found",
    })

    result = service.resolve_title_data_for_add("Watchmen", "US", media_type="movie")

    assert result["media_type"] == "movie"
