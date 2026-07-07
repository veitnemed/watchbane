"""Desktop i18n helpers for add-title resolve statuses."""

from __future__ import annotations

from desktop.i18n import tr

_SOURCE_LABEL_KEYS = {
    "sql": "add_title.resolve.source.sql",
    "sql_second_pass": "add_title.resolve.source.sql_second_pass",
    "kp_api": "add_title.resolve.source.kp_api",
    "tmdb_api": "add_title.resolve.source.tmdb_api",
}

_STAGE_KEYS = {
    "TMDb Search": "add_title.resolve.stage.tmdb_search",
    "TMDb Details": "add_title.resolve.stage.tmdb_details",
    "Подготовка defaults": "add_title.resolve.stage.prepare_defaults",
    "Готово": "add_title.resolve.stage.done",
}

_STATUS_VALUE_KEYS = {
    "поиск": "add_title.resolve.status.searching",
    "найдено": "add_title.resolve.status.found",
    "не найдено": "add_title.resolve.status.not_found",
    "ошибка": "add_title.resolve.status.error",
    "не требуется": "add_title.resolve.status.not_required",
    "ручной ввод": "add_title.resolve.status.manual_entry",
    "успешно": "add_title.resolve.status.success",
    "лимит": "add_title.resolve.status.limit",
}


def translate_resolve_status_value(value) -> str:
    """Translate compact domain status values for desktop UI."""
    text = str(value or "").strip()
    if text == "":
        return ""
    lowered = text.casefold()
    key = _STATUS_VALUE_KEYS.get(lowered)
    if key is not None:
        return tr(key)
    rejected_prefix = "найдено, но отклонено"
    if lowered.startswith(rejected_prefix):
        reason = text[len(rejected_prefix):].strip()
        return tr("add_title.resolve.status.found_rejected", reason=reason)
    return text


def format_resolve_status_lines_for_ui(statuses: dict) -> list[str]:
    """Compact translated status lines for add-title preview dialogs."""
    if not isinstance(statuses, dict):
        return []
    lines: list[str] = []
    for key in ("sql", "sql_second_pass", "kp_api", "tmdb_api"):
        value = statuses.get(key)
        if value in (None, ""):
            continue
        label = tr(_SOURCE_LABEL_KEYS.get(key, key))
        lines.append(f"{label}: {translate_resolve_status_value(value)}")
    return lines


def translate_resolve_progress_message(message: str) -> str:
    """Translate progress messages emitted by the domain resolver."""
    text = str(message or "").strip()
    if text == "":
        return ""
    if ":" not in text:
        return translate_resolve_status_value(text)
    stage, status = (part.strip() for part in text.split(":", 1))
    stage_label = tr(_STAGE_KEYS.get(stage, stage))
    status_label = translate_resolve_status_value(status)
    return f"{stage_label}: {status_label}" if status_label else stage_label


__all__ = [
    "format_resolve_status_lines_for_ui",
    "translate_resolve_progress_message",
    "translate_resolve_status_value",
]
