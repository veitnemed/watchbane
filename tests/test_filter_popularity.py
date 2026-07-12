from config import constant
from dataset.filter_popularity import (
    build_dataset_country_popularity,
    build_dataset_genre_popularity,
)


def _movie(*, country: str = "", genres: list[str] | None = None) -> dict:
    movie = {
        "main_info": {
            "title": "Title",
            "user_score": 8.0,
            "country": country,
        },
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


def test_build_dataset_country_popularity_displays_soviet_union_label() -> None:
    data = {
        "a": _movie(country="SU"),
        "b": _movie(country="USSR"),
        "c": _movie(country="Soviet Union"),
    }

    rows = build_dataset_country_popularity(data)

    assert rows == [{"code": "SU", "label": "СССР", "count": 3}]


def test_collect_search_country_options_displays_soviet_union_label() -> None:
    from candidates.pool.search_helpers import collect_search_country_options

    rows = collect_search_country_options(
        [
            {"title": "A", "country_codes": ["SU"]},
            {"title": "B", "countries": ["USSR"]},
        ]
    )

    assert {"code": "SU", "label": "СССР"} in rows


def test_collect_search_genre_options_splits_long_combined_labels() -> None:
    from candidates.pool.search_helpers import collect_search_genre_options

    rows = collect_search_genre_options(
        [
            {"title": "A", "genre_keys": ["action_adventure"]},
            {"title": "B", "genres_tmdb": ["Sci-Fi & Fantasy"]},
        ]
    )

    assert "Боевик" in rows
    assert "Приключения" in rows
    assert "Фантастика" in rows
    assert "Фэнтези" in rows
    assert "Боевик/приключения" not in rows


def test_collect_search_country_options_displays_known_iso_codes() -> None:
    from candidates.pool.search_helpers import collect_search_country_options

    rows = collect_search_country_options(
        [
            {"title": "A", "country_codes": ["CO", "ID", "IL", "IS", "KE", "LU", "ZA"]},
            {"title": "B", "country_codes": ["NZ"]},
        ]
    )

    labels_by_code = {row["code"]: row["label"] for row in rows}

    assert labels_by_code["CO"] == "Колумбия"
    assert labels_by_code["ID"] == "Индонезия"
    assert labels_by_code["IL"] == "Израиль"
    assert labels_by_code["IS"] == "Исландия"
    assert labels_by_code["KE"] == "Кения"
    assert labels_by_code["LU"] == "Люксембург"
    assert labels_by_code["ZA"] == "Южная Африка"
    assert labels_by_code["NZ"] == "Новая Зеландия"
    assert not any(row["label"] == row["code"] for row in rows)


def test_collect_search_country_options_skips_unknown_iso_code() -> None:
    from candidates.pool.search_helpers import collect_search_country_options

    rows = collect_search_country_options(
        [
            {"title": "A", "country_codes": ["ZZ"]},
            {"title": "B", "country_codes": ["RU"]},
        ]
    )

    assert rows == [{"code": "RU", "label": "Россия"}]


def test_merge_country_popularity_normalizes_pool_code_labels() -> None:
    from candidates.views.filter_popularity import merge_country_popularity_with_pool

    rows = merge_country_popularity_with_pool(
        [],
        [
            {"code": "CO", "label": "CO"},
            {"code": "ZZ", "label": "ZZ"},
        ],
    )

    assert rows == [{"code": "CO", "label": "Колумбия", "count": 0}]


def test_get_search_filter_chip_options_view_uses_dataset_popularity(monkeypatch) -> None:
    from candidates import service as candidate_service
    from candidates import search_service

    dataset = {
        "a": _movie(country="Россия", genres=["Драма"]),
        "b": _movie(country="США", genres=["Драма", "Комедия"]),
    }
    monkeypatch.setattr("candidates.search_service.storage_data.load_dataset", lambda: dataset)
    monkeypatch.setattr("candidates.search_service.get_pool_view", lambda: [])
    monkeypatch.setattr(
        "candidates.search_service.collect_search_genre_options",
        lambda _candidates: ["Триллер"],
    )
    monkeypatch.setattr(
        "candidates.search_service.collect_search_country_options",
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


def test_get_search_filter_chip_options_view_does_not_show_raw_su_code(monkeypatch) -> None:
    from candidates import service as candidate_service

    dataset = {
        "a": _movie(country="Россия"),
        "b": _movie(country="США"),
        "c": _movie(country="SU"),
    }
    monkeypatch.setattr("candidates.search_service.storage_data.load_dataset", lambda: dataset)
    monkeypatch.setattr("candidates.search_service.get_pool_view", lambda: [])
    monkeypatch.setattr(
        "candidates.search_service.collect_search_genre_options",
        lambda _candidates: [],
    )
    monkeypatch.setattr(
        "candidates.search_service.collect_search_country_options",
        lambda _candidates: [],
    )

    view = candidate_service.get_search_filter_chip_options_view()

    su_row = next(row for row in view["countries"] if row["code"] == "SU")
    assert su_row["label"] == "СССР"
    assert su_row["label"] != "SU"


def test_get_search_filter_chip_options_view_falls_back_when_dataset_empty(monkeypatch) -> None:
    from candidates import service as candidate_service

    monkeypatch.setattr("candidates.search_service.storage_data.load_dataset", lambda: {})
    monkeypatch.setattr("candidates.search_service.get_pool_view", lambda: [])
    monkeypatch.setattr(
        "candidates.search_service.collect_search_genre_options",
        lambda _candidates: ["Драма"],
    )
    monkeypatch.setattr(
        "candidates.search_service.collect_search_country_options",
        lambda _candidates: [],
    )

    view = candidate_service.get_search_filter_chip_options_view()

    assert view["is_empty"] is True
    assert view["source"] == "fallback"
    assert view["genres"] == [{"label": "Драма", "count": 0}]
    assert view["countries"][0]["code"] == "RU"
