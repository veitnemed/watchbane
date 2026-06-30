from app.core.explain import explain_candidate
from app.core.filters import candidate_matches, filter_candidates
from app.core.ranking import calculate_quality_score, rank_candidates
from candidates.keys import title_identity_key


def _candidate(**overrides):
    base = {
        "title": "Метод",
        "year": 2015,
        "countries": ["Россия"],
        "genres": ["драма", "детектив"],
        "kp_score": 8.1,
        "kp_votes": 12000,
        "imdb_score": 7.3,
        "imdb_votes": 2500,
        "is_complete": True,
    }
    base.update(overrides)
    return base


def test_candidate_matches_search_criteria() -> None:
    criteria = {
        "country": "Россия",
        "year_min": 2010,
        "year_max": 2020,
        "include_genres": ["Драма"],
        "exclude_genres": ["Комедия"],
        "min_kp_score": 7.0,
        "min_kp_votes": 1000,
        "min_imdb_score": 7.0,
        "min_imdb_votes": 1000,
        "only_complete": True,
    }

    assert candidate_matches(_candidate(), criteria) is True
    assert candidate_matches(_candidate(genres=["комедия"]), criteria) is False
    assert candidate_matches(_candidate(kp_score=6.9), criteria) is False


def test_candidate_matches_skips_watched_and_hidden() -> None:
    candidate = _candidate()
    identity = title_identity_key(candidate)

    assert candidate_matches(candidate, {"watched_identities": {identity}}) is False
    assert candidate_matches(candidate, {"hidden_identities": {identity}}) is False
    assert candidate_matches(candidate, {"watched_identities": {identity}, "only_unwatched": False}) is True
    assert filter_candidates([candidate], {"hidden_identities": set()})[0]["title"] == "Метод"


def test_quality_score_prefers_reliable_kp_and_votes() -> None:
    reliable = _candidate(title="Надёжный", kp_score=8.0, kp_votes=20000, imdb_score=7.0, imdb_votes=200)
    noisy_imdb = _candidate(title="Шумный", kp_score=7.0, kp_votes=500, imdb_score=9.8, imdb_votes=50)

    assert calculate_quality_score(reliable) > calculate_quality_score(noisy_imdb)
    assert rank_candidates([noisy_imdb, reliable])[0]["title"] == "Надёжный"


def test_explain_candidate_returns_search_reasons() -> None:
    reasons = explain_candidate(
        _candidate(),
        {
            "country": "Россия",
            "year_min": 2010,
            "include_genres": ["Драма"],
            "only_unwatched": True,
            "hide_hidden": True,
            "only_complete": True,
        },
    )

    text = "\n".join(reasons)
    assert "Оценка качества" in text
    assert "Высокий KP" in text
    assert "IMDb учтён" in text
    assert "Подходит по жанрам" in text
    assert "Не просмотрен" in text
    assert "Не скрыт" in text


def test_sort_search_candidates_orders_by_kp_score() -> None:
    from candidates import service

    candidates = [
        {"title": "Low", "year": 2020, "kp_score": 6.0, "imdb_score": 8.0},
        {"title": "High", "year": 2021, "kp_score": 9.0, "imdb_score": 7.0},
    ]
    result = service.sort_search_candidates(candidates, "kp_score")
    assert result["candidates"][0]["title"] == "High"
    assert result["sort_mode"] == "kp_score"


def test_sort_search_candidates_puts_missing_values_last() -> None:
    from candidates import service

    candidates = [
        {"title": "Missing", "year": 2020},
        {"title": "Rated", "year": 2021, "imdb_score": 7.5},
    ]
    result = service.sort_search_candidates(candidates, "imdb_score")
    assert result["candidates"][0]["title"] == "Rated"
    assert result["candidates"][-1]["title"] == "Missing"


def test_candidate_service_exposes_search_named_views(monkeypatch) -> None:
    from candidates import service

    monkeypatch.setattr(service.candidate_pool, "get_pool_stats", lambda criteria_name=None: {"storage_total": 1})
    monkeypatch.setattr(service.candidate_pool, "format_pool_stats_lines", lambda stats: ["В pool: 1"])
    monkeypatch.setattr(service.candidate_pool, "format_pool_stats_summary", lambda stats: "В pool: 1")
    monkeypatch.setattr(service, "get_pool_view", lambda criteria_name=None: [_candidate()])
    monkeypatch.setattr(service.candidate_pool, "load_candidate_criteria", lambda: {})

    overview = service.get_search_overview_view()
    assert overview["is_empty"] is False
    assert overview["candidates"][0]["title"] == "Метод"

    filter_view = service.get_search_filter_view([_candidate(), _candidate(title="Комедия", genres=["комедия"])], {
        "include_genres": ["Драма"],
    })
    assert filter_view["filtered_count"] == 1
    assert filter_view["candidates"][0]["title"] == "Метод"

    ranking_view = service.rank_search_candidates([_candidate(title="A", kp_score=7.0), _candidate(title="B", kp_score=8.5)])
    assert ranking_view["candidates"][0]["title"] == "B"


def test_search_menu_uses_search_named_service_api() -> None:
    import inspect

    from ui.console import search_menu

    source = inspect.getsource(search_menu.show_global_candidate_search)
    assert "get_search_overview_view" in source
    assert "rank_search_candidates" in source
    assert "top_prediction" not in source


def test_console_add_flow_uses_add_named_helpers() -> None:
    import inspect

    from ui.console import request, title_presenters

    request_source = inspect.getsource(request)
    presenters_source = inspect.getsource(title_presenters)

    assert hasattr(request, "resolve_title_for_add")
    assert hasattr(request, "confirm_or_edit_dataset_genres")
    assert hasattr(title_presenters, "print_sql_add_preview")
    assert hasattr(title_presenters, "print_api_add_preview")
    assert hasattr(title_presenters, "print_final_add_preview")

    assert "resolve_title_for_training" not in request_source
    assert "request_predict_features" not in request_source
    assert "confirm_or_edit_model_genres" not in request_source
    assert "print_sql_training_preview" not in presenters_source
    assert "print_api_training_preview" not in presenters_source
    assert "print_final_training_preview" not in presenters_source


def test_classify_candidate_poster_state_displayable_local_file(monkeypatch) -> None:
    from pathlib import Path

    from candidates import candidate_pool

    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: str(self).endswith("poster.jpg"),
    )

    state = candidate_pool.classify_candidate_poster_state(
        {
            "title": "Local Show",
            "poster_path": "/cache/posters/poster.jpg",
        }
    )
    assert state["display_state"] == "displayable"
    assert str(state["local_path"]).endswith("poster.jpg")


def test_classify_candidate_poster_state_metadata_only_without_file() -> None:
    from candidates import candidate_pool

    state = candidate_pool.classify_candidate_poster_state(
        {
            "title": "Remote Show",
            "poster_url": "https://example.com/poster.jpg",
        }
    )
    assert state["display_state"] == "metadata_only"
    assert state["local_path"] is None


def test_build_candidate_poster_diagnostics_summarizes_counts(monkeypatch) -> None:
    from pathlib import Path

    from candidates import candidate_pool

    monkeypatch.setattr(
        Path,
        "is_file",
        lambda self: str(self).endswith("ok.jpg"),
    )
    candidates = [
        {"title": "With file", "poster_path": "/cache/posters/ok.jpg"},
        {"title": "Url only", "poster_url": "https://example.com/poster.jpg"},
        {"title": "No poster"},
    ]

    diagnostics = candidate_pool.build_candidate_poster_diagnostics(candidates)

    assert diagnostics["total"] == 3
    assert diagnostics["counts"]["displayable"] == 1
    assert diagnostics["counts"]["metadata_only"] == 1
    assert diagnostics["counts"]["missing"] == 1
    assert len(diagnostics["problem_rows"]) == 2


def test_get_candidate_poster_diagnostics_view_uses_service_facade(monkeypatch) -> None:
    from candidates import service

    monkeypatch.setattr(
        service,
        "get_search_overview_view",
        lambda: {
            "is_empty": False,
            "candidates": [
                {"title": "A", "poster_url": "https://example.com/a.jpg"},
                {"title": "B"},
            ],
        },
    )

    view = service.get_candidate_poster_diagnostics_view()
    assert view["is_empty_pool"] is False
    assert view["total"] == 2
    assert view["counts"]["metadata_only"] + view["counts"]["missing"] == 1


def test_collect_unique_pool_poster_urls_deduplicates() -> None:
    from candidates import candidate_pool

    candidates = [
        {"title": "A", "poster_url": "https://example.com/one.jpg"},
        {"title": "B", "poster_url": "https://example.com/one.jpg"},
        {"title": "C", "poster_url": "https://example.com/two.jpg"},
        {"title": "D"},
    ]

    urls = candidate_pool.collect_unique_pool_poster_urls(candidates)

    assert urls == [
        "https://example.com/one.jpg",
        "https://example.com/two.jpg",
    ]


def test_download_preview_posters_for_urls(monkeypatch) -> None:
    import tempfile
    from pathlib import Path

    from posters import download_images

    with tempfile.TemporaryDirectory() as temp_root:
        preview_dir = Path(temp_root) / "preview"
        monkeypatch.setattr(download_images, "PREVIEW_POSTER_DIR", preview_dir)

        calls: list[str] = []

        def fake_preview(source_url: str, destination) -> tuple[bool, str]:
            calls.append(source_url)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"jpg")
            return True, "downloaded"

        monkeypatch.setattr(download_images, "_download_preview_poster", fake_preview)
        monkeypatch.setattr(download_images.time, "sleep", lambda *_args, **_kwargs: None)

        stats = download_images.download_preview_posters_for_urls(
            [
                "https://image.tmdb.org/t/p/original/a.jpg",
                "https://image.tmdb.org/t/p/original/a.jpg",
                "https://example.com/b.jpg",
                "",
            ]
        )

        assert stats["total_urls"] == 4
        assert stats["downloaded"] == 2
        assert stats["skipped_existing"] == 1
        assert stats["skipped_invalid"] == 1
        assert calls == [
            "https://image.tmdb.org/t/p/original/a.jpg",
            "https://example.com/b.jpg",
        ]


def test_normalize_tmdb_poster_download_url_uses_w500() -> None:
    from posters.download_images import normalize_tmdb_poster_download_url

    original = "https://image.tmdb.org/t/p/original/feVQc6vtTdOsrt8W4XXNBviRs71.jpg"
    assert normalize_tmdb_poster_download_url(original) == (
        "https://image.tmdb.org/t/p/w500/feVQc6vtTdOsrt8W4XXNBviRs71.jpg"
    )
    assert normalize_tmdb_poster_download_url("https://example.com/x.jpg") == "https://example.com/x.jpg"


def test_build_poster_request_headers_for_tmdb() -> None:
    from posters.download_images import build_poster_request_headers

    headers = build_poster_request_headers("https://image.tmdb.org/t/p/w500/foo.jpg")
    assert "Referer" in headers
    assert "Mozilla" in headers["User-Agent"]
    assert headers["Connection"] == "close"


def test_format_download_error_maps_ssl_and_http() -> None:
    from urllib.error import HTTPError, URLError

    from posters.download_images import _format_download_error

    assert _format_download_error(HTTPError("https://x", 403, "Forbidden", hdrs=None, fp=None)) == "http_403"
    assert _format_download_error(URLError("timed out")) == "network_timeout"
    assert _format_download_error(URLError("[SSL: UNEXPECTED_EOF_WHILE_READING]")) == "network_ssl"


def test_is_retryable_download_reason_includes_403() -> None:
    from posters.download_images import _is_retryable_download_reason

    assert _is_retryable_download_reason("http_403") is True
    assert _is_retryable_download_reason("network_ssl") is True
    assert _is_retryable_download_reason("http_404") is False


def test_download_preview_posters_for_urls_reports_failures(monkeypatch) -> None:
    import tempfile
    from pathlib import Path

    from posters import download_images

    with tempfile.TemporaryDirectory() as temp_root:
        preview_dir = Path(temp_root) / "preview"
        monkeypatch.setattr(download_images, "PREVIEW_POSTER_DIR", preview_dir)
        monkeypatch.setattr(
            download_images,
            "_download_preview_poster",
            lambda _url, _dest: (False, "http_429"),
        )
        monkeypatch.setattr(download_images.time, "sleep", lambda *_args, **_kwargs: None)

        errors: list[tuple[str, str]] = []

        stats = download_images.download_preview_posters_for_urls(
            ["https://image.tmdb.org/t/p/original/a.jpg"],
            error_callback=lambda url, reason: errors.append((url, reason)),
        )

        assert stats["failed"] == 1
        assert stats["failures"] == [
            {"url": "https://image.tmdb.org/t/p/original/a.jpg", "reason": "http_429"},
        ]
        assert errors == [("https://image.tmdb.org/t/p/original/a.jpg", "http_429")]


def test_download_candidate_pool_preview_posters_service(monkeypatch) -> None:
    from candidates import service

    monkeypatch.setattr(
        service,
        "get_search_overview_view",
        lambda: {
            "is_empty": False,
            "candidates": [
                {"title": "A", "poster_url": "https://example.com/a.jpg"},
            ],
        },
    )
    monkeypatch.setattr(
        "posters.download_images.download_preview_posters_for_urls",
        lambda urls, progress_callback=None, error_callback=None: {
            "total_urls": len(urls),
            "downloaded": 1,
            "skipped_existing": 0,
            "failed": 0,
            "skipped_invalid": 0,
            "failures": [],
        },
    )

    result = service.download_candidate_pool_preview_posters()
    assert result["ok"] is True
    assert result["pool_total"] == 1
    assert result["unique_urls"] == 1
    assert result["downloaded"] == 1


def test_deduplicate_pool_keeps_best_record() -> None:
    from candidates import candidate_pool

    pool = {
        "show|2018": {"title": "Show", "year": 2018, "kp_score": 7.0},
        "other|2018": {"title": "Show", "year": 2018, "kp_score": 8.5},
    }
    deduped = candidate_pool.deduplicate_pool(pool)
    assert len(deduped) == 1
    assert list(deduped.values())[0]["kp_score"] == 8.5


def test_dedupe_pool_by_similar_titles_merges_same_show() -> None:
    from candidates import candidate_pool

    pool = {
        "a|2015": {"title": "Метод", "year": 2015, "kp_score": 8.0},
        "b|2015": {"title": "метод", "year": 2015, "kp_score": 6.0},
    }
    deduped, removed = candidate_pool.dedupe_pool_by_similar_titles(pool)
    assert len(deduped) == 1
    assert removed == 1
    assert list(deduped.values())[0]["kp_score"] == 8.0


def test_format_pool_stats_summary_shows_unique_and_duplicates() -> None:
    from candidates import candidate_pool

    stats = {
        "unique_total": 10,
        "storage_total": 10,
        "ready_total": 8,
        "incomplete_total": 2,
        "raw_total": 14,
        "duplicate_entries": 4,
        "similar_duplicate_total": 1,
    }
    summary = candidate_pool.format_pool_stats_summary(stats)
    assert "уникальных: 10" in summary
    assert "+4 дублей" in summary
    assert "похожих: 1" in summary


def test_clean_common_pool_duplicates_writes_normalized_pool(monkeypatch) -> None:
    from candidates import candidate_pool

    raw_pool = {
        "legacy|show|2018": {"title": "Show", "year": 2018, "kp_score": 7.0},
        "show|2018": {"title": "Show", "year": 2018, "kp_score": 8.5},
    }
    saved = {}

    monkeypatch.setattr(candidate_pool, "load_candidate_pool", lambda: dict(raw_pool))
    monkeypatch.setattr(candidate_pool, "save_candidate_pool", lambda pool: saved.update({"pool": pool}))

    result = candidate_pool.clean_common_pool_duplicates()
    assert result["removed_exact"] == 1
    assert result["unique_total"] == 1
    assert len(saved["pool"]) == 1
    assert list(saved["pool"].values())[0]["kp_score"] == 8.5


def test_resolve_canonical_year_prefers_imdb_start_year() -> None:
    from candidates.schema import resolve_canonical_year

    candidate = {"imdb_start_year": 2016, "year": 2015}
    assert resolve_canonical_year(candidate) == 2016


def test_find_cross_year_title_groups_groups_different_years() -> None:
    from candidates import candidate_pool

    candidates = [
        {"title": "Show Name", "year": 2015},
        {"title": "Show Name", "year": 2016},
    ]
    groups = candidate_pool.find_cross_year_title_groups(candidates)
    assert len(groups) == 1
    assert groups[0]["years"] == [2015, 2016]


def test_find_title_duplicate_groups_counts_extra_entries() -> None:
    from candidates import candidate_pool

    candidates = [
        {"title": "Show Name", "year": 2015},
        {"title": "Show Name", "year": 2016},
        {"title": "Show Name", "year": 2016, "kp_score": 8.0},
        {"title": "Other", "year": 2020},
    ]
    groups = candidate_pool.find_title_duplicate_groups(candidates, include_dataset=False)
    summary = candidate_pool.build_title_duplicate_summary(groups)
    assert len(groups) == 1
    assert groups[0]["entry_count"] == 3
    assert summary["group_count"] == 1
    assert summary["extra_entries"] == 2


def test_find_title_duplicate_groups_includes_dataset_matches() -> None:
    from candidates import candidate_pool

    candidates = [{"title": "Show Name", "year": 2015}]
    dataset_index = {
        "show name": [
            {"dataset_key": "Show Name", "title": "Show Name", "year": 2015},
        ],
    }
    groups = candidate_pool.find_title_duplicate_groups(
        candidates,
        include_dataset=True,
        dataset_by_title_key=dataset_index,
    )
    summary = candidate_pool.build_title_duplicate_summary(groups)
    assert len(groups) == 1
    assert groups[0]["entry_count"] == 1
    assert groups[0]["dataset_count"] == 1
    assert summary["dataset_overlap_count"] == 1
    assert summary["group_count"] == 0


def test_get_title_duplicates_view_uses_service_facade(monkeypatch) -> None:
    from candidates import candidate_pool, service

    groups = [{
        "title": "Show",
        "entry_count": 2,
        "extra_entries": 1,
        "dataset_count": 1,
        "in_dataset": True,
        "years": [2015, 2016],
        "entries": [],
        "dataset_entries": [{"dataset_key": "Show", "title": "Show", "year": 2015}],
    }]
    monkeypatch.setattr(candidate_pool, "find_title_duplicate_groups", lambda: groups)
    monkeypatch.setattr(
        candidate_pool,
        "build_title_duplicate_summary",
        lambda _groups: {
            "group_count": 1,
            "extra_entries": 1,
            "reported_groups": 1,
            "dataset_overlap_count": 1,
        },
    )

    view = service.get_title_duplicates_view()
    assert view["group_count"] == 1
    assert view["extra_entries"] == 1
    assert view["dataset_overlap_count"] == 1
    assert view["is_empty"] is False


def test_dedupe_pool_cross_year_titles_merges_within_one_year() -> None:
    from candidates import candidate_pool

    pool = {
        "show|2015": {"title": "Show", "year": 2015, "kp_score": 7.0},
        "show|2016": {"title": "Show", "year": 2016, "imdb_start_year": 2015, "kp_score": 8.0},
    }
    deduped, removed = candidate_pool.dedupe_pool_cross_year_titles(pool)
    assert removed == 1
    assert len(deduped) == 1
    entry = list(deduped.values())[0]
    assert entry["year"] == 2015
    assert entry["kp_score"] == 8.0


def test_dedupe_pool_cross_year_titles_skips_conflicting_imdb_ids() -> None:
    from candidates import candidate_pool

    pool = {
        "show|2015": {"title": "Show", "year": 2015, "imdb_id": "tt111"},
        "show|2016": {"title": "Show", "year": 2016, "imdb_id": "tt222"},
    }
    deduped, removed = candidate_pool.dedupe_pool_cross_year_titles(pool)
    assert removed == 0
    assert len(deduped) == 2


def test_clean_common_pool_duplicates_merges_cross_year(monkeypatch) -> None:
    from candidates import candidate_pool

    raw_pool = {
        "show|2015": {"title": "Show", "year": 2015, "kp_score": 7.0, "tmdb_id": "1"},
        "show|2016": {"title": "Show", "year": 2016, "kp_score": 8.0, "imdb_id": "tt999"},
    }
    saved = {}

    monkeypatch.setattr(candidate_pool, "load_candidate_pool", lambda: dict(raw_pool))
    monkeypatch.setattr(candidate_pool, "save_candidate_pool", lambda pool: saved.update({"pool": pool}))

    result = candidate_pool.clean_common_pool_duplicates()
    assert result["removed_cross_year"] == 1
    assert result["unique_total"] == 1
    assert len(saved["pool"]) == 1
    merged = list(saved["pool"].values())[0]
    assert merged["kp_score"] == 8.0
    assert merged["tmdb_id"] == "1"
    assert merged["imdb_id"] == "tt999"


def test_is_dataset_title_match_ignores_year() -> None:
    from candidates import candidate_pool

    dataset_keys = {"бывшие"}
    candidate = {"title": "Бывшие", "year": 2018}
    assert candidate_pool.is_dataset_title_match(candidate, dataset_keys) is True


def test_purge_dataset_title_matches_from_pool(monkeypatch) -> None:
    from candidates import candidate_pool

    raw_pool = {
        "byvshie|2018": {"title": "Бывшие", "year": 2018},
        "other|2020": {"title": "Other", "year": 2020},
    }
    saved = {}

    monkeypatch.setattr(candidate_pool, "load_candidate_pool", lambda: dict(raw_pool))
    monkeypatch.setattr(
        candidate_pool,
        "build_dataset_title_keys",
        lambda: {"бывшие"},
    )
    monkeypatch.setattr(candidate_pool, "save_candidate_pool", lambda pool: saved.update({"pool": pool}))

    result = candidate_pool.purge_dataset_title_matches_from_pool()
    assert result["removed_dataset_title_matches"] == 1
    assert result["unique_total"] == 1
    assert len(saved["pool"]) == 1
    assert list(saved["pool"].values())[0]["title"] == "Other"
