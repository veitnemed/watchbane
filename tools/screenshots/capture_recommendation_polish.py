"""Capture repeatable native Recommendations detail states for visual polish."""

from __future__ import annotations

import argparse
import os
import sys
import time
from copy import deepcopy
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _process_events(app, seconds: float = 0.5) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _save_window(window, path: Path, app) -> bool:
    window.repaint()
    window.centralWidget().repaint()
    _process_events(app, 0.2)
    return window.grab().save(str(path))


def _candidate(index: int) -> dict:
    return {
        "pool_entry_key": f"polish-{index}|2024|movie",
        "title": f"Рекомендация {index + 1:02d}",
        "year": 2024 - index,
        "media_type": "movie",
        "is_searchable": True,
        "is_complete": True,
        "tmdb_score": 8.2 - index * 0.1,
        "tmdb_votes": 12_000 - index * 700,
        "tmdb_popularity": 80 - index,
        "final_score": 78 - index * 3,
        "overview": " ".join(
            [
                "Развёрнутое описание проверяет перенос текста, вертикальную плотность и прокрутку карточки.",
            ]
            * 18
        ),
        "poster_path": "",
        "genre_keys": ["drama", "thriller"],
        "genres": ["Драма", "Триллер"],
        "country_codes": ["US"],
        "localized": {"ru": {"title": f"Рекомендация {index + 1:02d}"}},
    }


class _Service:
    SEARCH_SORT_MODES = ("final_score",)

    def __init__(self) -> None:
        self.candidates = [_candidate(index) for index in range(12)]

    def get_search_overview_view(self) -> dict:
        return {
            "is_empty": False,
            "stats": {"unique_total": len(self.candidates)},
            "candidates": deepcopy(self.candidates),
        }

    def search_candidate_pool(self, source: list[dict], _filters: dict) -> dict:
        return {"candidates": list(source), "filtered_count": len(source)}

    def sort_search_candidates(self, source: list[dict], _sort_mode: str) -> dict:
        return {"candidates": list(source), "sort_mode": "final_score", "hidden_duplicates": 0}

    def get_search_filter_defaults_view(self) -> dict:
        from desktop.candidates.session import DEFAULT_BROWSE_FILTERS

        return {"defaults": dict(DEFAULT_BROWSE_FILTERS)}

    def get_search_filter_chip_options_view(self) -> dict:
        return {"genres": [], "countries": []}


class _DeckService:
    def __init__(self, service: _Service) -> None:
        self._service = service
        self.action_calls: list[tuple[str, int | None]] = []
        self._deck: dict = {}

    def refresh_deck(self, _preferences: dict, _now, *, force_new: bool = False) -> dict:
        self._deck = {
            "deck_id": "visual-polish",
            "active": deepcopy(self._service.candidates[:10]),
            "reserve": deepcopy(self._service.candidates[10:]),
            "active_limit": 10,
            "reserve_size": 70,
            "underfilled_reason": None,
        }
        return deepcopy(self._deck)

    def apply_action_and_refill(
        self,
        _deck_id: str,
        candidate: dict,
        action: str,
        *,
        user_score: int | None = None,
        refill_active: bool = True,
    ) -> dict:
        from desktop.candidates.presenters import candidate_detail_identity

        self.action_calls.append((action, user_score))
        identity = candidate_detail_identity(candidate)
        self._deck["active"] = [
            item for item in self._deck["active"] if candidate_detail_identity(item) != identity
        ]
        if refill_active and self._deck["reserve"]:
            self._deck["active"].append(self._deck["reserve"].pop(0))
        self._deck["last_action"] = {"action": action, "transition": {"ok": True}}
        return deepcopy(self._deck)


def _build_view(app, *, width: int, height: int):
    from PyQt6.QtCore import QModelIndex
    from PyQt6.QtWidgets import QMainWindow, QListView

    from desktop.candidates.list_view import CandidateListView
    from desktop.candidates.session import CandidateSearchSession
    from desktop.theme import build_app_style

    service = _Service()
    deck_service = _DeckService(service)
    view = CandidateListView(
        CandidateSearchSession(service=service),
        service=service,
        deck_service=deck_service,
    )
    window = QMainWindow()
    window.setWindowTitle("Watchbane — Recommendations visual polish")
    window.setCentralWidget(view.widget)
    window.setStyleSheet(build_app_style())
    window.resize(width, height)
    window.show()
    window.raise_()
    window.activateWindow()
    view.on_tab_activated()
    for _ in range(40):
        _process_events(app, 0.05)
        if view._deck and view._candidates:
            break
    results = view.widget.findChild(QListView, "candidateListWidget")
    if results is None or results.model() is None or results.model().rowCount() < 2:
        raise RuntimeError("Recommendations deck did not materialize")
    first = results.model().index(0, 0)
    results.setCurrentIndex(first)
    view._on_result_selected(first, QModelIndex())
    _process_events(app)
    return window, view, deck_service, results


def _assert_actions(app, *, width: int, height: int) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QPushButton

    checks = (
        ("recommendationWatchlistButton", "watchlist", None),
        ("recommendationHiddenButton", "hidden", None),
    )
    for object_name, action, expected_score in checks:
        window, view, deck_service, _results = _build_view(app, width=width, height=height)
        button = view.widget.findChild(QPushButton, object_name)
        if button is None or not button.isVisible() or not button.isEnabled():
            raise RuntimeError(f"Unavailable action control: {object_name}")
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        _process_events(app)
        if deck_service.action_calls != [(action, expected_score)]:
            raise RuntimeError(f"Unexpected action result: {deck_service.action_calls}")
        window.close()
    for score_index, expected_score in enumerate((1, 2, 3)):
        window, view, deck_service, _results = _build_view(app, width=width, height=height)
        watched = view.widget.findChild(QPushButton, "recommendationWatchedButton")
        if watched is None:
            raise RuntimeError("Unavailable watched control")
        QTest.mouseClick(watched, Qt.MouseButton.LeftButton)
        _process_events(app)
        QTest.mouseClick(
            view._candidate_rating_selector.buttons()[score_index],
            Qt.MouseButton.LeftButton,
        )
        _process_events(app)
        if deck_service.action_calls != [("watched", expected_score)]:
            raise RuntimeError(f"Unexpected rating result: {deck_service.action_calls}")
        window.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=960)
    args = parser.parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")

    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(args.scale)
    from desktop.theme.ui_modules import ensure_scaled_ui_modules

    ensure_scaled_ui_modules()
    from PyQt6.QtGui import QFont, QFontDatabase
    from PyQt6.QtWidgets import QApplication, QAbstractScrollArea, QPushButton

    from desktop.theme import FONT_APP, FONT_FAMILY, font_px

    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, font_px(FONT_APP)))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    window, view, _deck_service, results = _build_view(app, width=args.width, height=args.height)
    default_path = args.output_dir / f"{args.prefix}_default.png"
    watched_path = args.output_dir / f"{args.prefix}_watched.png"
    scrolled_path = args.output_dir / f"{args.prefix}_scrolled.png"
    if not _save_window(window, default_path, app):
        raise RuntimeError("Could not save default screenshot")
    watched = view.widget.findChild(QPushButton, "recommendationWatchedButton")
    if watched is None:
        raise RuntimeError("Watched action was not created")
    watched.click()
    _process_events(app)
    if not view._candidate_rating_selector.isVisible():
        raise RuntimeError("Watched action did not reveal the rating selector")
    if not _save_window(window, watched_path, app):
        raise RuntimeError("Could not save watched screenshot")
    view._rating_back_button.click()
    second = results.model().index(1, 0)
    results.setCurrentIndex(second)
    _process_events(app)
    detail_scroll = view.widget.findChild(QAbstractScrollArea, "candidateSearchDetailScroll")
    if detail_scroll is None:
        raise RuntimeError("Detail scroll area was not created")
    detail_scroll.verticalScrollBar().setValue(detail_scroll.verticalScrollBar().maximum())
    _process_events(app)
    if not _save_window(window, scrolled_path, app):
        raise RuntimeError("Could not save scrolled screenshot")
    _assert_actions(app, width=args.width, height=args.height)
    families = set(QFontDatabase.families())
    horizontal_scroll = [
        (area.objectName(), area.horizontalScrollBar().maximum())
        for area in window.findChildren(QAbstractScrollArea)
        if area.isVisible() and area.horizontalScrollBar().maximum() > 0
    ]
    print(f"platform={app.platformName()}")
    print(f"font_probe={{'family_count': {len(families)}, 'has_segoe_ui': {'Segoe UI' in families}}}")
    print(
        f"scale={args.scale} window={window.width()}x{window.height()} "
        f"horizontal_scroll={horizontal_scroll} interactions=watchlist,hidden,watched:1,2,3"
    )
    print(f"saved={default_path},{watched_path},{scrolled_path}")
    window.close()
    _process_events(app, 0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
