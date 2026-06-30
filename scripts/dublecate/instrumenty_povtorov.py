"""Общие инструменты для скриптов проверки повторов в candidate_pool.json."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from candidates import candidate_pool


@dataclass(frozen=True)
class PoolEntry:
    """Одна запись из raw candidate_pool.json вместе с её исходным ключом."""

    key: str
    candidate: dict


def load_pool_entries() -> list[PoolEntry]:
    """Загружает записи pool и нормализует поля кандидата без сохранения файла."""
    raw_pool = candidate_pool.load_candidate_pool()
    entries = []
    for key, candidate in raw_pool.items():
        if isinstance(candidate, dict) is False:
            continue
        entries.append(PoolEntry(key=key, candidate=candidate_pool.normalize_candidate_record(candidate)))
    return entries


def entry_title(entry: PoolEntry) -> str:
    """Возвращает основное название кандидата."""
    return candidate_pool.candidate_title(entry.candidate)


def title_identity(entry: PoolEntry) -> str:
    """Возвращает идентификатор title+year для поиска точных повторов."""
    return candidate_pool.candidate_key(entry.candidate)


def entry_sort_score(entry: PoolEntry) -> tuple:
    """Возвращает score-ключ, по которому выбирается лучший кандидат из повторов."""
    return candidate_pool.candidate_sort_score(entry.candidate)


def format_entry(entry: PoolEntry) -> str:
    """Форматирует кандидата в одну строку для консольного меню."""
    candidate = entry.candidate
    title = entry_title(entry) or "Без названия"
    year = candidate.get("year") or "?"
    criteria = candidate.get("criteria_name") or "legacy"
    kp_score = candidate.get("kp_score") or 0
    kp_votes = candidate.get("kp_votes") or 0
    imdb_score = candidate.get("imdb_score") or 0
    imdb_votes = candidate.get("imdb_votes") or 0
    return (
        f"{title} ({year}) | критерий: {criteria} | "
        f"KP {kp_score} / {kp_votes} | IMDb {imdb_score} / {imdb_votes}"
    )


def find_exact_duplicate_groups(entries: list[PoolEntry] | None = None) -> list[list[PoolEntry]]:
    """Ищет точные повторы по нормализованному названию и году во всём общем pool."""
    if entries is None:
        entries = load_pool_entries()

    groups_by_identity: dict[str, list[PoolEntry]] = {}
    for entry in entries:
        identity = title_identity(entry)
        if identity == "|":
            continue
        groups_by_identity.setdefault(identity, []).append(entry)

    groups = [
        sorted(group, key=entry_sort_score, reverse=True)
        for group in groups_by_identity.values()
        if len(group) > 1
    ]
    groups.sort(key=lambda group: (entry_title(group[0]), str(group[0].candidate.get("year") or "")))
    return groups


def find_cross_year_title_groups(entries: list[PoolEntry] | None = None) -> list[dict]:
    """Ищет группы с одним normalized title, но разными canonical year."""
    if entries is None:
        return candidate_pool.find_cross_year_title_groups()

    candidates = [entry.candidate for entry in entries]
    return candidate_pool.find_cross_year_title_groups(candidates)


def find_title_duplicate_groups(entries: list[PoolEntry] | None = None) -> list[dict]:
    """Ищет группы с одним normalized title (2+ записей)."""
    if entries is None:
        return candidate_pool.find_title_duplicate_groups()

    candidates = [entry.candidate for entry in entries]
    return candidate_pool.find_title_duplicate_groups(candidates)


def find_similar_title_pairs(
    entries: list[PoolEntry] | None = None,
    *,
    min_ratio: float = 0.80,
) -> list[dict]:
    """Ищет пары одного года с похожими, но не полностью одинаковыми названиями."""
    if entries is None:
        entries = load_pool_entries()

    pairs = []
    for left_index in range(len(entries)):
        left = entries[left_index]
        left_title = entry_title(left)
        left_year = left.candidate.get("year") or ""
        if left_title == "":
            continue

        for right_index in range(left_index + 1, len(entries)):
            right = entries[right_index]
            right_title = entry_title(right)
            right_year = right.candidate.get("year") or ""
            if right_title == "":
                continue
            if left_year != right_year:
                continue

            left_normalized = candidate_pool.normalized_title_key(left_title)
            right_normalized = candidate_pool.normalized_title_key(right_title)
            if left_normalized == right_normalized:
                continue

            ratio = SequenceMatcher(
                None,
                candidate_pool.compact_title_key(left_title),
                candidate_pool.compact_title_key(right_title),
            ).ratio()
            if ratio < min_ratio:
                continue

            pairs.append({
                "left": left,
                "right": right,
                "ratio": ratio,
            })

    pairs.sort(key=lambda item: item["ratio"], reverse=True)
    return pairs


def delete_entries_by_keys(keys: set[str]) -> int:
    """Удаляет выбранные raw-записи и сохраняет pool через обычный write-path проекта."""
    if len(keys) == 0:
        return 0

    raw_pool = candidate_pool.load_candidate_pool()
    filtered_pool = {}
    removed = 0
    for key, candidate in raw_pool.items():
        if key in keys:
            removed += 1
            continue
        filtered_pool[key] = candidate

    if removed > 0:
        candidate_pool.save_candidate_pool(filtered_pool)
    return removed

