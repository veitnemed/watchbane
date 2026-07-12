"""Интерактивная проверка похожих названий в candidate_pool.json."""

from __future__ import annotations

try:
    from .instrumenty_povtorov import (
        delete_entries_by_keys,
        find_similar_title_pairs,
        format_entry,
    )
except ImportError:
    from instrumenty_povtorov import (
        delete_entries_by_keys,
        find_similar_title_pairs,
        format_entry,
    )


def _ask_pair_action() -> str:
    """Спрашивает, какую запись из похожей пары удалить."""
    try:
        return input("Удалить [Enter=пропустить, a=удалить A, b=удалить B] >> ").strip().lower()
    except EOFError:
        return "stop"


def _ask_confirm_delete(target_text: str) -> bool:
    """Спрашивает финальное подтверждение удаления одной записи."""
    try:
        answer = input(f"Удалить: {target_text}? yes >> ").strip().lower()
    except EOFError:
        return False
    return answer == "yes"


def main() -> None:
    """Запускает меню проверки похожих названий."""
    pairs = find_similar_title_pairs()
    print("Проверка похожих названий в candidate_pool.json")
    print("Похожие = один год, разные названия, similarity >= 0.80.\n")

    if len(pairs) == 0:
        print("Похожих названий не найдено.")
        return

    print(f"Найдено подозрительных пар: {len(pairs)}\n")
    total_removed = 0
    deleted_keys: set[str] = set()

    for pair_index, pair in enumerate(pairs, start=1):
        left = pair["left"]
        right = pair["right"]
        if left.key in deleted_keys or right.key in deleted_keys:
            continue

        print(f"Пара {pair_index}/{len(pairs)} | похожесть: {pair['ratio']:.2f}")
        print(f"  A. {format_entry(left)}")
        print(f"  B. {format_entry(right)}")
        answer = _ask_pair_action()

        if answer == "stop":
            print("\nВвод закончился, остановка.")
            break
        if answer == "":
            print("Пропущено.\n")
            continue
        if answer not in {"a", "b"}:
            print("Не понял выбор, пара пропущена.\n")
            continue

        target = left if answer == "a" else right
        if _ask_confirm_delete(format_entry(target)) is False:
            print("Удаление отменено.\n")
            continue

        removed = delete_entries_by_keys({target.key})
        if removed > 0:
            deleted_keys.add(target.key)
        total_removed += removed
        print(f"Удалено: {removed}\n")

    print(f"Готово. Всего удалено: {total_removed}")


if __name__ == "__main__":
    main()

