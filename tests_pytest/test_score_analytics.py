from dataset.score_analytics import (
    build_dense_score_rows,
    build_score_analytics,
    build_score_distribution,
    build_score_insights,
    build_score_summary,
    collect_user_scores,
)


def _movie(score, title: str = "Title"):
    return {"main_info": {"title": title, "user_score": score}}


def test_score_summary() -> None:
    summary = build_score_summary([6.0, 7.0, 9.0, 10.0])

    assert summary == {
        "count": 4,
        "average": 8.0,
        "median": 8.0,
        "minimum": 6.0,
        "maximum": 10.0,
    }


def test_score_summary_empty() -> None:
    summary = build_score_summary([])

    assert summary == {
        "count": 0,
        "average": None,
        "median": None,
        "minimum": None,
        "maximum": None,
    }


def test_score_distribution_buckets() -> None:
    distribution = build_score_distribution([10.0, 9.5, 8.0, 7.7, 6.1, 5.9])

    assert [(item["label"], item["count"]) for item in distribution] == [
        ("10.0", 1),
        ("9.0-9.9", 1),
        ("8.0-8.9", 1),
        ("7.0-7.9", 1),
        ("6.0-6.9", 1),
        ("ниже 6.0", 1),
    ]
    assert all(item["percent"] == 16.7 for item in distribution)


def test_collect_user_scores_ignores_missing_and_invalid() -> None:
    data = {
        "A": _movie(8.25),
        "B": _movie(None),
        "C": {"main_info": {}},
        "D": _movie("bad"),
        "E": _movie(11),
        "F": _movie(7),
    }

    assert collect_user_scores(data) == [8.3, 7.0]


def test_dense_score_rows() -> None:
    rows = build_dense_score_rows(
        [
            {"score": 8.0, "title": "A"},
            {"score": 8.04, "title": "B"},
            {"score": 8.5, "title": "C"},
            {"score": 8.5, "title": "D"},
            {"score": 8.5, "title": "E"},
            {"score": 9.0, "title": "F"},
        ]
    )

    assert rows[:2] == [
        {"score": 8.5, "count": 3, "titles": ["C", "D", "E"], "extra_count": 0},
        {"score": 8.0, "count": 2, "titles": ["A", "B"], "extra_count": 0},
    ]


def test_dense_score_rows_limits_titles() -> None:
    rows = build_dense_score_rows(
        [
            {"score": 7.5, "title": "A"},
            {"score": 7.5, "title": "B"},
            {"score": 7.5, "title": "C"},
        ],
        title_limit=2,
    )

    assert rows[0]["titles"] == ["A", "B"]
    assert rows[0]["extra_count"] == 1


def test_score_insights() -> None:
    distribution = build_score_distribution([8.0, 8.5, 7.5, 5.0])
    dense_scores = build_dense_score_rows([8.0, 8.0, 7.5])
    summary = build_score_summary([8.0, 8.5, 7.5, 5.0])

    insights = build_score_insights(summary, distribution, dense_scores)

    assert insights[0].startswith("Больше всего оценок")
    assert "Самая частая одинаковая оценка: 8.0" in insights[1]
    assert insights[2] == "Очень высоких оценок 9.0+ сейчас: 0."


def test_score_insights_empty() -> None:
    assert build_score_insights(build_score_summary([]), build_score_distribution([]), []) == [
        "Пока нет оценок для аналитики."
    ]


def test_build_score_analytics() -> None:
    analytics = build_score_analytics({"A": _movie(8.0, "Alpha"), "B": _movie(9.0, "Bravo")})

    assert analytics["scores"] == [8.0, 9.0]
    assert analytics["summary"]["median"] == 8.5
    assert analytics["distribution"][1]["count"] == 1
    assert analytics["dense_scores"][0]["titles"] == ["Bravo"]
    assert len(analytics["insights"]) == 3
