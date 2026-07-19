"""Capture Recommendations after a hide action with reserve promote (C3-09)."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _process_events(app, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=960)
    parser.add_argument("--interface-language", choices=("ru", "en"), default="ru")
    parser.add_argument("--data-language", choices=("ru", "en"), default="ru")
    args = parser.parse_args(argv)

    runtime = args.runtime_root.resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ["WATCHBANE_DATA_DIR"] = str(runtime)
    os.environ["WATCHBANE_INTERFACE_LANGUAGE"] = args.interface_language
    os.environ["WATCHBANE_DATA_LANGUAGE"] = args.data_language
    os.environ["WATCHBANE_UI_SCALE"] = str(args.scale)
    os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")

    from storage.sqlite.candidate_pool_repository import save_candidate_pool_dict

    pool: dict = {}
    for index in range(30):
        key = f"c3-09-{index}|2020"
        pool[key] = {
            "pool_entry_key": key,
            "title": f"Карточка {index + 1}",
            "year": 2010 + (index % 10),
            "media_type": "tv",
            "tmdb_id": 90_000 + index,
            "tmdb_score": 8.0 - index * 0.01,
            "tmdb_votes": 500 + index,
            "tmdb_popularity": 50.0 - index,
            "final_score": 90 - index,
            "overview": f"Описание {index + 1}",
            "poster_path": f"/c309-{index}.jpg",
            "genre_keys": ["drama"],
            "genres": ["Drama"],
            "country_codes": ["US"],
            "localized": {
                "ru": {
                    "title": f"Карточка {index + 1}",
                    "overview": f"Описание {index + 1}",
                }
            },
        }
    save_candidate_pool_dict(pool)

    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(args.scale)

    from PyQt6.QtWidgets import QApplication, QListView

    from desktop.shell.main_window import WatchedMoviesWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = WatchedMoviesWindow(initial_size=(args.width, args.height))
    window.show()
    window.raise_()
    window.activateWindow()
    window._tab_registry.focus("candidates")
    _process_events(app, 3.0)

    list_view = window._tabs_context.candidate_list_view
    deck = list_view._deck if isinstance(getattr(list_view, "_deck", None), dict) else None
    if not isinstance(deck, dict) or not deck.get("active"):
        # Force a local deck build if shell has not materialized yet.
        from candidates.recommendation_deck_service import RecommendationDeckService

        service = RecommendationDeckService()
        built = service.build_deck({}, datetime.now(timezone.utc))
        list_view._deck = built
        list_view._deck_service = service
        list_view._present_recommendation_deck(built)
        _process_events(app, 1.0)
        deck = built

    active_before = len(deck.get("active") or [])
    reserve_before = len(deck.get("reserve") or [])
    selected = (deck.get("active") or [None])[0]
    if not isinstance(selected, dict):
        print("error=no_active_candidate")
        window.close()
        return 1

    list_view._selected_candidate = selected
    list_view._apply_recommendation_action("hidden")
    _process_events(app, 1.5)

    updated = list_view._deck if isinstance(list_view._deck, dict) else {}
    active_after = len(updated.get("active") or [])
    reserve_after = len(updated.get("reserve") or [])
    promoted = (updated.get("last_action") or {}).get("promoted_identity")

    candidates = window.findChild(QListView, "candidateListWidget")
    if candidates is not None and candidates.model() is not None and candidates.model().rowCount() > 0:
        candidates.setCurrentIndex(candidates.model().index(0, 0))
        _process_events(app, 0.6)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    saved = window.grab().save(str(args.output))
    print(
        f"active_before={active_before} reserve_before={reserve_before} "
        f"active_after={active_after} reserve_after={reserve_after} "
        f"promoted={bool(promoted)} saved={saved} path={args.output}"
    )
    window.close()
    _process_events(app, 0.2)
    return 0 if saved and active_after == active_before and reserve_after == reserve_before - 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
