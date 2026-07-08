"""Tests for TMDb discovery slicing and merge strategy."""

from candidates.sources.tmdb.discovery_strategy import build_discovery_slices, merge_discovery_results


def test_build_discovery_slices_for_ru_includes_origin_language_year_and_genres() -> None:
    slices = build_discovery_slices(
        "RU",
        year_min=2020,
        year_max=2024,
        with_genres="18,80",
        without_genres="16",
        pages_per_slice=2,
    )

    assert len(slices) == 8
    queries = [item["query"] for item in slices]
    assert any(query.get("with_origin_country") == "RU" for query in queries)
    assert any(query.get("with_original_language") == "ru" for query in queries)
    assert {query.get("sort_by") for query in queries} == {"vote_count.desc", "popularity.desc"}
    assert {query.get("with_genres") for query in queries} == {"18", "80"}
    assert all(query.get("without_genres") == "16" for query in queries)
    assert all(query.get("max_pages") == 2 for query in queries)
    assert all(query.get("first_air_date.gte") == "2020-01-01" for query in queries)
    assert all(query.get("first_air_date.lte") == "2024-12-31" for query in queries)


def test_build_discovery_slices_for_other_country_uses_origin_country_only() -> None:
    slices = build_discovery_slices("US", year_min=2020, year_max=2027)

    assert len(slices) == 4
    assert all(item["query"].get("with_origin_country") == "US" for item in slices)
    assert all("with_original_language" not in item["query"] for item in slices)
    assert {
        (item["query"].get("first_air_date.gte"), item["query"].get("first_air_date.lte"))
        for item in slices
    } == {
        ("2020-01-01", "2024-12-31"),
        ("2025-01-01", "2027-12-31"),
    }


def test_build_discovery_slices_for_movie_uses_primary_release_dates() -> None:
    slices = build_discovery_slices("US", year_min=2009, year_max=2009, media_type="movie")

    queries = [item["query"] for item in slices]
    assert all(query.get("primary_release_date.gte") == "2009-01-01" for query in queries)
    assert all(query.get("primary_release_date.lte") == "2009-12-31" for query in queries)
    assert all("first_air_date.gte" not in query for query in queries)
    assert all("first_air_date.lte" not in query for query in queries)


def test_merge_discovery_results_dedupes_and_combines_trace() -> None:
    results = [
        {
            "slice_name": "origin_votes",
            "query": {"sort_by": "vote_count.desc"},
            "page": 1,
            "results": [
                {"id": 10, "name": "Show", "vote_count": 100, "popularity": 5.0},
                {"id": 20, "name": "Other", "vote_count": 50, "popularity": 9.0},
            ],
        },
        {
            "slice_name": "origin_popularity",
            "query": {"sort_by": "popularity.desc"},
            "page": 1,
            "results": [
                {"id": 10, "name": "Show", "vote_count": 90, "popularity": 50.0},
            ],
        },
        {
            "slice_name": "language_votes",
            "query": {"with_original_language": "ru", "sort_by": "vote_count.desc"},
            "page": 2,
            "results": [
                {"id": 10, "name": "Show", "vote_count": 120, "popularity": 4.0},
            ],
        },
    ]

    merged = merge_discovery_results(results)

    assert [item["id"] for item in merged] == [10, 20]
    show = merged[0]
    assert show["vote_count"] == 120
    assert show["popularity"] == 4.0
    assert len(show["source_trace"]) == 3
    assert [trace["slice_name"] for trace in show["source_trace"]] == [
        "origin_votes",
        "origin_popularity",
        "language_votes",
    ]
    assert show["source_trace"][0]["original_order"] == 0
    assert show["source_trace"][2]["page"] == 2


def test_merge_discovery_results_accepts_mapping_input() -> None:
    merged = merge_discovery_results({
        "a": {
            "slice_name": "a",
            "query": {"sort_by": "vote_count.desc"},
            "page": 1,
            "results": [{"tmdb_id": 1, "vote_count": 1, "popularity": 1.0}],
        },
        "b": {
            "slice_name": "b",
            "query": {"sort_by": "popularity.desc"},
            "page": 1,
            "results": [{"id": 1, "vote_count": 2, "popularity": 1.0}],
        },
    })

    assert len(merged) == 1
    assert merged[0]["id"] == 1
    assert len(merged[0]["source_trace"]) == 2
