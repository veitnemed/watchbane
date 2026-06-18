"""SQLite title search helpers for the local IMDb database."""

from __future__ import annotations

import math
import re
import sqlite3
import json
from difflib import SequenceMatcher
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "datasets" / "dataset_sql_light" / "imdb_light.sqlite3"
ALIASES_PATH = Path(__file__).resolve().with_name("sql_title_aliases.json")

COUNTRY_TO_REGION = {
    "россия": "RU",
    "сша": "US",
    "великобритания": "GB",
    "япония": "JP",
    "весь мир": "XWW",
}

REGION_TO_COUNTRY = {
    "RU": "Россия",
    "US": "США",
    "GB": "Великобритания",
    "JP": "Япония",
    "XWW": "Весь мир",
}

CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}

COMMON_TITLE_TYPOS = {
    "haappy": "happy",
    "индентификация": "идентификация",
    "химмера": "химера",
    "фишшер": "фишер",
}

_MANUAL_ALIASES_CACHE: dict[str, str] | None = None


def make_response(ok: bool, data=None, error: str = None, details: str = None) -> dict:
    return {
        "ok": ok,
        "data": data,
        "error": error,
        "details": details,
    }


def normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_for_match(value) -> str:
    text = normalize_text(value).casefold()
    text = re.sub(r"[^0-9a-z\u0400-\u04FF]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_manual_aliases() -> dict[str, str]:
    global _MANUAL_ALIASES_CACHE
    if _MANUAL_ALIASES_CACHE is not None:
        return _MANUAL_ALIASES_CACHE

    if ALIASES_PATH.exists() is False:
        _MANUAL_ALIASES_CACHE = {}
        return _MANUAL_ALIASES_CACHE

    with open(ALIASES_PATH, "r", encoding="utf-8") as file:
        raw = json.load(file)

    aliases = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            normalized_key = normalize_for_match(key)
            normalized_value = normalize_text(value)
            if normalized_key and normalized_value:
                aliases[normalized_key] = normalized_value

    _MANUAL_ALIASES_CACHE = aliases
    return aliases


def resolve_manual_alias(title: str) -> str | None:
    return load_manual_aliases().get(normalize_for_match(title))


def contains_cyrillic(text: str) -> bool:
    return bool(re.search(r"[\u0400-\u04FF]", str(text or "")))


def transliterate_to_latin(text: str) -> str:
    pieces = []
    for char in normalize_text(text).casefold():
        if char in CYRILLIC_TO_LATIN:
            pieces.append(CYRILLIC_TO_LATIN[char])
        elif char.isascii() and (char.isalnum() or char.isspace()):
            pieces.append(char)
        else:
            pieces.append(" ")
    return normalize_for_match("".join(pieces))


def collapse_repeated_letters(text: str) -> str:
    return re.sub(r"([0-9a-zа-я\u0400-\u04FF])\1+", r"\1", text, flags=re.IGNORECASE)


def apply_known_typos(text: str) -> str:
    words = normalize_for_match(text).split()
    fixed = [COMMON_TITLE_TYPOS.get(word, word) for word in words]
    return " ".join(fixed)


def build_query_variants(title: str) -> list[str]:
    variants = []
    normalized = normalize_for_match(title)
    typo_fixed = apply_known_typos(title)
    collapsed = collapse_repeated_letters(normalized)
    transliterated = transliterate_to_latin(title)
    typo_transliterated = transliterate_to_latin(typo_fixed)
    manual_alias = resolve_manual_alias(title)
    manual_alias_norm = normalize_for_match(manual_alias) if manual_alias else ""
    for candidate in (
        normalized,
        typo_fixed,
        collapsed,
        transliterated,
        typo_transliterated,
        manual_alias_norm,
    ):
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants


def build_exact_variants(title: str) -> list[str]:
    variants = []
    raw = normalize_text(title)
    typo_fixed = apply_known_typos(title)
    manual_alias = resolve_manual_alias(title)
    transliterated_values = [transliterate_to_latin(title), transliterate_to_latin(typo_fixed)]
    if manual_alias:
        transliterated_values.append(transliterate_to_latin(manual_alias))
    title_cased = " ".join(word[:1].upper() + word[1:] for word in typo_fixed.split())
    manual_title_cased = ""
    if manual_alias:
        manual_title_cased = " ".join(word[:1].upper() + word[1:] for word in manual_alias.split())
    for candidate in (
        raw,
        typo_fixed,
        typo_fixed[:1].upper() + typo_fixed[1:],
        title_cased,
        manual_alias,
        manual_title_cased,
    ):
        if candidate and candidate not in variants:
            variants.append(candidate)
    for transliterated in transliterated_values:
        for candidate in (transliterated, transliterated[:1].upper() + transliterated[1:]):
            if candidate and candidate not in variants:
                variants.append(candidate)
    return variants


def build_token_variants(title: str) -> list[str]:
    variants = []
    pieces = []
    manual_alias = resolve_manual_alias(title)
    for source in (
        normalize_text(title),
        apply_known_typos(title),
        collapse_repeated_letters(normalize_for_match(title)),
        manual_alias or "",
    ):
        pieces.extend(re.split(r"\s+", source))

    for token in pieces:
        token = normalize_text(token)
        token = token.strip(".,:;!?()[]{}\"'")
        if len(token) < 4:
            continue
        for candidate in (
            token,
            token.casefold(),
            token[:1].upper() + token[1:],
            transliterate_to_latin(token),
        ):
            if candidate and candidate not in variants:
                variants.append(candidate)
    return variants


def country_to_region(country: str) -> str | None:
    return COUNTRY_TO_REGION.get(normalize_for_match(country))


def connect_db(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _init_candidate(row: sqlite3.Row) -> dict:
    return {
        "tconst": row["tconst"],
        "titleType": row["titleType"],
        "primaryTitle": row["primaryTitle"],
        "originalTitle": row["originalTitle"],
        "startYear": row["startYear"],
        "endYear": row["endYear"],
        "runtimeMinutes": row["runtimeMinutes"],
        "genres": row["genres"],
        "averageRating": row["averageRating"],
        "numVotes": row["numVotes"],
        "matched_titles": [],
        "matched_regions": [],
        "exact_hits": 0,
        "like_hits": 0,
        "token_hits": 0,
    }


def _add_title_hit(candidate: dict, title: str) -> None:
    original_query = normalize_text(title)
    title = original_query
    if title and title not in candidate["matched_titles"]:
        candidate["matched_titles"].append(title)


def _add_region_hit(candidate: dict, region: str) -> None:
    region = normalize_text(region).upper()
    if region and region not in candidate["matched_regions"]:
        candidate["matched_regions"].append(region)


def fetch_candidates(cursor: sqlite3.Cursor, title: str, limit: int = 20) -> dict[str, dict]:
    candidates: dict[str, dict] = {}
    variants = build_query_variants(title)
    exact_variants = build_exact_variants(title)
    if not variants:
        return candidates

    title_like_sql = """
        SELECT
            t.tconst,
            t.titleType,
            t.primaryTitle,
            t.originalTitle,
            t.startYear,
            t.endYear,
            t.runtimeMinutes,
            t.genres,
            t.averageRating,
            t.numVotes
        FROM titles t
        WHERE t.primaryTitle LIKE ?
           OR t.originalTitle LIKE ?
        ORDER BY COALESCE(t.numVotes, 0) DESC, t.startYear DESC, t.tconst
        LIMIT ?
    """
    title_exact_sql = title_like_sql.replace("LIKE ?", "= ?")
    aka_like_sql = """
        SELECT
            t.tconst,
            t.titleType,
            t.primaryTitle,
            t.originalTitle,
            t.startYear,
            t.endYear,
            t.runtimeMinutes,
            t.genres,
            t.averageRating,
            t.numVotes,
            a.title AS aka_title,
            a.region
        FROM akas a
        JOIN titles t ON t.tconst = a.titleId
        WHERE a.title LIKE ?
        ORDER BY COALESCE(t.numVotes, 0) DESC, t.startYear DESC, t.tconst
        LIMIT ?
    """
    aka_exact_sql = aka_like_sql.replace("LIKE ?", "= ?")
    title_token_sql = title_like_sql
    aka_token_sql = aka_like_sql

    for variant in exact_variants + variants:
        exact_pattern = variant
        like_pattern = f"%{variant}%"

        for row in cursor.execute(title_exact_sql, (exact_pattern, exact_pattern, limit)).fetchall():
            tconst = row["tconst"]
            candidate = candidates.get(tconst)
            if candidate is None:
                candidate = _init_candidate(row)
                candidates[tconst] = candidate
            candidate["exact_hits"] += 1
            _add_title_hit(candidate, row["primaryTitle"])
            _add_title_hit(candidate, row["originalTitle"])

        for row in cursor.execute(aka_exact_sql, (exact_pattern, limit)).fetchall():
            tconst = row["tconst"]
            candidate = candidates.get(tconst)
            if candidate is None:
                candidate = _init_candidate(row)
                candidates[tconst] = candidate
            candidate["exact_hits"] += 1
            _add_title_hit(candidate, row["aka_title"])
            _add_region_hit(candidate, row["region"])

        for row in cursor.execute(title_like_sql, (like_pattern, like_pattern, limit)).fetchall():
            tconst = row["tconst"]
            candidate = candidates.get(tconst)
            if candidate is None:
                candidate = _init_candidate(row)
                candidates[tconst] = candidate
            candidate["like_hits"] += 1
            _add_title_hit(candidate, row["primaryTitle"])
            _add_title_hit(candidate, row["originalTitle"])

        for row in cursor.execute(aka_like_sql, (like_pattern, limit)).fetchall():
            tconst = row["tconst"]
            candidate = candidates.get(tconst)
            if candidate is None:
                candidate = _init_candidate(row)
                candidates[tconst] = candidate
            candidate["like_hits"] += 1
            _add_title_hit(candidate, row["aka_title"])
            _add_region_hit(candidate, row["region"])

    if len(candidates) > 0:
        return candidates

    for token in build_token_variants(title):
        pattern = f"%{token}%"
        for row in cursor.execute(title_token_sql, (pattern, pattern, limit)).fetchall():
            tconst = row["tconst"]
            candidate = candidates.get(tconst)
            if candidate is None:
                candidate = _init_candidate(row)
                candidates[tconst] = candidate
            candidate["token_hits"] += 1
            _add_title_hit(candidate, row["primaryTitle"])
            _add_title_hit(candidate, row["originalTitle"])

        for row in cursor.execute(aka_token_sql, (pattern, limit)).fetchall():
            tconst = row["tconst"]
            candidate = candidates.get(tconst)
            if candidate is None:
                candidate = _init_candidate(row)
                candidates[tconst] = candidate
            candidate["token_hits"] += 1
            _add_title_hit(candidate, row["aka_title"])
            _add_region_hit(candidate, row["region"])

    return candidates


def best_text_ratio(query: str, texts: list[str]) -> float:
    query_norm = normalize_for_match(query)
    if query_norm == "":
        return 0.0
    best = 0.0
    for text in texts:
        text_norm = normalize_for_match(text)
        if text_norm == "":
            continue
        ratio = SequenceMatcher(None, query_norm, text_norm).ratio()
        if query_norm in text_norm or text_norm in query_norm:
            ratio = max(ratio, 0.82)
        best = max(best, ratio)
    return best


def score_candidate(candidate: dict, query: str, country_region: str | None) -> float:
    query_norm = normalize_for_match(query)
    matched_texts = [
        normalize_for_match(candidate.get("primaryTitle")),
        normalize_for_match(candidate.get("originalTitle")),
        *[normalize_for_match(text) for text in candidate.get("matched_titles", [])],
    ]
    matched_texts = [text for text in matched_texts if text]

    raw_query_exact = query_norm in matched_texts

    if int(candidate.get("exact_hits") or 0) > 0 or any(text == query_norm for text in matched_texts):
        score = 0.0
    elif any(text.startswith(query_norm) for text in matched_texts):
        score = 1.0
    elif any(query_norm in text for text in matched_texts):
        score = 2.0
    else:
        score = 3.0 - best_text_ratio(query, matched_texts)

    score -= min(int(candidate.get("exact_hits") or 0) * 0.75, 1.5)
    score -= min(int(candidate.get("like_hits") or 0) * 0.05, 0.5)
    score -= min(int(candidate.get("token_hits") or 0) * 0.12, 0.8)

    regions = set(candidate.get("matched_regions", []))
    if country_region is not None:
        if country_region in regions:
            score -= 0.4
        elif "XWW" in regions:
            score -= 0.1
        else:
            score += 0.2

    votes = int(candidate.get("numVotes") or 0)
    score -= min(math.log10(votes + 1) / 50.0, 0.4)
    year = candidate.get("startYear")
    if isinstance(year, int):
        score -= min(max(year - 1900, 0) / 100000.0, 0.05)
        if contains_cyrillic(query) and raw_query_exact:
            score -= 3.0
            score += max(year - 2018, 0) / 10.0

    return score


def fetch_credits(cursor: sqlite3.Cursor, tconst: str) -> dict:
    credits = {
        "directors": [],
        "writers": [],
        "creators": [],
        "producers": [],
        "actors": [],
        "actresses": [],
        "self": [],
    }
    rows = cursor.execute(
        """
        SELECT category, primaryName, ordering, characters
        FROM credits
        WHERE tconst = ?
        ORDER BY ordering
        """,
        (tconst,),
    ).fetchall()

    for row in rows:
        category = normalize_text(row["category"]).lower()
        name = normalize_text(row["primaryName"])
        if name == "":
            continue
        if category in credits:
            if name not in credits[category]:
                credits[category].append(name)
        elif category in ("actor", "actress"):
            if name not in credits["actors"]:
                credits["actors"].append(name)
        elif category == "self":
            if name not in credits["self"]:
                credits["self"].append(name)

    if credits["actors"] == []:
        credits.pop("actors")
    if credits["actresses"] == []:
        credits.pop("actresses")
    if credits["self"] == []:
        credits.pop("self")
    return credits


def fetch_akas(cursor: sqlite3.Cursor, tconst: str) -> list[dict]:
    rows = cursor.execute(
        """
        SELECT title, region, language, types, isOriginalTitle
        FROM akas
        WHERE titleId = ?
        ORDER BY COALESCE(isOriginalTitle, 0) DESC, region, title
        """,
        (tconst,),
    ).fetchall()
    aliases = []
    for row in rows:
        region = normalize_text(row["region"]).upper()
        aliases.append({
            "title": normalize_text(row["title"]),
            "region": region,
            "country": REGION_TO_COUNTRY.get(region),
            "language": normalize_text(row["language"]),
            "types": normalize_text(row["types"]),
            "is_original": int(row["isOriginalTitle"] or 0),
        })
    return aliases


def build_title_payload(candidate: dict, query: str, country_region: str | None, cursor: sqlite3.Cursor) -> dict:
    akas = fetch_akas(cursor, candidate["tconst"])
    regions = []
    region_countries = []
    for item in akas:
        if item["region"] and item["region"] not in regions:
            regions.append(item["region"])
        if item["country"] and item["country"] not in region_countries:
            region_countries.append(item["country"])

    credits = fetch_credits(cursor, candidate["tconst"])
    score = score_candidate(candidate, query, country_region)
    actors = credits.get("actors") or credits.get("actresses") or []
    directors = credits.get("directors", [])
    writers = credits.get("writers", [])
    producers = credits.get("producers", [])
    creators = credits.get("creators", [])

    return {
        "tconst": candidate["tconst"],
        "title_type": candidate.get("titleType"),
        "title": candidate.get("primaryTitle"),
        "original_title": candidate.get("originalTitle"),
        "year": candidate.get("startYear"),
        "end_year": candidate.get("endYear"),
        "runtime_minutes": candidate.get("runtimeMinutes"),
        "genres": [genre.strip() for genre in str(candidate.get("genres") or "").split(",") if genre.strip()],
        "imdb_rating": candidate.get("averageRating"),
        "imdb_votes": candidate.get("numVotes"),
        "production_countries": [],
        "description": None,
        "regions": regions,
        "countries": region_countries,
        "title_region_countries": region_countries,
        "actors": actors,
        "directors": directors,
        "writers": writers,
        "producers": producers,
        "creators": creators,
        "source": {
            "search": "sql",
            "database": str(DEFAULT_DB_PATH),
        },
        "alternative_titles": akas,
        "credits": credits,
        "match": {
            "query": normalize_text(query),
            "country_region": country_region,
            "score": round(score, 3),
            "matched_source": "exact" if int(candidate.get("exact_hits") or 0) > 0 else "like",
            "matched_titles": candidate.get("matched_titles", []),
        },
        "url": f"https://www.imdb.com/title/{candidate['tconst']}/",
    }


def search_title_in_sql(
    title: str,
    country: str = "Россия",
    db_path: str | Path = DEFAULT_DB_PATH,
    limit: int = 20,
) -> dict:
    original_query = normalize_text(title)
    title = original_query
    if title == "":
        return make_response(False, error="empty_title", details="Название не задано.")

    db_path = Path(db_path)
    if db_path.exists() is False:
        return make_response(False, error="db_not_found", details=f"SQLite database not found: {db_path}")

    country_region = country_to_region(country)
    alias_applied = resolve_manual_alias(title)
    try:
        with connect_db(db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            candidates = fetch_candidates(cursor, title, limit=limit)
            if len(candidates) == 0:
                return make_response(False, error="not_found", details="Тайтл не найден в локальной SQLite-базе.")

            ranked = sorted(
                candidates.values(),
                key=lambda candidate: (
                    score_candidate(candidate, title, country_region),
                    -(int(candidate.get("numVotes") or 0)),
                    -(int(candidate.get("startYear") or 0)),
                    candidate.get("tconst"),
                ),
            )

            best = build_title_payload(ranked[0], title, country_region, cursor)
            best["source"]["database"] = str(db_path)
            best["match"]["original_query"] = original_query
            best["match"]["alias_applied"] = alias_applied
            alternatives = [
                {
                    "tconst": candidate["tconst"],
                    "title": candidate.get("primaryTitle"),
                    "original_title": candidate.get("originalTitle"),
                    "year": candidate.get("startYear"),
                    "title_type": candidate.get("titleType"),
                    "imdb_rating": candidate.get("averageRating"),
                    "imdb_votes": candidate.get("numVotes"),
                }
                for candidate in ranked[1:5]
            ]
            best["alternatives"] = alternatives
            return make_response(True, data=best)
    except sqlite3.Error as error:
        return make_response(False, error="sqlite_error", details=str(error))
