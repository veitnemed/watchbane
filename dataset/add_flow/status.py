"""Status formatting for add-title resolve reports."""


def format_resolve_status_lines(statuses: dict) -> list[str]:
    """Compact status lines for GUI."""
    if not isinstance(statuses, dict):
        return []
    lines = []
    for key, label in (
        ("tmdb_api", "TMDb API"),
    ):
        value = statuses.get(key)
        if value not in (None, ""):
            lines.append(f"{label}: {value}")
    return lines
