from desktop.shared.detail.additional_info import format_runtime_minutes, format_tmdb_status
from desktop.shared.detail.main_info import build_main_info_items


def _value_for(items: list[dict], label: str):
    for item in items:
        if item.get("label") == label:
            return item.get("value")
    return None


def test_movie_detail_info_translates_status_country_and_runtime() -> None:
    items = build_main_info_items(
        {
            "media_type": "movie",
            "object_type": "movie",
            "country": "United States of America",
            "watch_providers": None,
            "tmdb_votes": 2600,
            "status": "Released",
            "runtime": 162,
        },
        data_language="ru",
    )

    assert _value_for(items, "Страна") == "США"
    assert _value_for(items, "Статус") == "Выпущен"
    assert _value_for(items, "Продолжительность") == "2 ч 42 мин"
    assert _value_for(items, "Длительность серии") is None


def test_movie_runtime_formatter_handles_edge_cases() -> None:
    assert format_runtime_minutes(45, data_language="ru") == "45 мин"
    assert format_runtime_minutes(60, data_language="ru") == "1 ч"
    assert format_runtime_minutes(61, data_language="ru") == "1 ч 1 мин"
    assert format_runtime_minutes(None, data_language="ru") is None
    assert format_runtime_minutes(0, data_language="ru") is None


def test_tmdb_movie_status_released_is_localized() -> None:
    assert format_tmdb_status("Released", data_language="ru") == "Выпущен"
