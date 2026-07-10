"""Build full watched score analytics payload."""

from dataset.analytics.completeness import (
    build_dataset_completeness,
    build_dataset_completeness_from_entries,
)
from dataset.analytics.reports import (
    build_genre_count_rows,
    build_rating_gap_lists,
    build_suspicious_ratings,
    build_tmdb_delta_chart_rows,
    build_year_average_points,
)
from dataset.analytics.scores import (
    build_dense_score_rows,
    build_score_count_points,
    build_score_distribution,
    build_score_distribution_chart_rows,
    build_score_insights,
    build_score_summary,
    collect_score_items,
)


def build_score_analytics(records, entries=None) -> dict:
    """Build all read-only score analytics for watched records."""
    score_items = collect_score_items(records)
    scores = [item["score"] for item in score_items]
    summary = build_score_summary(scores)
    distribution = build_score_distribution(scores)
    chart_distribution = build_score_distribution_chart_rows(records)
    score_count_points = build_score_count_points(score_items)
    dense_scores = build_dense_score_rows(score_items)
    dataset_completeness = (
        build_dataset_completeness_from_entries(entries)
        if entries is not None
        else build_dataset_completeness(records)
    )
    analytics_entries = entries if entries is not None else []
    genre_count_rows = build_genre_count_rows(analytics_entries)
    year_average_points = build_year_average_points(analytics_entries)
    rating_gap_lists = build_rating_gap_lists(analytics_entries)
    tmdb_delta_chart = build_tmdb_delta_chart_rows(analytics_entries)
    suspicious_ratings = build_suspicious_ratings(analytics_entries)
    return {
        "scores": scores,
        "score_items": score_items,
        "summary": summary,
        "distribution": distribution,
        "chart_distribution": chart_distribution,
        "score_count_points": score_count_points,
        "dense_scores": dense_scores,
        "insights": build_score_insights(summary, distribution, dense_scores),
        "dataset_completeness": dataset_completeness,
        "genre_count_rows": genre_count_rows,
        "year_average_points": year_average_points,
        "rating_higher_than_public": rating_gap_lists["higher_than_public"],
        "rating_lower_than_public": rating_gap_lists["lower_than_public"],
        "rating_higher_extra_count": rating_gap_lists["higher_extra_count"],
        "rating_lower_extra_count": rating_gap_lists["lower_extra_count"],
        "tmdb_delta_rows": tmdb_delta_chart["rows"],
        "tmdb_delta_extra_count": tmdb_delta_chart["extra_count"],
        "suspicious_ratings": suspicious_ratings["items"],
        "suspicious_extra_count": suspicious_ratings["extra_count"],
    }
