"""Tests for stats summary, analytics split, and service facade."""


def test_dataset_stats_wrapper_reexports_summary() -> None:
    from dataset.dataset_stats import get_dataset_stats
    from dataset.stats.summary import get_dataset_stats as source

    assert get_dataset_stats is source


def test_score_analytics_wrapper_reexports_build() -> None:
    from dataset.analytics.build import build_score_analytics as source
    from dataset.score_analytics import build_score_analytics

    assert build_score_analytics is source


def test_service_facade_exports_core_operations() -> None:
    import dataset.service as service

    assert hasattr(service, "add_dataset_record")
    assert hasattr(service, "update_dataset_record")
    assert hasattr(service, "delete_watched_record")
    assert hasattr(service, "resolve_title_for_add")
    assert hasattr(service, "save_add_title_record")
    assert hasattr(service, "build_score_analytics")
    assert hasattr(service, "get_dataset_stats")
