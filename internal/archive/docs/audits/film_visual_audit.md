# Film Visual Card Audit

Задача: привести общий `DetailCard` для фильмов и сериалов к референсу из `.codex-visual-film-card/reference.png`, сохранив единый визуальный контракт для movies/tv. Различия между типами должны оставаться только в текстах/бейджах/акцентах, а не в разных layout-системах.

Baseline:

- Reference: `D:\VS PROJJJ\vscode projects\.codex-visual-film-card\reference.png`
- Native Windows screenshot, `QT_QPA_PLATFORM=windows`, fonts: `family_count=355`, `Segoe UI=True`, `Arial=True`
- Series baseline: `screens/tmp_ui/film_card/baseline_scale100.png`
- Movie baseline: `screens/tmp_ui/film_card/baseline_movie_scale100.png`

| component | file | object/class | current style source | intended change |
| --- | --- | --- | --- | --- |
| 3-column title screen layout | `desktop/watched/tab.py` | `WatchedTabView._build_right_panel`, `QSplitter`, `QScrollArea` | `desktop/theme/shell_layout.py`, `desktop/theme/styles/shell.py`, `desktop/theme/styles/watched_shell.py` | Match reference: dark blue root, stable left list / poster / info proportions, no accidental scrollbars over content, checked at 75/100/150 scale. |
| Shared title detail card | `desktop/shared/detail/card.py` | `DetailCard` | `desktop/shared/detail/profiles.py`, `desktop/theme/styles/detail_card.py` | Keep one card system for movies and series; restyle colors, spacing, ring/stars/chips without moving business logic into widgets. |
| Detail card widget tree | `desktop/shared/detail/card_layout.py` | `build_detail_card_layout`, `QFrame#detailHeroCard`, `QFrame#detailPosterShell`, `QWidget#detailInfoColumn` | `build_detail_card_style()`, `DetailCardLayoutProfile` | Rework layout toward reference: poster column center-left, right info block with visible section dividers, no chip/main-info overlap, stable wrapping. |
| Left title list | `desktop/shared/detail/list_delegate.py` | `WatchedListItemDelegate` | delegate painting with `COLOR_*`, `detail_profiles.LIST_*` | Make rows read like reference cards: darker row surface, cyan selected border/glow, better thumbnail frame, muted meta, blue selected state. |
| List container and scrollbars | `desktop/theme/styles/lists.py`, `desktop/theme/styles/watched_shell.py` | `QListWidget`, `QListWidget#watchedList` | `build_lists_style()`, `build_watched_shell_style()` | Use film palette list surface and scrollbar colors from brief; avoid default scrollbar artifacts visible in baseline. |
| Add-title button | `desktop/theme/styles/watched_shell.py` | `QPushButton#watchedAddTitle` | old cyan gradient tokens | Align with reference blue control style; keep button readable and scaled. |
| Center poster card | `desktop/shared/detail/card_layout.py`, `desktop/shared/detail/card_poster.py` | `QFrame#detailPosterShell`, `QLabel#detailPoster`, poster overlay | `DETAIL_POSTER_*`, `build_poster_*_style()` | Poster shell should match reference: thin cyan-blue border, rounded corners, no distortion, stable aspect at 75/100/150. |
| Movie/series badge | `desktop/shared/detail/card.py`, `desktop/shared/detail/card_layout.py`, `desktop/shared/detail/presenters.py` | currently only `QLabel#detailUserScoreBadge` score badge | `build_user_score_badge_item()`, `QLabel#detailUserScoreBadge` | Add or adapt bottom media-type badge later if required by prompt sequence; preserve watched score badge behavior. |
| TMDb ring | `desktop/shared/detail/rating_indicator.py`, `desktop/shared/detail/card_pills.py` | `RatingCircleIndicator`, `make_meta_pill` | `COLOR_ACCENT`, `COLOR_BORDER`, `COLOR_SURFACE`, score ring helpers | Use brief colors: track `#17314F`, value `#2EA8FF`, interior dark, reference-sized label/value. |
| User stars | `desktop/shared/detail/rating_indicator.py` | `StarRatingIndicator` | `COLOR_STAR_ACTIVE`, `COLOR_STAR_INACTIVE` | Change from yellow to blue reference stars; keep fractional fill and fixed scaled geometry. |
| Right info card | `desktop/shared/detail/card_layout.py`, `desktop/shared/detail/card.py`, `desktop/shared/detail/main_info.py` | `QFrame#detailMainInfoPanel`, labels/values grid | `DETAIL_MAIN_INFO_*`, `build_detail_card_style()` | Match right reference card: darker framed panel, row separators/icons, no value overlap, correct movie vs series metadata. |
| Genre chips | `desktop/shared/detail/card_pills.py`, `desktop/shared/detail/presenters.py` | `fill_detail_chip_rows`, `QLabel#genrePill` | `DETAIL_CHIP_*`, `COLOR_DETAIL_CHIP_*` | Use reference chip fill/border/text; fix observed overlap on movie baseline and keep two-row overflow behavior. |
| Icons/dividers | `desktop/shared/detail/action_icons.py`, `desktop/shared/detail/card_layout.py`, `desktop/theme/styles/detail_card.py` | action icons, header dividers | generated icon painter, `QFrame#detail*Divider` | Introduce reference-like cyan dividers and small row icons where prompt requires; avoid decorative duplication. |
| App/window palette | `desktop/theme/tokens.py`, `desktop/theme/styles/shell.py` | `COLOR_*`, `QMainWindow`, `QTabWidget#mainTabs` | token module and shell QSS builders | Introduce film palette tokens first, then reuse from QSS/builders instead of hard-coded colors. |

Observed baseline gaps vs reference:

- Movie screenshot for `Горничная` shows chip overlap in the top chip row.
- Movie main-info panel text overlaps heavily at the current 100% window width.
- The movie baseline selected through `media_type=movie` still displays `Тип: Сериал`; this needs data/presenter verification before visual hardening.
- Score badge is white/inverted while reference uses colder dark-blue film styling and a separate media badge near the poster bottom.
- User stars are yellow, not reference blue.
- Left list selected state is close in hue but lacks the reference row depth and stable scrollbar styling.
- Right-side content is not visually separated enough from the hero background; dividers are too sparse compared with the reference.
- Several source files contain existing mojibake strings. This audit does not repair encoding; future text fixes must trace source encoding instead of broad replace.

## 2026-07-08 media badge and WatchBane stars pass

Implemented:

- `ФИЛЬМ` / `СЕРИАЛ` poster badge is now an opaque custom-painted pill instead of a transparent QSS background.
- The label above final-score stars is `WatchBane`, not `Моя оценка`.
- The final-score stars keep a fixed gap from the TMDb ring when `Основная информация` is expanded/collapsed.
- The main-info toggle button has a stable width for `Показать больше` / `Скрыть`, so its text change does not reflow the rating row.
- Main-info values get a bounded maximum width from the detail profile to avoid expanded long values inflating the right column.

Visual verification:

- Platform plugin: `windows`.
- Font probe: `family_count=355`, `Segoe UI=True`, `Arial=True`.
- Checked titles: `Горничная`, `Игра на выживание`, `Чернобыль: Зона отчуждения`.
- Checked scales: 75%, 100%, 150%.
- Checked expanded states: `screens/tmp_ui/film_card/fix_badge_stars_movie0_scale100_expanded.png`, `screens/tmp_ui/film_card/fix_badge_stars_tv0_scale100_expanded.png`.

Remaining risk:

- At 150% the detail view still relies on horizontal scrolling. Rating position and `WatchBane` label are stable, but a later responsive-layout pass should reduce or remove this horizontal scroll.
