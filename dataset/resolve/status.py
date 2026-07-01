"""Short status strings for add-flow source reports."""


def get_kp_status(api_data: dict | None, api_error: dict | None) -> str:
    """Возвращает короткий статус KP API для отчёта автозаполнения."""
    if api_data is not None:
        return "найдено"
    if api_error is None:
        return "не найдено"
    if api_error.get("error") in {"not_found", "country_not_found"}:
        return "не найдено"
    return "ошибка"


def get_sql_status(sql_data: dict | None, sql_identity: dict | None) -> str:
    """Возвращает статус SQL-кандидата с учётом identity gate."""
    if sql_data is None:
        return "не найдено"
    if not isinstance(sql_identity, dict):
        return "найдено"

    reason = sql_identity.get("reason")
    if sql_identity.get("accepted") is False:
        return f"найдено, но отклонено ({reason})"
    if reason == "sql_only":
        return "найдено (SQL-only)"
    return "найдено и принято"
