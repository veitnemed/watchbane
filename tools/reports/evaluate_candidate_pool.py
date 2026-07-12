"""Evaluate saved TMDb candidate_pool JSON and export quality reports."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

UNWANTED_GENRES = {
    "animation",
    "family",
    "short",
    "reality-tv",
    "talk-show",
    "game-show",
    "news",
    "sport",
    "adult",
}
SERIOUS_GENRES = {"drama", "crime", "mystery", "thriller"}
TOP_CSV_FIELDS = [
    "rank",
    "final_score",
    "country_score",
    "quality_score",
    "hidden_gem_score",
    "title",
    "original_title",
    "year",
    "tmdb_score",
    "tmdb_votes",
    "genres_tmdb",
    "original_language",
    "production_countries",
    "networks",
    "country_signals",
    "imdb_id",
    "tmdb_id",
    "overview",
]
SUSPICIOUS_CSV_FIELDS = [
    "rank",
    "reasons",
    "final_score",
    "country_score",
    "quality_score",
    "hidden_gem_score",
    "title",
    "original_title",
    "year",
    "tmdb_score",
    "tmdb_votes",
    "genres_tmdb",
    "original_language",
    "production_countries",
    "networks",
    "country_signals",
    "imdb_id",
    "tmdb_id",
    "overview",
]


def load_candidates(path: str | Path) -> tuple[list[dict], dict]:
    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)
    if isinstance(payload, dict):
        candidates = payload.get("candidates")
        if isinstance(candidates, list):
            return candidates, payload
    if isinstance(payload, list):
        return payload, {"candidates": payload}
    raise ValueError("Input JSON does not contain candidates list.")


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return []
        if "," in text:
            return [item.strip() for item in text.split(",") if item.strip()]
        return [text]
    return [value]


def safe_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value):
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalize_title(title) -> str:
    text = str(title or "").strip().casefold()
    text = text.replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return " ".join(text.split())


def normalize_genre_name(name) -> str:
    text = str(name or "").strip().casefold()
    replacements = {
        "драма": "drama",
        "криминал": "crime",
        "детектив": "mystery",
        "мистика": "mystery",
        "триллер": "thriller",
        "комедия": "comedy",
        "анимация": "animation",
        "семейный": "family",
        "новости": "news",
        "спорт": "sport",
    }
    return replacements.get(text, text)


def extract_output_prefix(input_path: str | Path) -> tuple[Path, Path]:
    path = Path(input_path)
    match = re.match(r"candidate_pool_([A-Z]{2})_([a-z_]+)\.json$", path.name)
    if match:
        country, mode = match.groups()
        prefix = f"eval_{country}_{mode}"
    else:
        prefix = "eval"
    return (
        path.with_name(f"{prefix}_top50.csv"),
        path.with_name(f"{prefix}_suspicious.csv"),
    )


def write_csv(path: str | Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def mean_of(candidates: list[dict], field: str):
    values = [safe_float(candidate.get(field)) for candidate in candidates]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return sum(values) / len(values)


def counter_from_field(candidates: list[dict], field: str) -> Counter:
    counter = Counter()
    for candidate in candidates:
        for item in as_list(candidate.get(field)):
            text = str(item or "").strip()
            if text:
                counter[text] += 1
    return counter


def get_title_year_key(candidate: dict) -> str:
    return f"{normalize_title(candidate.get('title') or candidate.get('original_title'))}|{candidate.get('year') or ''}"


def build_duplicate_sets(candidates: list[dict]) -> dict[str, set]:
    tmdb_counts = Counter(str(candidate.get("tmdb_id")) for candidate in candidates if candidate.get("tmdb_id") not in (None, ""))
    imdb_counts = Counter(str(candidate.get("imdb_id")) for candidate in candidates if candidate.get("imdb_id") not in (None, ""))
    title_year_counts = Counter(get_title_year_key(candidate) for candidate in candidates if normalize_title(candidate.get("title") or candidate.get("original_title")) != "")
    return {
        "tmdb": {key for key, count in tmdb_counts.items() if count > 1},
        "imdb": {key for key, count in imdb_counts.items() if count > 1},
        "title_year": {key for key, count in title_year_counts.items() if count > 1},
    }


def candidate_has_comedy(candidate: dict) -> bool:
    genres = {normalize_genre_name(item) for item in as_list(candidate.get("genres_tmdb"))}
    return "comedy" in genres


def candidate_has_serious_genre(candidate: dict) -> bool:
    genres = {normalize_genre_name(item) for item in as_list(candidate.get("genres_tmdb"))}
    return bool(genres & SERIOUS_GENRES)


def candidate_has_unwanted_genre(candidate: dict) -> bool:
    genres = {normalize_genre_name(item) for item in as_list(candidate.get("genres_tmdb"))}
    return bool(genres & UNWANTED_GENRES)


def find_suspicious(candidates: list[dict]) -> list[dict]:
    duplicate_sets = build_duplicate_sets(candidates)
    suspicious = []

    for rank, candidate in enumerate(sorted(candidates, key=lambda item: safe_float(item.get("final_score")) or 0, reverse=True), start=1):
        reasons = []
        country_score = safe_float(candidate.get("country_score")) or 0
        tmdb_votes = safe_int(candidate.get("tmdb_votes")) or 0
        final_score = safe_float(candidate.get("final_score")) or 0
        overview = str(candidate.get("overview") or "").strip()
        imdb_id = candidate.get("imdb_id")

        if country_score < 0.40:
            reasons.append("low_country_score")
        if tmdb_votes < 10:
            reasons.append("few_tmdb_votes")
        if imdb_id in (None, ""):
            reasons.append("missing_imdb_id")
        if overview == "":
            reasons.append("missing_overview")
        if candidate_has_unwanted_genre(candidate):
            reasons.append("unwanted_genre")
        if candidate_has_comedy(candidate) and not candidate_has_serious_genre(candidate):
            reasons.append("comedy_without_serious_genre")
        if str(candidate.get("tmdb_id")) in duplicate_sets["tmdb"]:
            reasons.append("duplicate_tmdb_id")
        if str(candidate.get("imdb_id")) in duplicate_sets["imdb"]:
            reasons.append("duplicate_imdb_id")
        if get_title_year_key(candidate) in duplicate_sets["title_year"]:
            reasons.append("duplicate_title_year")
        if final_score >= 0.65 and country_score < 0.70:
            reasons.append("high_score_low_country")

        if not reasons:
            continue

        suspicious.append(build_csv_row(candidate, rank=rank, reasons=reasons))
    return suspicious


def build_csv_row(candidate: dict, rank: int, reasons: list[str] | None = None) -> dict:
    return {
        "rank": rank,
        "reasons": ", ".join(reasons or []),
        "final_score": safe_float(candidate.get("final_score")) or 0,
        "country_score": safe_float(candidate.get("country_score")) or 0,
        "quality_score": safe_float(candidate.get("quality_score")) or 0,
        "hidden_gem_score": safe_float(candidate.get("hidden_gem_score")) or 0,
        "title": candidate.get("title") or "",
        "original_title": candidate.get("original_title") or "",
        "year": candidate.get("year") or "",
        "tmdb_score": candidate.get("tmdb_score") or candidate.get("tmdb_rating") or "",
        "tmdb_votes": candidate.get("tmdb_votes") or "",
        "genres_tmdb": ", ".join(str(item) for item in as_list(candidate.get("genres_tmdb"))),
        "original_language": candidate.get("original_language") or "",
        "production_countries": ", ".join(str(item) for item in as_list(candidate.get("tmdb_production_countries"))),
        "networks": ", ".join(str(item) for item in as_list(candidate.get("networks"))),
        "country_signals": ", ".join(str(item) for item in as_list(candidate.get("country_signals"))),
        "imdb_id": candidate.get("imdb_id") or "",
        "tmdb_id": candidate.get("tmdb_id") or "",
        "overview": candidate.get("overview") or "",
    }


def build_report(candidates: list[dict]) -> dict:
    sorted_by_final = sorted(candidates, key=lambda item: safe_float(item.get("final_score")) or 0, reverse=True)
    sorted_by_hidden = sorted(candidates, key=lambda item: safe_float(item.get("hidden_gem_score")) or 0, reverse=True)
    duplicate_sets = build_duplicate_sets(candidates)
    country_signal_counter = counter_from_field(candidates, "country_signals")
    tmdb_genres_counter = counter_from_field(candidates, "genres_tmdb")

    high_final_low_country = [
        candidate for candidate in sorted_by_final
        if (safe_float(candidate.get("final_score")) or 0) >= 0.65
        and (safe_float(candidate.get("country_score")) or 0) < 0.70
    ]
    high_rating_low_votes = [
        candidate for candidate in sorted_by_final
        if (
            (safe_float(candidate.get("tmdb_score")) or safe_float(candidate.get("tmdb_rating")) or 0) >= 7.5
            and (safe_int(candidate.get("tmdb_votes")) or 0) < 30
        )
    ]
    comedy_candidates = [candidate for candidate in sorted_by_final if candidate_has_comedy(candidate)]
    comedy_without_serious = [candidate for candidate in sorted_by_final if candidate_has_comedy(candidate) and not candidate_has_serious_genre(candidate)]
    unwanted_genre_candidates = [candidate for candidate in sorted_by_final if candidate_has_unwanted_genre(candidate)]

    return {
        "total": len(candidates),
        "with_tmdb_id": sum(1 for candidate in candidates if candidate.get("tmdb_id") not in (None, "")),
        "with_imdb_id": sum(1 for candidate in candidates if candidate.get("imdb_id") not in (None, "")),
        "without_imdb_id": sum(1 for candidate in candidates if candidate.get("imdb_id") in (None, "")),
        "without_overview": sum(1 for candidate in candidates if str(candidate.get("overview") or "").strip() == ""),
        "country_ge_070": sum(1 for candidate in candidates if (safe_float(candidate.get("country_score")) or 0) >= 0.70),
        "country_ge_040_lt_070": sum(1 for candidate in candidates if 0.40 <= (safe_float(candidate.get("country_score")) or 0) < 0.70),
        "country_lt_040": sum(1 for candidate in candidates if (safe_float(candidate.get("country_score")) or 0) < 0.40),
        "country_signal_counter": country_signal_counter,
        "high_final_low_country": high_final_low_country,
        "mean_tmdb_score": mean_of(candidates, "tmdb_score"),
        "mean_tmdb_votes": mean_of(candidates, "tmdb_votes"),
        "high_rating_low_votes": high_rating_low_votes,
        "tmdb_genres_counter": tmdb_genres_counter,
        "comedy_candidates": comedy_candidates,
        "comedy_without_serious": comedy_without_serious,
        "unwanted_genre_candidates": unwanted_genre_candidates,
        "duplicate_tmdb_ids": sorted(duplicate_sets["tmdb"]),
        "duplicate_imdb_ids": sorted(duplicate_sets["imdb"]),
        "duplicate_title_year": sorted(duplicate_sets["title_year"]),
        "top20_final": sorted_by_final[:20],
        "top20_hidden": sorted_by_hidden[:20],
        "top50_rows": [build_csv_row(candidate, rank=index) for index, candidate in enumerate(sorted_by_final[:50], start=1)],
    }


def print_candidate_line(rank: int, candidate: dict, score_field: str) -> None:
    print(
        f"{rank:>2}. {candidate.get('title') or 'Без названия'} | "
        f"{score_field}={safe_float(candidate.get(score_field)) or 0:.3f} | "
        f"country={safe_float(candidate.get('country_score')) or 0:.2f} | "
        f"TMDb={candidate.get('tmdb_score') or candidate.get('tmdb_rating') or '-'}/{candidate.get('tmdb_votes') or 0}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate saved TMDb candidate_pool JSON.")
    parser.add_argument("--input", required=True, help="Path to candidate_pool JSON file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    candidates, payload = load_candidates(input_path)
    report = build_report(candidates)
    suspicious_rows = find_suspicious(candidates)
    top_csv_path, suspicious_csv_path = extract_output_prefix(input_path)

    write_csv(top_csv_path, report["top50_rows"], TOP_CSV_FIELDS)
    write_csv(suspicious_csv_path, suspicious_rows, SUSPICIOUS_CSV_FIELDS)

    print("Candidate pool quality report")
    print("=" * 60)
    print(f"Input: {input_path}")
    print(f"Country: {payload.get('country') or '-'}")
    print(f"Mode: {payload.get('mode') or '-'}")
    print("")
    print("Общая статистика")
    print("-" * 60)
    print(f"Всего кандидатов: {report['total']}")
    print(f"С tmdb_id: {report['with_tmdb_id']}")
    print(f"С imdb_id: {report['with_imdb_id']}")
    print(f"Без imdb_id: {report['without_imdb_id']}")
    print(f"Без overview: {report['without_overview']}")
    print("")
    print("Страна")
    print("-" * 60)
    print(f"country_score >= 0.70: {report['country_ge_070']}")
    print(f"0.40 <= country_score < 0.70: {report['country_ge_040_lt_070']}")
    print(f"country_score < 0.40: {report['country_lt_040']}")
    print(f"Top country_signals: {report['country_signal_counter'].most_common(10)}")
    print(f"High final, low country: {len(report['high_final_low_country'])}")
    print("")
    print("Рейтинги и голоса")
    print("-" * 60)
    print(f"Средний tmdb_score: {safe_float(report['mean_tmdb_score']) or 0:.3f}")
    print(f"Среднее tmdb_votes: {safe_float(report['mean_tmdb_votes']) or 0:.1f}")
    print(f"Высокий рейтинг при малом числе голосов: {len(report['high_rating_low_votes'])}")
    print("")
    print("Жанры")
    print("-" * 60)
    print(f"Top genres_tmdb: {report['tmdb_genres_counter'].most_common(10)}")
    print(f"Кандидаты с Comedy: {len(report['comedy_candidates'])}")
    print(f"Comedy без serious genres: {len(report['comedy_without_serious'])}")
    print(f"Кандидаты с нежелательными жанрами: {len(report['unwanted_genre_candidates'])}")
    print("")
    print("Дубли")
    print("-" * 60)
    print(f"Дубли по tmdb_id: {len(report['duplicate_tmdb_ids'])}")
    print(f"Дубли по imdb_id: {len(report['duplicate_imdb_ids'])}")
    print(f"Дубли по title+year: {len(report['duplicate_title_year'])}")
    print("")
    print("Top-20 by final_score")
    print("-" * 60)
    for index, candidate in enumerate(report["top20_final"], start=1):
        print_candidate_line(index, candidate, "final_score")
    print("")
    print("Top-20 by hidden_gem_score")
    print("-" * 60)
    for index, candidate in enumerate(report["top20_hidden"], start=1):
        print_candidate_line(index, candidate, "hidden_gem_score")
    print("")
    print("First 20 suspicious")
    print("-" * 60)
    for row in suspicious_rows[:20]:
        print(
            f"{row['rank']:>2}. {row['title'] or 'Без названия'} | "
            f"reasons={row['reasons']} | final={safe_float(row['final_score']) or 0:.3f}"
        )
    print("")
    print(f"Saved CSV top50: {top_csv_path}")
    print(f"Saved CSV suspicious: {suspicious_csv_path}")


if __name__ == "__main__":
    main()
