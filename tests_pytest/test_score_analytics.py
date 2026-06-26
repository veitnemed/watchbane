from dataset.score_analytics import (
    build_dense_score_rows,
    build_dataset_completeness,
    build_dataset_completeness_from_entries,
    build_score_analytics,
    build_score_count_points,
    build_score_distribution,
    build_score_distribution_chart_rows,
    build_score_insights,
    build_score_summary,
    collect_user_scores,
    summarize_dataset_completeness,
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


def test_score_distribution_chart_rows_counts_and_percent() -> None:
    rows = build_score_distribution_chart_rows(
        {
            "A": _movie(5.5, "A"),
            "B": _movie(6.2, "B"),
            "C": _movie(7.4, "C"),
            "D": _movie(8.1, "D"),
            "E": _movie(9.9, "E"),
            "F": _movie(10.0, "F"),
        }
    )

    assert [(row["label"], row["count"], row["percent"]) for row in rows] == [
        ("ниже 6.0", 1, 16.7),
        ("6.0-6.9", 1, 16.7),
        ("7.0-7.9", 1, 16.7),
        ("8.0-8.9", 1, 16.7),
        ("9.0-9.9", 1, 16.7),
        ("10.0", 1, 16.7),
    ]


def test_score_distribution_chart_rows_limits_hover_examples() -> None:
    rows = build_score_distribution_chart_rows(
        {
            f"T{index}": _movie(7.2, f"Title {index}")
            for index in range(1, 8)
        }
    )

    target = next(row for row in rows if row["label"] == "7.0-7.9")

    assert target["count"] == 7
    assert target["example_titles"] == ["Title 1", "Title 2", "Title 3", "Title 4", "Title 5"]
    assert target["extra_count"] == 2


def test_score_distribution_chart_rows_empty_and_missing_scores() -> None:
    rows = build_score_distribution_chart_rows(
        {
            "A": _movie(None, "A"),
            "B": {"main_info": {"title": "B"}},
            "C": _movie("bad", "C"),
        }
    )

    assert sum(row["count"] for row in rows) == 0
    assert all(row["percent"] == 0.0 for row in rows)
    assert all(row["example_titles"] == [] for row in rows)


def test_score_count_points_group_exact_scores() -> None:
    points = build_score_count_points(
        [
            {"score": 8.0, "title": "A"},
            {"score": 8.04, "title": "B"},
            {"score": 8.5, "title": "C"},
            {"score": 8.5, "title": "D"},
            {"score": 9.0, "title": "E"},
        ]
    )

    assert points == [
        {"score": 8.0, "count": 2, "example_titles": ["A", "B"], "extra_count": 0},
        {"score": 8.5, "count": 2, "example_titles": ["C", "D"], "extra_count": 0},
        {"score": 9.0, "count": 1, "example_titles": ["E"], "extra_count": 0},
    ]


def test_score_count_points_limits_examples() -> None:
    points = build_score_count_points(
        [{"score": 7.5, "title": f"Title {index}"} for index in range(1, 8)],
        title_limit=5,
    )

    assert points[0]["example_titles"] == ["Title 1", "Title 2", "Title 3", "Title 4", "Title 5"]
    assert points[0]["extra_count"] == 2


def test_score_count_points_empty_and_invalid() -> None:
    assert build_score_count_points([None, {"score": None}, {"score": "bad"}]) == []


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
    assert analytics["score_count_points"] == [
        {"score": 8.0, "count": 1, "example_titles": ["Alpha"], "extra_count": 0},
        {"score": 9.0, "count": 1, "example_titles": ["Bravo"], "extra_count": 0},
    ]
    assert analytics["dense_scores"][0]["titles"] == ["Bravo"]
    assert len(analytics["insights"]) == 3
    assert analytics["dataset_completeness"]["total"] == 2


def _full_card(**overrides) -> dict:
    card = {
        "user_score": 8.0,
        "year": 2020,
        "genres": ["Драма"],
        "imdb_score": 7.5,
        "kp_score": 7.0,
        "overview": "Описание фильма.",
        "poster_url": "https://example.com/poster.jpg",
        "poster_path": None,
        "poster_src": "https://example.com/poster.jpg",
    }
    card.update(overrides)
    return card


def test_dataset_completeness_empty() -> None:
    result = build_dataset_completeness({})

    assert result["total"] == 0
    assert result["overall_percent"] == 0.0
    assert len(result["items"]) == 7
    assert all(item["count"] == 0 for item in result["items"])
    assert all(item["percent"] == 0.0 for item in result["items"])


def test_dataset_completeness_full_entries() -> None:
    movie = _movie(8.0, "Alpha")
    result = build_dataset_completeness_from_entries([("Alpha", movie, _full_card())])

    assert result["total"] == 1
    assert result["overall_percent"] == 100.0
    assert all(item["percent"] == 100.0 for item in result["items"])


def test_dataset_completeness_partial_entries() -> None:
    movie = _movie(8.0, "Alpha")
    entries = [
        ("A", movie, _full_card()),
        ("B", movie, _full_card(poster_url=None, poster_path=None, poster_src=None)),
        ("C", movie, _full_card(overview="")),
        ("D", movie, _full_card(imdb_score=None)),
        ("E", movie, _full_card(kp_score=None)),
        ("F", movie, _full_card(genres=[])),
        ("G", movie, _full_card(year=None)),
    ]
    result = build_dataset_completeness_from_entries(entries)

    assert result["total"] == 7
    by_key = {item["key"]: item for item in result["items"]}
    assert by_key["poster"]["count"] == 6
    assert by_key["description"]["count"] == 6
    assert by_key["imdb"]["count"] == 6
    assert by_key["kp"]["count"] == 6
    assert by_key["genres"]["count"] == 6
    assert by_key["year"]["count"] == 6
    assert by_key["user_score"]["count"] == 7


def test_dataset_completeness_reads_raw_scores_without_card_fields() -> None:
    movie = {
        "main_info": {"title": "Alpha", "user_score": 8.0, "year": 2020},
        "raw_scores": {"imdb_score": 7.8, "kp_score": 6.9},
        "genres": ["Драма"],
        "overview": "Есть описание.",
        "poster_url": "https://example.com/a.jpg",
    }
    result = build_dataset_completeness_from_entries([("Alpha", movie, {})])

    by_key = {item["key"]: item for item in result["items"]}
    assert by_key["imdb"]["count"] == 1
    assert by_key["kp"]["count"] == 1
    assert by_key["description"]["count"] == 1
    assert by_key["poster"]["count"] == 1


def test_summarize_dataset_completeness_ok() -> None:
    movie = _movie(8.0, "Alpha")
    completeness = build_dataset_completeness_from_entries([("Alpha", movie, _full_card())])
    summary = summarize_dataset_completeness(completeness)

    assert summary["is_ok"] is True
    assert summary["issues"] == []
    assert summary["status_text"] == "Dataset заполнен полностью"


def test_summarize_dataset_completeness_with_issues() -> None:
    movie = _movie(8.0, "Alpha")
    completeness = build_dataset_completeness_from_entries(
        [("Alpha", movie, _full_card(kp_score=None))]
    )
    summary = summarize_dataset_completeness(completeness)

    assert summary["is_ok"] is False
    assert any(item["key"] == "kp" for item in summary["issues"])
    assert summary["status_text"].startswith("Полнота dataset —")


def test_summarize_dataset_completeness_empty() -> None:
    summary = summarize_dataset_completeness(build_dataset_completeness({}))

    assert summary["is_ok"] is False
    assert summary["status_text"] == "Нет записей в watched-базе"
