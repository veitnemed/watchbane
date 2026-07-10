"""Печать карточек и превью для поиска тайтлов."""

from config import scheme
from dataset.resolve.countries import extract_country_value
from dataset.resolve.defaults import extract_tmdb_description, extract_tmdb_raw_scores, extract_tmdb_title
from dataset.resolve.genres import extract_tmdb_genres


def short_text(value, limit: int = 50) -> str:
    """Обрезает текст для короткого предпросмотра."""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def print_api_add_preview(api_data: dict) -> None:
    """Показывает краткую TMDb-сводку для будущего сохранения."""
    countries = extract_country_value(api_data)
    genres_line = ", ".join(extract_tmdb_genres(api_data)) or "нет данных"
    raw_scores = extract_tmdb_raw_scores(api_data)

    print("\nTMDb обогатил объект:")
    print(f"Название: {extract_tmdb_title(api_data) or 'нет данных'}")
    print(f"Год: {api_data.get('year') or 'нет данных'}")
    print(f"Страны: {countries or 'нет данных'}")
    print(f"Жанры: {genres_line}")
    print(f"TMDb: {raw_scores.get('tmdb_score') or '-'} / голосов {raw_scores.get('tmdb_votes') or '-'}")
    print(f"Описание: {short_text(extract_tmdb_description(api_data), 80) or 'нет данных'}")


def print_final_add_preview(defaults: dict) -> None:
    """Показывает итоговые значения, которые попадут в форму добавления."""
    genres = extract_tmdb_genres(defaults)
    raw_scores = defaults.get(scheme.RAW_SCORES, {})

    print("\nИтог для добавления:")
    print(f"Название: {defaults.get(scheme.MAIN_INFO, {}).get('title') or 'нет данных'}")
    print(f"Год: {defaults.get(scheme.MAIN_INFO, {}).get('year') or 'нет данных'}")
    print(f"TMDb: {raw_scores.get('tmdb_score') or '-'} / голосов {raw_scores.get('tmdb_votes') or '-'}")
    print(f"Жанры: {', '.join(genres) if len(genres) > 0 else 'нет данных'}")
