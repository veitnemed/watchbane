"""Internal console helper for local SQL search.

This module is not part of the public candidate flow.
"""

from apis import imdb_sql as sql_search
from ui.console import request
from ui.console import title_presenters


def print_sql_title_result(data: dict) -> None:
    """Print compact local SQL search result details."""
    title_presenters.print_sql_title_result(data)


def search_sql_title_by_name() -> None:
    """Search a title in the local SQL database by title and country."""
    title = request.loop_input(
        text="\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 >> ",
        funcs_list=[lambda value: str(value).strip() != ""],
    )
    country = request.loop_input_with_default(
        text="\u0421\u0442\u0440\u0430\u043d\u0430 [\u0420\u043e\u0441\u0441\u0438\u044f] >> ",
        funcs_list=[lambda value: str(value).strip() != ""],
        default_value="\u0420\u043e\u0441\u0441\u0438\u044f",
    )
    result = sql_search.search_title_in_sql(title, country)

    if result["ok"] is False:
        print(f"\u0422\u0430\u0439\u0442\u043b \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d: {result['details'] or result['error']}")
        return

    print_sql_title_result(result["data"])
