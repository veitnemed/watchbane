"""Console actions for external API diagnostics."""

import time


def _print_api_ping_result(name: str, host: str, result: dict, elapsed_ms: float | None = None) -> None:
    print(f"{name} ({host})")
    if result.get("ok") is True:
        ms = elapsed_ms if elapsed_ms is not None else result.get("elapsed_ms")
        status_line = "\u0421\u0442\u0430\u0442\u0443\u0441: OK"
        if ms is not None:
            status_line += f" ({ms} \u043c\u0441)"
        print(f"  {status_line}")
    else:
        print("  \u0421\u0442\u0430\u0442\u0443\u0441: \u041e\u0448\u0438\u0431\u043a\u0430")
        details = result.get("details") or result.get("error") or "unknown_error"
        print(f"  \u041f\u0440\u0438\u0447\u0438\u043d\u0430: {details}")
    print()


def ping_external_apis() -> None:
    """Check TMDb availability with a short API request."""
    from apis import tmdb_api

    print("\u041f\u0438\u043d\u0433 TMDb API...\n")

    started = time.monotonic()
    tmdb_result = tmdb_api.check_api_available()
    tmdb_ms = round((time.monotonic() - started) * 1000, 1)
    _print_api_ping_result("TMDb API", "api.themoviedb.org", tmdb_result, tmdb_ms)
