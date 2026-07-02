"""Human-readable reasons for candidate search results."""

from __future__ import annotations

from app.core import filters
from app.core.ranking import calculate_quality_score, imdb_vote_weight, tmdb_vote_weight
from candidates.models import country_schema, genre_schema
from candidates.models.schema import coerce_candidate_number, normalize_candidate_record


def _number(value) -> float | None:
    coerced = coerce_candidate_number(value)
    if coerced is None:
        return None
    return float(coerced)


def explain_candidate(candidate: dict, criteria: dict | None = None) -> list[str]:
    """Returns short reasons why a candidate belongs in the result list."""
    criteria = criteria or {}
    candidate = normalize_candidate_record(candidate)
    reasons = []

    quality_score = calculate_quality_score(candidate)
    reasons.append(f"Оценка качества: {quality_score:.2f}")

    kp_score = _number(candidate.get("kp_score"))
    kp_votes = _number(candidate.get("kp_votes")) or 0
    imdb_score = _number(candidate.get("imdb_score"))
    imdb_votes = _number(candidate.get("imdb_votes")) or 0
    tmdb_score = _number(candidate.get("tmdb_score"))
    tmdb_votes = _number(candidate.get("tmdb_votes")) or 0

    if tmdb_score is None:
        reasons.append("TMDb не учтён: нет оценки")
    else:
        signal = "слабый" if tmdb_vote_weight(tmdb_votes) <= 0.55 else "нормальный"
        if tmdb_votes >= 1000:
            signal = "сильный"
        if tmdb_score >= 7.5:
            reasons.append(f"Высокий TMDb: {tmdb_score:.1f}")
        else:
            reasons.append(f"TMDb учтён как {signal} сигнал: {tmdb_score:.1f}")
    if tmdb_votes >= 100:
        reasons.append(f"Много голосов TMDb: {int(tmdb_votes)}")

    if kp_score is not None:
        if kp_score >= 7.5:
            reasons.append(f"Высокий KP: {kp_score:.1f}")
        else:
            reasons.append(f"KP учтён: {kp_score:.1f}")
    if kp_votes >= 1000:
        reasons.append(f"Много голосов KP: {int(kp_votes)}")

    if imdb_score is None:
        reasons.append("IMDb не учтён: нет оценки")
    elif imdb_votes < 300:
        reasons.append(f"IMDb почти не учтён: мало голосов ({int(imdb_votes)})")
    else:
        signal = "слабый" if imdb_vote_weight(imdb_votes) <= 0.15 else "нормальный"
        if imdb_votes >= 5000:
            signal = "сильный"
        reasons.append(f"IMDb учтён как {signal} сигнал: {imdb_score:.1f}, голосов {int(imdb_votes)}")

    if filters.candidate_matches(candidate, {**criteria, "country": criteria.get("country")}) and criteria.get("country"):
        country = country_schema.candidate_country_for_display(candidate)
        reasons.append(f"Подходит по стране: {country or criteria.get('country')}")

    if criteria.get("year_min") or criteria.get("min_year") or criteria.get("year_from"):
        reasons.append("Подходит по нижней границе года")
    if criteria.get("year_max") or criteria.get("max_year") or criteria.get("year_to"):
        reasons.append("Подходит по верхней границе года")

    include_genres = criteria.get("include_genres") or criteria.get("genres") or []
    if include_genres:
        genres = ", ".join(genre_schema.candidate_genres_for_display(candidate)) or "нет данных"
        reasons.append(f"Подходит по жанрам: {genres}")

    if criteria.get("only_unwatched", True):
        reasons.append("Не просмотрен")
    if criteria.get("hide_hidden", True):
        reasons.append("Не скрыт")
    if criteria.get("only_complete"):
        reasons.append("Complete-кандидат")

    return reasons
