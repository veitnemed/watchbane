"""Печать карточек и превью для поиска тайтлов."""

from config import constant
from config import scheme
from dataset import title_resolve


def short_text(value, limit: int = 50) -> str:
    """Обрезает текст для короткого предпросмотра."""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def print_sql_training_preview(sql_data: dict) -> None:
    """Показывает краткую SQL-сводку перед API-обогащением."""
    genres_line = ", ".join(sql_data.get("genres", []) or []) or "нет данных"
    print("\nSQL нашёл базовый объект:")
    print(f"Название: {sql_data.get('title')}")
    print(f"Оригинальное: {sql_data.get('original_title') or 'нет данных'}")
    print(f"Год: {sql_data.get('year') or 'нет данных'}")
    print(f"Жанры: {genres_line}")
    print(f"IMDb: {sql_data.get('imdb_rating') or '-'} / голосов {sql_data.get('imdb_votes') or '-'}")


def print_api_training_preview(api_data: dict) -> None:
    """Показывает краткую API-сводку для будущего сохранения."""
    countries = title_resolve.extract_api_countries(api_data)
    genres_line = ", ".join(title_resolve.extract_api_genres(api_data)) or "нет данных"
    raw_scores = title_resolve.extract_api_raw_scores(api_data)

    print("\nAPI обогатил объект:")
    print(f"Название: {title_resolve.extract_api_title(api_data) or 'нет данных'}")
    print(f"Год: {api_data.get('year') or 'нет данных'}")
    print(f"Страны: {countries if countries != 'None' else 'нет данных'}")
    print(f"Жанры: {genres_line}")
    print(f"KP: {raw_scores.get('kp_score') or '-'} / голосов {raw_scores.get('kp_votes') or '-'}")
    print(f"IMDb: {raw_scores.get('imdb_score') or '-'} / голосов {raw_scores.get('imdb_votes') or '-'}")
    print(
        f"Описание: {short_text(api_data.get('description') or api_data.get('shortDescription'), 80) or 'нет данных'}"
    )


def print_final_training_preview(defaults: dict) -> None:
    """Показывает итоговые значения, которые попадут в форму добавления."""
    genres = [
        constant.FIELD_LABELS.get(feature, feature)
        for feature, value in defaults.get(scheme.GENRE, {}).items()
        if int(value or 0) > 0
    ]
    raw_scores = defaults.get(scheme.RAW_SCORES, {})

    print("\nИтог для добавления:")
    print(f"Название: {defaults.get(scheme.MAIN_INFO, {}).get('title') or 'нет данных'}")
    print(f"Год: {defaults.get(scheme.MAIN_INFO, {}).get('year') or 'нет данных'}")
    print(f"KP: {raw_scores.get('kp_score') or '-'} / голосов {raw_scores.get('kp_votes') or '-'}")
    print(f"IMDb: {raw_scores.get('imdb_score') or '-'} / голосов {raw_scores.get('imdb_votes') or '-'}")
    print(f"Жанры: {', '.join(genres) if len(genres) > 0 else 'нет данных'}")


def print_sql_title_result(data: dict) -> None:
    """Печатает компактную карточку результата SQL-поиска."""
    title = data.get("title") or "нет данных"
    original_title = data.get("original_title") or "нет данных"
    year = data.get("year") or "?"
    genres = ", ".join(data.get("genres", [])) or "нет данных"
    production_countries = ", ".join(data.get("production_countries", [])) or "нет данных в IMDb light"
    title_regions = ", ".join(data.get("title_region_countries", [])) or "нет данных"
    description = short_text(data.get("description"), 180) or "нет данных в IMDb light"
    match = data.get("match", {})
    credits = data.get("credits", {})
    directors = ", ".join(credits.get("directors", [])[:5]) or "нет данных"
    actors = ", ".join((credits.get("actors") or credits.get("actresses") or [])[:8]) or "нет данных"

    print(f"\n{title} ({year})")
    print(f"Оригинальное название: {original_title}")
    print(f"Жанры: {genres}")
    print(f"Страна производства: {production_countries}")
    print(f"Описание: {description}")
    print(f"Регионы локализаций названия: {title_regions}")
    print(f"IMDb: {data.get('imdb_rating', '-')} | голосов: {data.get('imdb_votes', '-')}")
    print(f"Режиссеры: {directors}")
    print(f"Актеры: {actors}")
    print(f"Совпадение: {match.get('matched_source')} | score: {match.get('score')}")
    print(f"Matched titles: {', '.join(match.get('matched_titles', [])[:8]) or 'нет данных'}")
    print(f"URL: {data.get('url')}")

    alternatives = data.get("alternatives", [])
    if len(alternatives) > 0:
        print("\nПохожие варианты:")
        for idx, item in enumerate(alternatives[:5], start=1):
            print(
                f"{idx}) {item.get('title')} ({item.get('year')}) "
                f"| IMDb: {item.get('imdb_rating')} | votes: {item.get('imdb_votes')}"
            )
