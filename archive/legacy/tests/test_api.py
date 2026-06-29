"""Тесты API-модуля поиска сериалов."""

from pathlib import Path
import contextlib
import io
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apis import kp_api as api


def assert_check(text: str, result: bool) -> None:
    print(f"{text}: {result}")
    assert result, text


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.text.encode("utf-8")


def make_opener(text: str):
    def opener(request, timeout=10):
        return FakeResponse(text)
    return opener


def test_empty_input() -> None:
    empty_title = api.find_series("", "США", token="token")
    empty_country = api.find_series(
        "Euphoria",
        "",
        token="token",
        opener=make_opener("""
        {
            "docs": [
                {
                    "id": 1,
                    "name": "Эйфория",
                    "alternativeName": "Euphoria",
                    "year": 2019,
                    "type": "tv-series",
                    "countries": [{"name": "США"}],
                    "rating": {"kp": 8.0, "imdb": 8.1},
                    "votes": {"kp": 100000, "imdb": 300000}
                }
            ]
        }
        """),
    )

    assert_check("Пустое название возвращает ошибку", empty_title["error"] == "empty_title")
    assert_check("Пустая страна ищет без country filter", empty_country["ok"] is True)
    assert_check("Без country filter берёт лучший match", empty_country["data"]["title"] == "Эйфория")


def test_missing_token() -> None:
    result = api.find_series("Во все тяжкие", "США", token=None)

    assert_check("Без токена возвращается ошибка", result["error"] == "missing_token")


def test_invalid_json() -> None:
    result = api.find_series(
        "Во все тяжкие",
        "США",
        token="token",
        opener=make_opener("not json"),
    )

    assert_check("Некорректный JSON возвращает ошибку", result["error"] == "invalid_json")


def test_not_found() -> None:
    result = api.find_series(
        "Неизвестный сериал",
        "США",
        token="token",
        opener=make_opener('{"docs": []}'),
    )

    assert_check("Пустая выдача возвращает not_found", result["error"] == "not_found")


def test_successful_series_search() -> None:
    payload = """
    {
        "docs": [
            {
                "id": 1,
                "name": "Во все тяжкие",
                "alternativeName": "Breaking Bad",
                "year": 2008,
                "type": "tv-series",
                "countries": [{"name": "США"}],
                "rating": {"kp": 8.9, "imdb": 9.5},
                "votes": {"kp": 900000, "imdb": 2300000}
            }
        ]
    }
    """
    result = api.find_series(
        "Во все тяжкие",
        "США",
        token="token",
        opener=make_opener(payload),
    )

    assert_check("Успешный поиск возвращает ok", result["ok"] is True)
    assert_check("Название сериала извлечено", result["data"]["title"] == "Во все тяжкие")
    assert_check("Страна извлечена", result["data"]["countries"] == ["США"])
    assert_check("Рейтинг KP извлечен", result["data"]["kp_score"] == 8.9)
    assert_check("Голоса IMDb извлечены", result["data"]["imdb_votes"] == 2300000)


def test_raw_series_search() -> None:
    payload = """
    {
        "docs": [
            {
                "id": 10,
                "name": "Тестовый сериал",
                "year": 2025,
                "type": "tv-series",
                "countries": [{"name": "Россия"}],
                "rating": {"kp": 7.1},
                "rawOnlyField": {"nested": true}
            }
        ]
    }
    """
    result = api.find_series_raw(
        "Тестовый сериал",
        "Россия",
        token="token",
        opener=make_opener(payload),
    )

    assert_check("Сырой поиск возвращает ok", result["ok"] is True)
    assert_check("Сырой поиск сохраняет полный JSON", result["data"]["rawOnlyField"]["nested"] is True)


def test_format_api_movie_lines() -> None:
    movie = {
        "id": 10,
        "name": "Тестовый сериал",
        "year": 2025,
        "type": "tv-series",
        "countries": [{"name": "Россия"}],
        "genres": [{"name": "драма"}],
        "rating": {"kp": 7.1},
        "votes": {"kp": 1000},
        "rawOnlyField": {"nested": True},
    }
    lines = api.format_api_movie_lines(movie)

    assert_check("Красивый вывод содержит заголовок", "API признаки сериала" in lines)
    assert_check("Красивый вывод содержит название", "Название: Тестовый сериал" in lines)
    assert_check("Красивый вывод содержит страны", "Страны: Россия" in lines)
    assert_check("Красивый вывод показывает остальные поля", "rawOnlyField" in "\n".join(lines))


def test_country_mismatch() -> None:
    payload = """
    {
        "docs": [
            {
                "id": 1,
                "name": "Dark",
                "year": 2017,
                "type": "tv-series",
                "countries": [{"name": "Германия"}]
            }
        ]
    }
    """
    result = api.find_series(
        "Dark",
        "США",
        token="token",
        opener=make_opener(payload),
    )

    assert_check("Если страна не совпала, возвращается ошибка", result["error"] == "country_not_found")


def test_dict_to_lines() -> None:
    lines = api.dict_to_lines({
        "ok": True,
        "data": {
            "title": "Dark",
            "year": 2017,
        },
        "error": None,
    })

    assert_check("Верхний ключ печатается как key: value", "ok: True" in lines)
    assert_check("Вложенный словарь печатается отдельным блоком", "data:" in lines)
    assert_check("Вложенное значение печатается с отступом", "    title: Dark" in lines)


def test_request_series_info_prints_dict() -> None:
    payload = """
    {
        "docs": [
            {
                "id": 1,
                "name": "Dark",
                "year": 2017,
                "type": "tv-series",
                "countries": [{"name": "Германия"}]
            }
        ]
    }
    """
    answers = iter(["Dark", "Германия"])
    old_input = api.input if hasattr(api, "input") else None
    api.input = lambda text: next(answers)

    try:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = api.request_series_info(
                token="token",
                opener=make_opener(payload),
            )
    finally:
        if old_input is None:
            del api.input
        else:
            api.input = old_input

    printed = output.getvalue()
    assert_check("Интерактивный запрос возвращает ok", result["ok"] is True)
    assert_check("Результат печатается как key: value", "title: Dark" in printed)


def run_tests() -> None:
    print("=== Тесты API-модуля ===")
    test_empty_input()
    test_missing_token()
    test_invalid_json()
    test_not_found()
    test_successful_series_search()
    test_raw_series_search()
    test_format_api_movie_lines()
    test_country_mismatch()
    test_dict_to_lines()
    test_request_series_info_prints_dict()
    print("\nПроверки API-модуля пройдены: True")


if __name__ == "__main__":
    run_tests()
