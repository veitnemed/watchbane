from candidates.models.keys import title_identity_key


def test_watched_sort_options_are_tmdb_only() -> None:
    from desktop.watched import SORT_OPTIONS

    labels = dict(SORT_OPTIONS)

    assert labels["tmdb_score"] == "TMDb"
    assert labels["tmdb_votes"] == "Голоса TMDb"
    assert labels["tmdb_popularity"] == "Популярность TMDb"
    assert "imdb_score" not in labels
    assert "kp_score" not in labels


def test_watched_sort_entries_supports_tmdb_fields() -> None:
    from desktop.watched import sort_entries

    entries = [
        ("A", {}, {"title": "A", "tmdb_score": 7.0, "tmdb_votes": 100, "tmdb_popularity": 10.0}),
        ("B", {}, {"title": "B", "tmdb_score": 8.2, "tmdb_votes": 50, "tmdb_popularity": 5.0}),
        ("C", {}, {"title": "C", "tmdb_score": 6.0, "tmdb_votes": 900, "tmdb_popularity": 30.0}),
    ]

    assert [entry[0] for entry in sort_entries(entries, "tmdb_score")] == ["B", "A", "C"]
    assert [entry[0] for entry in sort_entries(entries, "tmdb_votes")] == ["C", "A", "B"]
    assert [entry[0] for entry in sort_entries(entries, "tmdb_popularity")] == ["C", "A", "B"]


def test_watched_card_uses_candidate_pool_tmdb_scores_and_final_score() -> None:
    from desktop.watched import build_final_score_star_item, build_score_ring_item
    from web.export import build_export_lookup_cache, build_watched_movie_card

    movie = {
        "main_info": {"title": "Alpha", "year": 2024, "user_score": 8.0},
        "raw_scores": {"kp_score": 9.9, "imdb_score": 9.1},
    }
    candidate = {
        "title": "Alpha",
        "year": 2024,
        "tmdb_score": 8.1,
        "tmdb_votes": 777,
        "tmdb_popularity": 21.0,
        "quality_score": 0.81,
        "final_score": 0.74,
    }
    lookup_cache = build_export_lookup_cache(
        meta={},
        pool_by_identity={title_identity_key(candidate): candidate},
    )

    card = build_watched_movie_card(movie, poster_cache={}, lookup_cache=lookup_cache)
    ring = build_score_ring_item(card)

    assert card["tmdb_score"] == 8.1
    assert card["tmdb_votes"] == 777
    assert card["tmdb_popularity"] == 21.0
    assert card["quality_score"] == 0.81
    assert card["final_score"] == 0.74
    assert "kp_score" not in card
    assert "imdb_score" not in card
    assert ring["display_value"] == "8.1"
    assert ring["display_label"] == "TMDb"
    assert ring["ring_progress"] == 0.81
    assert "footer_label" not in ring
    assert "footer_stars" not in ring
    assert build_final_score_star_item(card)["stars"] == 3.5


def test_delete_preview_lines_are_tmdb_only() -> None:
    from desktop.watched.delete import format_delete_preview_lines

    lines = format_delete_preview_lines(
        {
            "title": "Alpha",
            "year": 2020,
            "user_score": 8.0,
            "tmdb_score": 7.8,
            "kp_score": 7.5,
            "imdb_score": 8.1,
            "has_meta": True,
            "has_poster_cache": False,
        }
    )
    joined = "\n".join(lines)

    assert "TMDb: 7.8" in joined
    assert "КП:" not in joined
    assert "IMDb:" not in joined
