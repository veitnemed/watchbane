from desktop.analytics.chart_constructor import (
    CHART_FUNCTION,
    SOURCE_CANDIDATE_POOL,
    SOURCE_WATCHED,
    X_USER_SCORE,
    Y_COUNT,
    build_chart_constructor_data,
    build_user_score_distribution,
)


def _entry(title: str, score):
    return (title, {}, {"title": title, "user_score": score})


def test_user_score_distribution_by_count_step_one() -> None:
    rows = build_user_score_distribution(
        [_entry("A", 8.2), _entry("B", 8.9), _entry("C", 10.0)],
        step=1.0,
    )

    by_label = {row["label"]: row for row in rows}
    assert by_label["8"]["count"] == 2
    assert by_label["10"]["count"] == 1
    assert by_label["8"]["percent"] == 66.7


def test_user_score_distribution_empty_dataset() -> None:
    rows = build_user_score_distribution([], step=1.0)

    assert len(rows) == 11
    assert all(row["count"] == 0 for row in rows)
    assert all(row["percent"] == 0.0 for row in rows)


def test_user_score_distribution_fractional_scores() -> None:
    rows = build_user_score_distribution(
        [_entry("A", 8.2), _entry("B", 8.5), _entry("C", 8.9)],
        step=0.5,
    )

    by_label = {row["label"]: row for row in rows}
    assert by_label["8.0"]["count"] == 1
    assert by_label["8.5"]["count"] == 2


def test_chart_constructor_rejects_candidate_pool_user_score() -> None:
    result = build_chart_constructor_data(
        source=SOURCE_CANDIDATE_POOL,
        x_axis=X_USER_SCORE,
        y_axis=Y_COUNT,
        step=1.0,
        watched_entries=[],
    )

    assert result == {
        "ok": False,
        "message": "В candidate pool нет пользовательских оценок",
        "rows": [],
    }


def test_chart_constructor_rejects_candidate_pool_average_user_score() -> None:
    result = build_chart_constructor_data(
        source=SOURCE_CANDIDATE_POOL,
        x_axis="year",
        y_axis="avg_user_score",
        candidate_entries=[{"title": "A", "year": 2024}],
    )

    assert result["ok"] is False
    assert result["message"] == "В candidate pool нет пользовательских оценок"


def test_chart_constructor_builds_watched_user_score_count() -> None:
    result = build_chart_constructor_data(
        source=SOURCE_WATCHED,
        x_axis=X_USER_SCORE,
        y_axis=Y_COUNT,
        step=1.0,
        watched_entries=[_entry("A", 7.1)],
    )

    assert result["ok"] is True
    assert result["rows"][7]["count"] == 1


def test_chart_constructor_builds_candidate_tmdb_votes_distribution() -> None:
    result = build_chart_constructor_data(
        source=SOURCE_CANDIDATE_POOL,
        x_axis="tmdb_votes",
        y_axis=Y_COUNT,
        candidate_entries=[
            {"title": "A", "tmdb_votes": 8},
            {"title": "B", "tmdb_votes": 120},
            {"title": "C", "tmdb_votes": 900},
        ],
    )

    by_label = {row["label"]: row for row in result["rows"]}
    assert result["ok"] is True
    assert by_label["1-9"]["count"] == 1
    assert by_label["100-499"]["count"] == 1
    assert by_label["500-999"]["count"] == 1


def test_chart_constructor_builds_average_tmdb_by_year() -> None:
    result = build_chart_constructor_data(
        source=SOURCE_WATCHED,
        x_axis="year",
        y_axis="avg_tmdb_score",
        watched_entries=[
            ("A", {}, {"title": "A", "year": 2023, "tmdb_score": 8.0}),
            ("B", {}, {"title": "B", "year": 2023, "tmdb_score": 6.0}),
            ("C", {}, {"title": "C", "year": 2024, "tmdb_score": 9.0}),
        ],
    )

    by_label = {row["label"]: row for row in result["rows"]}
    assert by_label["2023"]["value"] == 7.0
    assert by_label["2024"]["value"] == 9.0


def test_chart_constructor_builds_average_final_score_by_country() -> None:
    result = build_chart_constructor_data(
        source=SOURCE_CANDIDATE_POOL,
        x_axis="country",
        y_axis="avg_final_score",
        candidate_entries=[
            {"title": "A", "country": "Россия", "final_score": 0.8},
            {"title": "B", "country": "Россия", "final_score": 60},
            {"title": "C", "country": "США", "final_score": 0.5},
        ],
    )

    by_label = {row["label"]: row for row in result["rows"]}
    assert by_label["Россия"]["value"] == 70.0
    assert by_label["США"]["value"] == 50.0


def test_chart_constructor_counts_multigenre_items() -> None:
    result = build_chart_constructor_data(
        source=SOURCE_CANDIDATE_POOL,
        x_axis="genre",
        y_axis=Y_COUNT,
        candidate_entries=[
            {"title": "A", "genres": ["Драма", "Криминал"]},
            {"title": "B", "genres": ["Драма"]},
        ],
    )

    by_label = {row["label"]: row for row in result["rows"]}
    assert by_label["Драма"]["count"] == 2
    assert by_label["Криминал"]["count"] == 1


def test_chart_constructor_preserves_function_chart_type() -> None:
    result = build_chart_constructor_data(
        source=SOURCE_WATCHED,
        x_axis="year",
        y_axis=Y_COUNT,
        chart_type=CHART_FUNCTION,
        watched_entries=[("A", {}, {"title": "A", "year": 2024})],
    )

    assert result["ok"] is True
    assert result["chart_type"] == CHART_FUNCTION
