"""Общие инструменты для скриптов проверки повторов в candidate_pool.json."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from candidates.models.keys import normalize_key_part
from candidates.models.schema import normalize_candidate_record, resolve_canonical_year
from candidates.pool.dedupe import (
    candidate_key,
    candidate_title,
    compact_title_key,
    normalized_title_key,
)
from candidates.pool.diagnostics import find_cross_year_title_groups, find_title_duplicate_groups
from candidates.repositories.pool_repository import load_candidate_pool, save_candidate_pool
from candidates.scoring.sort_keys import candidate_sort_score


@dataclass(frozen=True)
class PoolEntry:
    """Одна запись из raw candidate_pool.json вместе с её исходным ключом."""

    key: str
    candidate: dict


def load_pool_entries() -> list[PoolEntry]:
    """Загружает записи pool и нормализует поля кандидата без сохранения файла."""
    raw_pool = load_candidate_pool()
    entries = []
    for key, candidate in raw_pool.items():
        if isinstance(candidate, dict) is False:
            continue
        entries.append(PoolEntry(key=key, candidate=normalize_candidate_record(candidate)))
    return entries


def entry_title(entry: PoolEntry) -> str:
    return candidate_title(entry.candidate)


def entry_key(entry: PoolEntry) -> str:
    return candidate_key(entry.candidate)


def entry_score(entry: PoolEntry) -> float:
    return candidate_sort_score(entry.candidate)


def find_cross_year_groups(entries: list[PoolEntry] | None = None) -> list[dict]:
    if entries is None:
        return find_cross_year_title_groups()
    candidates = [entry.candidate for entry in entries]
    return find_cross_year_title_groups(candidates)


def find_title_groups(entries: list[PoolEntry] | None = None) -> list[dict]:
    if entries is None:
        return find_title_duplicate_groups()
    candidates = [entry.candidate for entry in entries]
    return find_title_duplicate_groups(candidates)


def titles_are_similar(left_title: str, right_title: str, threshold: float = 0.88) -> bool:
    left_normalized = normalized_title_key(left_title)
    right_normalized = normalized_title_key(right_title)
    if left_normalized == right_normalized:
        return True
    if left_normalized == "" or right_normalized == "":
        return False
    if compact_title_key(left_title) == compact_title_key(right_title):
        return True
    ratio = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return ratio >= threshold


def purge_keys(keys_to_remove: set[str]) -> int:
    raw_pool = load_candidate_pool()
    filtered_pool = {
        key: candidate
        for key, candidate in raw_pool.items()
        if key not in keys_to_remove
    }
    removed = len(raw_pool) - len(filtered_pool)
    if removed > 0:
        save_candidate_pool(filtered_pool)
    return removed


def delete_entries_by_keys(keys_to_remove: set[str]) -> int:
    """Удаляет записи pool по raw JSON-ключам."""
    return purge_keys(keys_to_remove)


def format_entry(entry: PoolEntry) -> str:
    """Краткое описание записи для интерактивных скриптов."""
    candidate = entry.candidate
    title = candidate_title(candidate) or "Без названия"
    year = resolve_canonical_year(candidate)
    year_text = str(year) if year is not None else "?"
    parts = [f"{title} ({year_text})", f"key={entry.key}"]
    kp_score = candidate.get("kp_score")
    if kp_score not in (None, ""):
        parts.append(f"kp={kp_score}")
    return " | ".join(parts)


def _exact_duplicate_group_key(entry: PoolEntry) -> tuple[str, int | None]:
    title_key = normalize_key_part(candidate_title(entry.candidate))
    year = resolve_canonical_year(entry.candidate)
    return title_key, year if isinstance(year, int) else None


def find_exact_duplicate_groups(
    entries: list[PoolEntry] | None = None,
) -> list[list[PoolEntry]]:
    """Группы с одинаковым normalized title и canonical year; лучший кандидат первым."""
    if entries is None:
        entries = load_pool_entries()

    groups_by_key: dict[tuple[str, int | None], list[PoolEntry]] = {}
    for entry in entries:
        title_key, year = _exact_duplicate_group_key(entry)
        if title_key == "" or year is None:
            continue
        groups_by_key.setdefault((title_key, year), []).append(entry)

    groups: list[list[PoolEntry]] = []
    for group in groups_by_key.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda item: candidate_sort_score(item.candidate), reverse=True)
        groups.append(group)

    groups.sort(
        key=lambda group: (
            candidate_title(group[0].candidate).casefold(),
            resolve_canonical_year(group[0].candidate) or 0,
        )
    )
    return groups


def find_similar_title_pairs(
    entries: list[PoolEntry] | None = None,
    *,
    threshold: float = 0.80,
) -> list[dict]:
    """Пары с одним годом, разными normalized title и similarity >= threshold."""
    if entries is None:
        entries = load_pool_entries()

    pairs: list[dict] = []
    for left_index in range(len(entries)):
        left = entries[left_index]
        left_title = candidate_title(left.candidate)
        left_year = resolve_canonical_year(left.candidate)
        if left_title == "" or left_year is None:
            continue

        for right_index in range(left_index + 1, len(entries)):
            right = entries[right_index]
            right_title = candidate_title(right.candidate)
            right_year = resolve_canonical_year(right.candidate)
            if right_title == "" or right_year is None:
                continue
            if left_year != right_year:
                continue

            left_normalized = normalized_title_key(left_title)
            right_normalized = normalized_title_key(right_title)
            if left_normalized == right_normalized:
                continue

            ratio = SequenceMatcher(
                None,
                compact_title_key(left_title),
                compact_title_key(right_title),
            ).ratio()
            if ratio < threshold:
                continue

            pairs.append({"left": left, "right": right, "ratio": ratio})

    pairs.sort(key=lambda item: item["ratio"], reverse=True)
    return pairs
