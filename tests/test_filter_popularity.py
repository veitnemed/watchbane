from config import constant
from dataset.filter_popularity import (
    build_dataset_country_popularity,
    build_dataset_genre_popularity,
)


def _movie(*, country: str = "", genres: list[str] | None = None) -> dict:
    genre_section = {feature: 0 for feature in constant.GENRE}
    movie = {
        "main_info": {
            "title": "Title",
            "user_score": 8.0,
            "country": country,
        },
        constant.GENRE_SECTION: genre_section,
    }
    if genres:
        movie["genres"] = genres
    return movie


def test_build_dataset_genre_popularity_sorts_by_count() -> None:
    data = {
        "a": _movie(genres=["Драма"]),
        "b": _movie(genres=["Драма"]),
        "c": _movie(genres=["Драма", "Комедия"]),
        "d": _movie(genres=["Комедия"]),
    }

    rows = build_dataset_genre_popularity(data)

    assert [(row["label"], row["count"]) for row in rows] == [
        ("Драма", 3),
        ("Комедия", 2),
    ]


def test_build_dataset_country_popularity_maps_russia_to_ru() -> None:
    data = {
        "a": _movie(country="Россия"),
        "b": _movie(country="Россия"),
        "c": _movie(country="США"),
    }

    rows = build_dataset_country_popularity(data)

    assert rows[0] == {"code": "RU", "label": "Россия", "count": 2}
    assert rows[1] == {"code": "US", "label": "США", "count": 1}


def test_get_search_filter_chip_options_view_uses_dataset_popularity(monkeypatch) -> None:
    from candidates import service as candidate_service

    dataset = {
        "a": _movie(country="Россия", genres=["Драма"]),
        "b": _movie(country="США", genres=["Драма", "Комедия"]),
    }
    monkeypatch.setattr("candidates.service.storage_data.load_dataset", lambda: dataset)
    monkeypatch.setattr("candidates.service.get_pool_view", lambda: [])
    monkeypatch.setattr(
        "candidates.service.collect_search_genre_options",
        lambda _candidates: ["Триллер"],
    )
    monkeypatch.setattr(
        "candidates.service.collect_search_country_options",
        lambda _candidates: [{"code": "GB", "label": "Великобритания"}],
    )

    view = candidate_service.get_search_filter_chip_options_view()

    assert view["source"] == "dataset"
    assert view["dataset_total"] == 2
    assert view["genres"][0]["label"] == "Драма"
    assert view["genres"][0]["count"] == 2
    assert view["genres"][-1] == {"label": "Триллер", "count": 0}
    assert view["countries"][0]["code"] == "RU"
    assert view["countries"][0]["count"] == 1
    assert view["countries"][-1] == {"code": "GB", "label": "Великобритания", "count": 0}


def test_get_search_filter_chip_options_view_falls_back_when_dataset_empty(monkeypatch) -> None:
    from candidates import service as candidate_service

    monkeypatch.setattr("candidates.service.storage_data.load_dataset", lambda: {})
    monkeypatch.setattr("candidates.service.get_pool_view", lambda: [])
    monkeypatch.setattr(
        "candidates.service.collect_search_genre_options",
        lambda _candidates: ["Драма"],
    )
    monkeypatch.setattr(
        "candidates.service.collect_search_country_options",
        lambda _candidates: [],
    )

    view = candidate_service.get_search_filter_chip_options_view()

    assert view["is_empty"] is True
    assert view["source"] == "fallback"
    assert view["genres"] == [{"label": "Драма", "count": 0}]
    assert view["countries"][0]["code"] == "RU"
