"""QSS builder for main application shell (composes section stylesheets)."""

from __future__ import annotations

from desktop.theme.styles.candidates_shell import build_candidates_shell_style
from desktop.theme.styles.chips import build_chip_selector_style
from desktop.theme.styles.form_controls import build_form_controls_style
from desktop.theme.styles.lists import build_lists_style
from desktop.theme.styles.settings import build_settings_style
from desktop.theme.styles.shell import build_shell_style
from desktop.theme.styles.watched_shell import build_watched_shell_style


def build_app_style() -> str:
    """Return the main desktop application stylesheet."""
    return "".join(
        (
            build_shell_style(),
            build_form_controls_style(),
            build_lists_style(),
            build_watched_shell_style(),
            build_chip_selector_style(),
            build_candidates_shell_style(),
            build_settings_style(),
        )
    )
