"""Интерактивная проверка точных повторов в candidate_pool.json."""

from __future__ import annotations

try:
    from .instrumenty_povtorov import (
        delete_entries_by_keys,
        find_exact_duplicate_groups,
        format_entry,
    )
except ImportError:
    from instrumenty_povtorov import (
        delete_entries_by_keys,
        find_exact_duplicate_groups,
        format_entry,
    )


def _duplicate_title(group: list) -> str:
    """Возвращает человекочитаемое название группы повторов."""
    candidate = group[0].candidate
    title = candidate.get("title") or candidate.get("alternative_title") or "Без названия"
    year = candidate.get("year") or "?"
    return f"{title} ({year})"


def _ask_delete_duplicates() -> str:
    """Спрашивает подтверждение удаления и спокойно обрабатывает конец ввода."""
    try:
        return input("Удалить дубликаты? yes/no >> ").strip().lower()
    except EOFError:
        return "stop"


def main() -> None:
    """Запускает простое меню удаления точных повторов."""
    groups = find_exact_duplicate_groups()
    print("Проверка точных повторов в candidate_pool.json")
    print("Точный повтор = одинаковое нормализованное название + год.\n")

    if len(groups) == 0:
        print("Точных повторов не найдено.")
        return

    print(f"Найдено повторов: {len(groups)}\n")
    total_removed = 0
    for group in groups:
        duplicate_count = len(group)
        keep_entry = group[0]
        keys_to_delete = {
            entry.key
            for entry in group[1:]
        }

        print(f"Повторов {duplicate_count}: {_duplicate_title(group)}")
        print(f"Оставить: {format_entry(keep_entry)}")
        print("Удалить:")
        for entry in group[1:]:
            print(f"  - {format_entry(entry)}")

        confirm = _ask_delete_duplicates()
        if confirm == "stop":
            print("\nВвод закончился, остановка.")
            break
        if confirm not in {"yes", "y"}:
            print("Пропущено.\n")
            continue

        removed = delete_entries_by_keys(keys_to_delete)
        total_removed += removed
        print(f"Удалено: {removed}\n")

    print(f"Готово. Всего удалено: {total_removed}")


if __name__ == "__main__":
    main()

