from tools.qa.benchmark_story_qt_cold import summarize


def test_callback_gaps_include_shutdown_boundary_and_overlap_only():
    report = summarize(1.0, 1.220, [1.020, 1.140], [
        ("before", .90, 1.020),
        ("session", 1.030, 1.130),
        ("tokenizer", 1.150, 1.240),
    ])
    assert report["callbacks"] == 2
    assert report["elapsed_ms"] == 220
    assert report["max_callback_interval_ms"] == 120
    assert report["long_gaps"] == [
        {"offset_ms": 20, "duration_ms": 120,
         "overlaps": [{"name": "session", "overlap_ms": 100}]},
        {"offset_ms": 140, "duration_ms": 80,
         "overlaps": [{"name": "tokenizer", "overlap_ms": 70}]},
    ]


def test_no_callback_is_not_evidence_of_responsiveness():
    report = summarize(1.0, 1.125, [], [])
    assert report["callbacks"] == 0
    assert report["p95_callback_interval_ms"] is None
    assert report["max_callback_interval_ms"] == 125
