"""TMDb candidate snapshot acquisition use cases."""

from __future__ import annotations

from candidates.tmdb_acquisition_service import build_and_save_tmdb_candidate_pool, import_tmdb_result_to_pool


def get_tmdb_startup_readiness() -> dict:
    """Return network and credential readiness before opening the main UI."""
    from apis.tmdb_connectivity import evaluate_tmdb_startup_readiness

    return evaluate_tmdb_startup_readiness()


def reload_tmdb_runtime() -> None:
    """Reload locally entered TMDb credentials after the startup gate."""
    from apis.tmdb.auth import reload_tmdb_env

    reload_tmdb_env()

__all__ = [
    "build_and_save_tmdb_candidate_pool", "get_tmdb_startup_readiness",
    "import_tmdb_result_to_pool", "reload_tmdb_runtime",
]
