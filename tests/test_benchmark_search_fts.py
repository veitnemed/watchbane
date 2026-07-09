"""Smoke tests for benchmark_search_fts script."""

from __future__ import annotations


def test_benchmark_search_fts_smoke(tmp_path, monkeypatch, capsys) -> None:
    from storage.sqlite import candidate_repository

    data_dir = tmp_path / "data"
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    candidate_repository.save_candidate_pool_dict(
        {
            "show|2024": {
                "title": "Show",
                "year": 2024,
                "localized": {"en": {"overview": "A detective show."}},
                "final_score": 7.0,
            },
        },
        path=data_dir / "watchbane.sqlite3",
    )

    from scripts.reports import benchmark_search_fts

    assert benchmark_search_fts.main(["--repeats", "1", "--query", "detective"]) == 0
    output = capsys.readouterr().out
    assert '"pool_size": 1' in output
    assert '"sql_p50_ms"' in output
