"""Read-only helpers for the desktop watched-movies view."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from desktop.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_SOFT,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_CARD_ALT,
    COLOR_IMDB_ACCENT,
    COLOR_KP_ACCENT,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY,
    FONT_RATING_LABEL_POINT,
    FONT_RATING_VALUE_POINT,
    TRANSPARENT_STYLE,
    build_detail_card_style,
    build_poster_image_style,
    build_poster_placeholder_style,
    OVERVIEW_DIVIDER_TEXT_SPACING,
    OVERVIEW_SECTION_TOP_SPACING,
    OVERVIEW_TITLE_DIVIDER_SPACING,
)
from storage import data as storage_data
from web.export import build_export_lookup_cache, build_watched_movie_card

_poster_cache = None
_lookup_cache = None


def _get_poster_cache() -> dict:
    global _poster_cache
    if _poster_cache is None:
        try:
            from posters.cache import load_poster_cache

            _poster_cache = load_poster_cache()
        except Exception:
            _poster_cache = {}
    return _poster_cache


def _get_lookup_cache() -> dict:
    global _lookup_cache
    if _lookup_cache is None:
        _lookup_cache = build_export_lookup_cache()
    return _lookup_cache

WatchedEntry = tuple[str, dict, dict]

SORT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("user_score", "Моя оценка"),
    ("year", "Год"),
    ("imdb_score", "IMDb"),
    ("kp_score", "КП"),
    ("title", "Название"),
)


def load_watched_entries() -> list[WatchedEntry]:
    """Load dataset and return (dataset_key, movie, card) tuples."""
    data = storage_data.load_dataset()
    poster_cache = _get_poster_cache()
    lookup_cache = _get_lookup_cache()
    return [
        (key, movie, build_watched_movie_card(movie, poster_cache=poster_cache, lookup_cache=lookup_cache))
        for key, movie in data.items()
    ]


def prepare_card_for_display(movie: dict) -> dict:
    """Build a card dict for GUI display without mutating the source movie."""
    original = deepcopy(movie)
    card = build_watched_movie_card(
        movie,
        poster_cache=_get_poster_cache(),
        lookup_cache=_get_lookup_cache(),
    )
    if movie != original:
        raise RuntimeError("build_watched_movie_card mutated the source movie")
    return card


def filter_by_title(entries: list[WatchedEntry], query: str) -> list[WatchedEntry]:
    """Return entries whose title matches the search query (case-insensitive)."""
    normalized = query.strip().lower()
    if normalized == "":
        return list(entries)

    result: list[WatchedEntry] = []
    for key, movie, card in entries:
        title = (card.get("title") or key or "").lower()
        if normalized in title or normalized in key.lower():
            result.append((key, movie, card))
    return result


def _coerce_filter_score(value) -> float | None:
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < USER_SCORE_MIN or score > USER_SCORE_MAX:
        return None
    return score


def filter_entries_by_user_score(
    entries: list[WatchedEntry],
    min_score: float | None = None,
    max_score: float | None = None,
) -> list[WatchedEntry]:
    """Return entries whose user_score is inside the inclusive range."""
    lower = USER_SCORE_MIN if min_score is None else float(min_score)
    upper = USER_SCORE_MAX if max_score is None else float(max_score)
    if lower > upper:
        lower, upper = upper, lower
    if lower <= USER_SCORE_MIN and upper >= USER_SCORE_MAX:
        return list(entries)

    result: list[WatchedEntry] = []
    for entry in entries:
        _key, _movie, card = entry
        score = _coerce_filter_score(card.get("user_score"))
        if score is None:
            continue
        if lower <= score <= upper:
            result.append(entry)
    return result


def _coerce_filter_year(value) -> int | None:
    if value is None:
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year


def _entry_year(entry: WatchedEntry) -> int | None:
    _key, movie, card = entry
    main_info = movie.get("main_info", {}) if isinstance(movie, dict) else {}
    if isinstance(main_info, dict):
        year = _coerce_filter_year(main_info.get("year"))
        if year is not None:
            return year
    return _coerce_filter_year(card.get("year"))


def filter_entries_by_year(
    entries: list[WatchedEntry],
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[WatchedEntry]:
    """Return entries whose main year is inside the inclusive range."""
    lower = YEAR_FILTER_MIN if year_from is None else int(year_from)
    upper = YEAR_FILTER_MAX if year_to is None else int(year_to)
    if lower > upper:
        lower, upper = upper, lower
    if lower <= YEAR_FILTER_MIN and upper >= YEAR_FILTER_MAX:
        return list(entries)

    result: list[WatchedEntry] = []
    for entry in entries:
        year = _entry_year(entry)
        if year is None:
            continue
        if lower <= year <= upper:
            result.append(entry)
    return result


GENRE_FILTER_ALL = "Все жанры"


def _entry_genres(entry: WatchedEntry) -> list[str]:
    _key, _movie, card = entry
    genres = card.get("genres") or []
    if isinstance(genres, str):
        genres = [genres]
    result: list[str] = []
    for genre in genres:
        text = str(genre).strip()
        if text:
            result.append(text)
    return result


def get_available_genres(entries: list[WatchedEntry]) -> list[str]:
    """Return sorted genre labels present in watched entries."""
    genres: set[str] = set()
    for entry in entries:
        genres.update(_entry_genres(entry))
    return sorted(genres, key=str.casefold)


def filter_entries_by_genre(entries: list[WatchedEntry], genre: str | None = None) -> list[WatchedEntry]:
    """Return entries containing the selected watched-card genre."""
    if genre is None:
        return list(entries)
    selected = str(genre).strip()
    if selected == "" or selected == GENRE_FILTER_ALL:
        return list(entries)

    result: list[WatchedEntry] = []
    for entry in entries:
        if selected in _entry_genres(entry):
            result.append(entry)
    return result


def sort_entries(entries: list[WatchedEntry], sort_key: str) -> list[WatchedEntry]:
    """Return a sorted copy of entries without mutating source data."""
    items = list(entries)

    if sort_key == "title":
        return sorted(
            items,
            key=lambda entry: (entry[2].get("title") or entry[0] or "").lower(),
        )

    def numeric_sort_key(entry: WatchedEntry) -> tuple[int, float | int]:
        value = entry[2].get(sort_key)
        if value is None:
            return (1, 0)
        return (0, value)

    return sorted(items, key=numeric_sort_key, reverse=True)


def apply_view(
    entries: list[WatchedEntry],
    query: str,
    sort_key: str,
    min_score: float | None = None,
    max_score: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    genre: str | None = None,
) -> list[WatchedEntry]:
    """Filter and sort entries for display."""
    filtered = filter_by_title(entries, query)
    filtered = filter_entries_by_user_score(filtered, min_score, max_score)
    filtered = filter_entries_by_year(filtered, year_from, year_to)
    filtered = filter_entries_by_genre(filtered, genre)
    return sort_entries(filtered, sort_key)


def _round_one_decimal(value) -> str:
    """Round to one decimal place (half up), e.g. 8.25 -> 8.3."""
    rounded = Decimal(str(float(value))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded:.1f}"


def format_user_score_display(user_score) -> str:
    """Format user score for detail card display."""
    if user_score is None:
        return "—"
    try:
        return _round_one_decimal(user_score)
    except (TypeError, ValueError):
        return "—"


USER_SCORE_MIN = 0.0
USER_SCORE_MAX = 10.0
USER_SCORE_STEP = 0.1
YEAR_FILTER_MIN = 1980
YEAR_FILTER_MAX = date.today().year
YEAR_FILTER_DEFAULT_FROM = 2000
YEAR_FILTER_DEFAULT_TO = date.today().year


def normalize_user_score_value(score) -> float:
    """Normalize user score to one decimal place for storage/display."""
    return float(Decimal(str(float(score))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def get_user_score_spin_value(card: dict) -> float:
    """Return user_score formatted for QDoubleSpinBox."""
    score = card.get("user_score")
    if score is None:
        return USER_SCORE_MIN
    return normalize_user_score_value(score)


def build_user_score_update_payload(user_score: float) -> dict:
    """Build update_dataset_record patch for user_score only."""
    return {"main_info": {"user_score": normalize_user_score_value(user_score)}}


def save_watched_user_score(dataset_key: str, user_score: float):
    """Save user_score for a watched record via the dataset update pipeline."""
    from dataset.dataset_records import update_dataset_record

    return update_dataset_record(
        dataset_key,
        build_user_score_update_payload(user_score),
        source_name="desktop_gui",
    )


def format_save_user_score_status(result) -> str:
    """Short GUI status text after save attempt."""
    if result.ok and result.reason == "updated":
        return "Оценка сохранена"
    if result.ok and result.reason == "nothing_changed":
        return "Изменений нет"
    return result.message


def validate_score_edit_entry(entry: WatchedEntry | None) -> tuple[bool, str]:
    """Validate that a watched entry can be used for score edit dialog."""
    if entry is None:
        return False, "Запись не выбрана"

    dataset_key, _movie, _card = entry
    if str(dataset_key).strip() == "":
        return False, "Запись не выбрана"

    return True, ""


def format_rating_score_display(score) -> str | None:
    """Format external rating for pill badges."""
    if score is None:
        return None
    try:
        return _round_one_decimal(score)
    except (TypeError, ValueError):
        return None


def build_meta_pill_items(card: dict) -> list[dict]:
    """Build IMDb/KP pill display items for the detail card."""
    items: list[dict] = []
    imdb = format_rating_score_display(card.get("imdb_score"))
    if imdb is not None:
        items.append(format_imdb_pill(imdb))

    kp = format_rating_score_display(card.get("kp_score"))
    if kp is not None:
        items.append(format_kp_pill(kp))

    return items


def build_meta_pill_labels(card: dict) -> list[str]:
    """Plain-text pill labels (legacy helper for tests)."""
    labels: list[str] = []
    year = card.get("year")
    if year not in (None, ""):
        labels.append(str(year))

    imdb = format_rating_score_display(card.get("imdb_score"))
    if imdb is not None:
        labels.append(f"IMDb {imdb}")

    kp = format_rating_score_display(card.get("kp_score"))
    if kp is not None:
        labels.append(f"КП {kp}")

    return labels


def format_year_pill(year) -> str:
    return str(year)


def _rating_indicator_item(source: str, score: str, label: str) -> dict:
    return {
        "kind": "rating_indicator",
        "source": source,
        "label": label,
        "score": score,
        "accent": COLOR_IMDB_ACCENT if source == "imdb" else COLOR_KP_ACCENT,
    }


def format_imdb_pill(score: str) -> dict:
    return _rating_indicator_item("imdb", score, "IMDb")


def format_kp_pill(score: str) -> dict:
    return _rating_indicator_item("kp", score, "КП")


def format_genre_pill_label(genre: str) -> str:
    return str(genre).strip()


def build_genre_pill_labels(card: dict) -> list[str]:
    """Build genre pill labels for the detail card."""
    genres = card.get("genres") or []
    return [format_genre_pill_label(genre) for genre in genres if str(genre).strip()]


def build_detail_info_pill_labels(card: dict) -> list[str]:
    """Build lower info pills shown near genres."""
    labels: list[str] = []
    year = card.get("year")
    if year not in (None, ""):
        labels.append(format_year_pill(year))
    labels.extend(build_genre_pill_labels(card))
    country = get_country_display(card)
    if country is not None:
        labels.append(country)
    return labels


def get_country_display(card: dict) -> str | None:
    """Return country label for detail card or None when missing."""
    country = card.get("country")
    if country in (None, ""):
        return None
    text = str(country).strip()
    return text if text else None


def has_overview_text(card: dict) -> bool:
    """Return True when the card has non-empty overview text."""
    overview = card.get("overview")
    if overview in (None, ""):
        return False
    return bool(str(overview).strip())


def get_overview_display(card: dict) -> str:
    """Return overview text for detail card."""
    return str(card.get("overview", "")).strip()


def format_list_label(card: dict) -> str:
    """Compact label for the left-hand list."""
    title = card.get("title") or "Без названия"
    year = card.get("year")
    score_label = format_user_score_display(card.get("user_score"))
    parts = [title]
    if year is not None:
        parts.append(f"({year})")
    label = " ".join(parts)
    if score_label != "—":
        label = f"{label}  ·  {score_label}"
    return label


def format_watched_list_status(
    visible_count: int,
    total_count: int,
    query: str = "",
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
) -> str:
    """Status bar text for watched list filter results."""
    normalized = query.strip()
    has_filter = bool(normalized) or has_score_filter or has_year_filter or has_genre_filter
    if visible_count == 0:
        return "Ничего не найдено" if has_filter else "Список пуст"
    if has_filter:
        return f"Показано {visible_count} из {total_count}"
    return f"Всего {visible_count}"


def format_watched_list_counter(
    visible_count: int,
    total_count: int,
    query: str = "",
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
) -> str:
    """Compact counter shown above the watched list."""
    normalized = query.strip()
    has_filter = bool(normalized) or has_score_filter or has_year_filter or has_genre_filter
    if visible_count == 0:
        return "Ничего не найдено" if has_filter else "Список пуст"
    if has_filter or visible_count != total_count:
        return f"{visible_count} из {total_count}"
    return f"Всего {visible_count}"


def count_active_filters(
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
) -> int:
    """Return the number of active score/year/genre filters (search excluded)."""
    return int(has_score_filter) + int(has_year_filter) + int(has_genre_filter)


def score_filter_is_active(min_score: float, max_score: float) -> bool:
    """Return True when user score range differs from the default 0.0–10.0."""
    return float(min_score) > USER_SCORE_MIN or float(max_score) < USER_SCORE_MAX


def year_filter_is_active(year_from: int, year_to: int) -> bool:
    """Return True when year range differs from the default 2000–current year."""
    return int(year_from) != YEAR_FILTER_DEFAULT_FROM or int(year_to) != YEAR_FILTER_DEFAULT_TO


def genre_filter_is_active(genre: str | None) -> bool:
    """Return True when a specific genre is selected instead of all genres."""
    if genre is None:
        return False
    selected = str(genre).strip()
    return selected != "" and selected != GENRE_FILTER_ALL


def watched_filters_are_active(
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
) -> bool:
    """Return True when at least one score/year/genre filter is active."""
    return bool(has_score_filter or has_year_filter or has_genre_filter)


def watched_filters_are_active_from_ranges(
    min_score: float = USER_SCORE_MIN,
    max_score: float = USER_SCORE_MAX,
    year_from: int = YEAR_FILTER_DEFAULT_FROM,
    year_to: int = YEAR_FILTER_DEFAULT_TO,
    genre: str | None = None,
) -> bool:
    """Return True when any filter range/genre differs from defaults."""
    return (
        score_filter_is_active(min_score, max_score)
        or year_filter_is_active(year_from, year_to)
        or genre_filter_is_active(genre)
    )


def format_watched_filters_label(
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
    is_expanded: bool = False,
) -> str:
    """Build the watched filters toggle label for the sidebar."""
    arrow = "▾" if is_expanded else "▸"
    if watched_filters_are_active(has_score_filter, has_year_filter, has_genre_filter):
        return f"{arrow} Фильтры активны"
    return f"{arrow} Фильтры"


def resolve_local_poster_path(movie: dict, card: dict | None = None) -> str | None:
    """Return a local filesystem poster path when available. Never uses network."""
    display_card = card if card is not None else build_watched_movie_card(movie)
    candidates: list[str | None] = [
        display_card.get("poster_path"),
        _local_path(display_card.get("poster_src")),
        _local_path(movie.get("poster_src")),
        _local_path(movie.get("poster_path")),
        _local_path(_nested_poster_value(movie, "path")),
        _local_path(_nested_poster_value(movie, "poster_path")),
    ]

    for candidate in candidates:
        if candidate is None:
            continue
        path = Path(candidate)
        if path.is_file():
            return str(path)
    return None


def _local_path(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.startswith(("http://", "https://")):
        return None
    return text


def _nested_poster_value(movie: dict, field: str) -> str | None:
    poster = movie.get("poster")
    if isinstance(poster, dict):
        return poster.get(field)
    return None


POSTER_WIDTH = 220
POSTER_HEIGHT = 330
LIST_ITEM_HEIGHT = 72
LIST_THUMB_WIDTH = 40
LIST_THUMB_HEIGHT = 60
LIST_ITEM_H_PADDING = 10
LIST_ITEM_V_PADDING = 6
LIST_TEXT_GAP = 10
GENRES_PER_ROW = 4
CARD_PADDING = 22
RATING_CIRCLE_WIDGET_SIZE = 88
RATING_CIRCLE_DIAMETER = 78

POSTER_PLACEHOLDER_STYLE = build_poster_placeholder_style()
POSTER_IMAGE_STYLE = build_poster_image_style()
DETAIL_CARD_STYLE = build_detail_card_style()

_thumb_pixmap_cache: dict[str, object] = {}


def _load_list_thumb_pixmap(poster_path: str | None):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap

    if poster_path is None:
        return None
    cached = _thumb_pixmap_cache.get(poster_path)
    if cached is not None:
        return cached if cached is not False else None
    pixmap = QPixmap(poster_path)
    if pixmap.isNull():
        _thumb_pixmap_cache[poster_path] = False
        return None
    scaled = pixmap.scaled(
        LIST_THUMB_WIDTH,
        LIST_THUMB_HEIGHT,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    _thumb_pixmap_cache[poster_path] = scaled
    return scaled


class WatchedListItemDelegate:
    """Rich list row: thumbnail, title, year and user score."""

    def __new__(cls, parent=None):
        from PyQt6.QtCore import QRect, QSize, Qt
        from PyQt6.QtGui import QColor, QFont, QPainter, QPen
        from PyQt6.QtWidgets import QStyledItemDelegate, QStyle

        class _WatchedListItemDelegate(QStyledItemDelegate):
            def sizeHint(self, option, index):
                width = option.rect.width() if option.rect.width() > 0 else 280
                return QSize(width, LIST_ITEM_HEIGHT)

            def paint(self, painter, option, index) -> None:
                entry = index.data(Qt.ItemDataRole.UserRole)
                if not isinstance(entry, tuple) or len(entry) != 3:
                    super().paint(painter, option, index)
                    return

                _key, movie, card = entry
                rect = option.rect.adjusted(2, 1, -2, -1)
                is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
                is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

                if is_selected:
                    painter.setPen(QPen(QColor(COLOR_ACCENT), 2))
                    painter.setBrush(QColor(COLOR_ACCENT_SOFT))
                elif is_hovered:
                    painter.setPen(QPen(QColor(COLOR_BORDER), 1))
                    painter.setBrush(QColor(COLOR_CARD_ALT))
                else:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)

                if is_selected or is_hovered:
                    painter.drawRoundedRect(rect, 10, 10)

                thumb_left = rect.left() + LIST_ITEM_H_PADDING
                thumb_top = rect.top() + (rect.height() - LIST_THUMB_HEIGHT) // 2
                thumb_rect = QRect(thumb_left, thumb_top, LIST_THUMB_WIDTH, LIST_THUMB_HEIGHT)

                poster_path = resolve_local_poster_path(movie, card)
                thumb = _load_list_thumb_pixmap(poster_path)
                if thumb is not None:
                    clip = thumb_rect.adjusted(1, 1, -1, -1)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(COLOR_CARD))
                    painter.drawRoundedRect(clip, 6, 6)
                    painter.drawPixmap(clip, thumb)
                else:
                    painter.setPen(QPen(QColor(COLOR_BORDER), 1))
                    painter.setBrush(QColor(COLOR_CARD))
                    painter.drawRoundedRect(thumb_rect, 6, 6)
                    placeholder_font = QFont(FONT_FAMILY, 8)
                    painter.setFont(placeholder_font)
                    painter.setPen(QColor(COLOR_TEXT_SECONDARY))
                    painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "—")

                text_left = thumb_rect.right() + LIST_TEXT_GAP
                text_right = rect.right() - LIST_ITEM_H_PADDING
                text_width = max(40, text_right - text_left)

                title = str(card.get("title") or _key or "Без названия")
                year = card.get("year")
                year_text = str(year) if year not in (None, "") else ""
                score_text = format_user_score_display(card.get("user_score"))
                meta_parts = [part for part in (year_text, score_text if score_text != "—" else "") if part]
                meta_text = " · ".join(meta_parts)

                title_font = QFont(FONT_FAMILY)
                title_font.setPointSize(10)
                title_font.setBold(True)
                meta_font = QFont(FONT_FAMILY)
                meta_font.setPointSize(9)

                title_rect = QRect(text_left, rect.top() + LIST_ITEM_V_PADDING, text_width, 28)
                meta_rect = QRect(text_left, title_rect.bottom(), text_width, 20)

                painter.setFont(title_font)
                painter.setPen(QColor(COLOR_TEXT if is_selected else COLOR_TEXT))
                painter.drawText(
                    title_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    _elide_text(painter, title, title_rect.width()),
                )

                if meta_text:
                    painter.setFont(meta_font)
                    painter.setPen(QColor(COLOR_ACCENT if is_selected else COLOR_TEXT_SECONDARY))
                    painter.drawText(
                        meta_rect,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        meta_text,
                    )

                painter.restore()

        return _WatchedListItemDelegate(parent)


def _elide_text(painter, text: str, max_width: int) -> str:
    from PyQt6.QtCore import Qt

    metrics = painter.fontMetrics()
    return metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(20, max_width))


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def _make_pill_label(text: str, object_name: str, rich: bool = False):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel

    pill = QLabel()
    pill.setObjectName(object_name)
    if rich:
        pill.setTextFormat(Qt.TextFormat.RichText)
    pill.setText(text)
    return pill


class RatingCircleIndicator:
    """Small circular score indicator with a radial progress ring."""

    def __new__(cls, label: str, score=None, accent: str = COLOR_ACCENT):
        from PyQt6.QtWidgets import QWidget

        class _RatingCircleWidget(QWidget):
            def __init__(self, label_text: str, score_value, accent_color: str) -> None:
                super().__init__()
                self._label = label_text
                self._score = score_value
                self._accent = accent_color
                self.setFixedSize(RATING_CIRCLE_WIDGET_SIZE, RATING_CIRCLE_WIDGET_SIZE)
                self.setStyleSheet(TRANSPARENT_STYLE)

            def set_score(self, score_value) -> None:
                self._score = score_value
                self.update()

            def paintEvent(self, _event) -> None:
                from PyQt6.QtCore import QRectF, Qt
                from PyQt6.QtGui import QColor, QFont, QPainter, QPen

                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

                left = (self.width() - RATING_CIRCLE_DIAMETER) / 2
                top = (self.height() - RATING_CIRCLE_DIAMETER) / 2
                rect = QRectF(left, top, RATING_CIRCLE_DIAMETER, RATING_CIRCLE_DIAMETER)
                inner_rect = rect.adjusted(6, 6, -6, -6)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(COLOR_SURFACE))
                painter.drawEllipse(rect)

                ring_rect = rect.adjusted(5, 5, -5, -5)
                track_pen = QPen(QColor(COLOR_BORDER), 5)
                track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(track_pen)
                painter.drawArc(ring_rect, 90 * 16, -360 * 16)

                progress = _score_progress(self._score)
                if progress > 0:
                    accent_pen = QPen(QColor(self._accent), 5)
                    accent_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    painter.setPen(accent_pen)
                    painter.drawArc(ring_rect, 90 * 16, -int(360 * 16 * progress))

                painter.setPen(QColor(COLOR_TEXT))
                value_font = QFont(FONT_FAMILY)
                value_font.setPointSize(FONT_RATING_VALUE_POINT)
                value_font.setBold(True)
                painter.setFont(value_font)
                painter.drawText(inner_rect.adjusted(0, -8, 0, 0), Qt.AlignmentFlag.AlignCenter, _score_text(self._score))

                painter.setPen(QColor(COLOR_TEXT_SECONDARY))
                label_font = QFont(FONT_FAMILY)
                label_font.setPointSize(FONT_RATING_LABEL_POINT)
                label_font.setBold(True)
                painter.setFont(label_font)
                painter.drawText(inner_rect.adjusted(0, 38, 0, -4), Qt.AlignmentFlag.AlignCenter, self._label)

        return _RatingCircleWidget(label, score, accent)


def _score_progress(score) -> float:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, value / 10.0))


def _score_text(score) -> str:
    return format_user_score_display(score)


def _make_meta_pill(item: dict):
    return RatingCircleIndicator(
        item.get("label", ""),
        item.get("score"),
        item.get("accent", COLOR_ACCENT),
    )


def _fill_meta_pill_row(layout, items: list[dict]) -> None:
    _clear_layout(layout)
    layout.setSpacing(8)
    for item in items:
        layout.addWidget(_make_meta_pill(item))
    layout.addStretch()


def _fill_pill_rows(container_layout, labels: list[str], object_name: str) -> None:
    _clear_layout(container_layout)
    container_layout.setSpacing(8)
    if len(labels) == 0:
        return
    from PyQt6.QtWidgets import QHBoxLayout

    for index in range(0, len(labels), GENRES_PER_ROW):
        row = QHBoxLayout()
        row.setSpacing(8)
        for text in labels[index : index + GENRES_PER_ROW]:
            row.addWidget(_make_pill_label(text, object_name))
        row.addStretch()
        container_layout.addLayout(row)


class WatchedDetailCard:
    """Detail card widget for the selected watched title."""

    def __init__(self, parent=None) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import (
            QFrame,
            QHBoxLayout,
            QLabel,
            QSizePolicy,
            QVBoxLayout,
            QWidget,
        )

        self._poster_source_pixmap = None
        card = self

        class DetailCardFrame(QFrame):
            def resizeEvent(self, event) -> None:
                super().resizeEvent(event)
                card._schedule_poster_height_sync()

        self._frame = DetailCardFrame(parent)
        self._frame.setObjectName("detailCard")
        self._frame.setStyleSheet(DETAIL_CARD_STYLE)
        self._frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        root = QVBoxLayout(self._frame)
        root.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        root.setSpacing(OVERVIEW_SECTION_TOP_SPACING)

        top_row = QHBoxLayout()
        top_row.setSpacing(22)

        self._poster_label = QLabel("Нет постера")
        self._poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster_label.setFixedWidth(POSTER_WIDTH)
        self._poster_label.setScaledContents(False)
        self._poster_label.setStyleSheet(POSTER_PLACEHOLDER_STYLE)

        self._info_column_widget = QWidget()
        self._info_column_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._info_column_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        info_column = QVBoxLayout(self._info_column_widget)
        info_column.setContentsMargins(0, 0, 0, 0)
        info_column.setSpacing(12)

        self._title_label = QLabel("Выберите тайтл слева")
        self._title_label.setObjectName("detailTitle")
        self._title_label.setWordWrap(True)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._title_label.setMinimumHeight(36)
        self._title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        metrics_row_widget = QWidget()
        metrics_row_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._metrics_row_widget = metrics_row_widget
        self._metrics_row = QHBoxLayout(metrics_row_widget)
        self._metrics_row.setContentsMargins(0, 0, 0, 0)
        self._metrics_row.setSpacing(10)

        self._score_indicator = RatingCircleIndicator("моя", None, COLOR_ACCENT)

        self._meta_pills_widget = QWidget()
        self._meta_pills_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._meta_pills_layout = QHBoxLayout(self._meta_pills_widget)
        self._meta_pills_layout.setContentsMargins(0, 0, 0, 0)
        self._meta_pills_layout.setSpacing(10)

        self._metrics_row.addWidget(self._score_indicator, alignment=Qt.AlignmentFlag.AlignLeft)
        self._metrics_row.addWidget(self._meta_pills_widget, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._metrics_row.addStretch()

        self._genre_section = QWidget()
        self._genre_section.setStyleSheet(TRANSPARENT_STYLE)
        self._genre_pills_layout = QVBoxLayout(self._genre_section)
        self._genre_pills_layout.setContentsMargins(0, 0, 0, 0)
        self._genre_pills_layout.setSpacing(8)

        self._overview_frame = QFrame()
        self._overview_frame.setObjectName("overviewBlock")
        self._overview_frame.setFrameShape(QFrame.Shape.NoFrame)
        self._overview_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        overview_layout = QVBoxLayout(self._overview_frame)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.setSpacing(0)

        self._overview_title_label = QLabel("Описание")
        self._overview_title_label.setObjectName("overviewTitle")
        self._overview_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self._overview_divider = QFrame()
        self._overview_divider.setObjectName("overviewDivider")
        self._overview_divider.setFrameShape(QFrame.Shape.HLine)
        self._overview_divider.setFixedHeight(1)

        self._overview_label = QLabel("")
        self._overview_label.setObjectName("overviewText")
        self._overview_label.setWordWrap(True)
        self._overview_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._overview_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        overview_layout.addWidget(self._overview_title_label)
        overview_layout.addSpacing(OVERVIEW_TITLE_DIVIDER_SPACING)
        overview_layout.addWidget(self._overview_divider)
        overview_layout.addSpacing(OVERVIEW_DIVIDER_TEXT_SPACING)
        overview_layout.addWidget(self._overview_label)

        info_column.addWidget(self._title_label)
        info_column.addSpacing(2)
        info_column.addWidget(self._genre_section)
        info_column.addSpacing(2)
        info_column.addWidget(metrics_row_widget)

        top_row.addWidget(self._poster_label, alignment=Qt.AlignmentFlag.AlignTop)
        top_row.addWidget(self._info_column_widget, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(top_row)
        root.addWidget(self._overview_frame)
        root.addStretch(1)

    @property
    def widget(self):
        return self._frame

    def _info_column_content_width(self) -> int:
        width = self._info_column_widget.width()
        if width > 0:
            return width
        frame_width = self._frame.width()
        if frame_width <= 0:
            return 0
        return max(120, frame_width - POSTER_WIDTH - 22 - (2 * CARD_PADDING))

    def _measure_info_column_height(self) -> int:
        content_width = self._info_column_content_width()
        if content_width > 0:
            title_height = self._title_label.heightForWidth(content_width)
        else:
            title_height = self._title_label.sizeHint().height()
        title_height = max(title_height, self._title_label.minimumHeight())

        parts = [title_height]
        if self._genre_section.isVisible():
            self._genre_section.adjustSize()
            parts.append(self._genre_section.sizeHint().height())
        self._metrics_row_widget.adjustSize()
        parts.append(self._metrics_row_widget.sizeHint().height())

        layout = self._info_column_widget.layout()
        spacing = layout.spacing() if layout is not None else 12
        extra_spacing = 0
        if len(parts) >= 2:
            extra_spacing += 2
        if self._genre_section.isVisible() and len(parts) >= 3:
            extra_spacing += 2

        gaps = max(0, len(parts) - 1)
        return sum(parts) + gaps * spacing + extra_spacing

    def _target_poster_height(self) -> int:
        info_height = self._measure_info_column_height()
        if info_height <= 0:
            return POSTER_HEIGHT
        return min(POSTER_HEIGHT, info_height)

    def _sync_poster_height_to_info(self) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap

        height = self._target_poster_height()
        self._poster_label.setFixedSize(POSTER_WIDTH, height)

        if self._poster_source_pixmap is not None and not self._poster_source_pixmap.isNull():
            scaled = self._poster_source_pixmap.scaled(
                POSTER_WIDTH,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._poster_label.setStyleSheet(POSTER_IMAGE_STYLE)
            self._poster_label.setText("")
            self._poster_label.setPixmap(scaled)
            return

        if self._poster_label.pixmap() is None or self._poster_label.pixmap().isNull():
            self._poster_label.setPixmap(QPixmap())
            if self._poster_label.text() == "":
                self._poster_label.setText("Нет постера")
            self._poster_label.setStyleSheet(POSTER_PLACEHOLDER_STYLE)

    def _schedule_poster_height_sync(self) -> None:
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._sync_poster_height_to_info)

    def _set_poster_placeholder(self) -> None:
        from PyQt6.QtGui import QPixmap

        self._poster_source_pixmap = None
        self._poster_label.setPixmap(QPixmap())
        self._poster_label.setText("Нет постера")
        self._poster_label.setStyleSheet(POSTER_PLACEHOLDER_STYLE)

    def _set_poster_image(self, poster_path: str) -> bool:
        from PyQt6.QtGui import QPixmap

        pixmap = QPixmap(poster_path)
        if pixmap.isNull():
            return False

        self._poster_source_pixmap = pixmap
        self._sync_poster_height_to_info()
        return True

    def show_empty(self, title: str = "Выберите тайтл слева") -> None:
        self._set_poster_placeholder()
        self._title_label.setText(title)
        self._score_indicator.set_score(None)
        _fill_meta_pill_row(self._meta_pills_layout, [])
        self._meta_pills_widget.setVisible(False)
        _fill_pill_rows(self._genre_pills_layout, [], "genrePill")
        self._genre_section.setVisible(False)
        self._overview_label.setText("")
        self._overview_frame.setVisible(False)
        self._schedule_poster_height_sync()

    def show_entry(self, entry: WatchedEntry) -> None:
        _, movie, card = entry
        self._title_label.setText(card.get("title") or entry[0])
        self._score_indicator.set_score(card.get("user_score"))

        meta_pills = build_meta_pill_items(card)
        _fill_meta_pill_row(self._meta_pills_layout, meta_pills)
        self._meta_pills_widget.setVisible(len(meta_pills) > 0)

        detail_pills = build_detail_info_pill_labels(card)
        _fill_pill_rows(self._genre_pills_layout, detail_pills, "genrePill")
        self._genre_section.setVisible(len(detail_pills) > 0)

        if has_overview_text(card):
            self._overview_label.setText(get_overview_display(card))
            self._overview_frame.setVisible(True)
        else:
            self._overview_label.setText("")
            self._overview_frame.setVisible(False)

        poster_path = resolve_local_poster_path(movie, card)
        if poster_path is None or self._set_poster_image(poster_path) is False:
            self._set_poster_placeholder()
        self._schedule_poster_height_sync()
