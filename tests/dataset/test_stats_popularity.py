import importlib


def test_stats_popularity_does_not_import_candidates_or_score_analytics() -> None:
    module = importlib.import_module("dataset.stats.popularity")
    source_path = module.__file__
    assert source_path is not None
    with open(source_path, encoding="utf-8") as handle:
        text = handle.read()
    assert "candidates" not in text
    assert "score_analytics" not in text
