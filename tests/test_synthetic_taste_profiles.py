from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from copy import deepcopy

import pytest

from tools.qa.synthetic_taste_profiles import (
    TasteProfileError,
    build_fixed_synthetic_pool,
    evaluate_vibe_alignment,
    evaluate_profile,
    load_profile,
    resolve_profile,
    validate_profile,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / "tools" / "qa" / "fixtures" / "synthetic_taste_profiles"


def test_builtin_profiles_validate_and_map_to_existing_filter_contract() -> None:
    for path in sorted(PROFILES_DIR.glob("*.json")):
        profile = load_profile(path)
        resolved = resolve_profile(profile)

        filters = resolved["candidate_filters"]
        assert set(filters).issuperset(
            {
                "country",
                "media_type",
                "year_min",
                "year_max",
                "include_genres",
                "exclude_genres",
                "min_tmdb_score",
                "min_tmdb_votes",
            }
        )
        assert set(resolved["recommendation_vector"]) == {
            "openness_level",
            "rarity_level",
            "diversity_level",
            "mood",
        }


def test_profile_rejects_unknown_fields_instead_of_ignoring_them() -> None:
    payload = json.loads((PROFILES_DIR / "P1-mainstream.json").read_text(encoding="utf-8"))
    payload["unexpected"] = "not allowed"

    with pytest.raises(TasteProfileError, match=r"Unknown field\(s\) at profile: unexpected"):
        validate_profile(payload)

    payload = json.loads((PROFILES_DIR / "P1-mainstream.json").read_text(encoding="utf-8"))
    payload["vibe_alignment"]["unexpected"] = "not allowed"
    with pytest.raises(
        TasteProfileError,
        match=r"Unknown field\(s\) at profile.vibe_alignment: unexpected",
    ):
        validate_profile(payload)


def test_keyword_constraints_are_reported_as_audit_only_when_no_filter_exists() -> None:
    profile = load_profile(PROFILES_DIR / "P2-dark_anime.json")
    resolved = resolve_profile(profile)

    assert resolved["audit_only_constraints"]["include_keywords"] == ["psychological"]
    assert resolved["audit_only_constraints"]["exclude_keywords"] == [
        "ecchi",
        "harem",
        "fan service",
    ]
    assert "keywords" not in resolved["candidate_filters"]


@pytest.mark.parametrize("profile_path", sorted(PROFILES_DIR.glob("*.json")))
def test_profile_runner_uses_real_deck_service_and_keeps_hard_checks_green(
    tmp_path: Path,
    profile_path: Path,
) -> None:
    profile = load_profile(profile_path)
    runtime_root = tmp_path / "runtime"
    report = evaluate_profile(
        profile,
        runtime_root=runtime_root,
        app_data_dir=runtime_root / "data",
        commit="test-commit",
        app_version="test-version",
    )

    assert len(report["top_10"]) == 10
    assert report["all_hard_checks_passed"] is True
    assert report["isolation_proof"]["app_data_dir_inside_runtime"] is True
    assert report["hard_checks"]["watched_leak"]["passed"] is True
    assert report["hard_checks"]["hidden_leak"]["passed"] is True
    assert report["vibe_alignment"]["audit_only"] is True
    assert report["vibe_alignment"]["passed"] is True


def test_same_profile_fixture_date_and_seed_keep_top_ten_reproducible(tmp_path: Path) -> None:
    profile = load_profile(PROFILES_DIR / "P2-dark_anime.json")
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = evaluate_profile(
        profile,
        runtime_root=first_root,
        app_data_dir=first_root / "data",
        commit="test-commit",
        app_version="test-version",
    )
    second = evaluate_profile(
        profile,
        runtime_root=second_root,
        app_data_dir=second_root / "data",
        commit="test-commit",
        app_version="test-version",
    )

    assert [item["tmdb_id"] for item in first["top_10"]] == [
        item["tmdb_id"] for item in second["top_10"]
    ]
    assert first["hard_checks"] == second["hard_checks"]
    assert first["vibe_alignment"] == second["vibe_alignment"]


def test_vibe_rubric_reports_a_concrete_wrong_vibe_reason() -> None:
    profile = load_profile(PROFILES_DIR / "P2-dark_anime.json")
    pool = build_fixed_synthetic_pool()
    outlier = deepcopy(next(candidate for candidate in pool.values() if candidate["tmdb_id"] == 1005))
    outlier["countries"] = outlier["country_codes"] = ["RU"]
    outlier["genres"] = outlier["genre_keys"] = ["drama"]
    outlier["keywords"] = ["school", "fan service"]

    report = evaluate_vibe_alignment(profile, [outlier])

    assert report["passed"] is False
    assert report["cards"][0]["aligned"] is False
    assert report["cards"][0]["reasons"] == [
        "missing_required_all_genres",
        "wrong_country",
        "forbidden_keyword",
    ]


def test_safe_runner_writes_isolation_proof_and_one_report_per_profile(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    output_dir = tmp_path / "evidence"
    env = os.environ.copy()
    env.pop("WATCHBANE_DATA_DIR", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qa.run_synthetic_taste_profile_evaluation",
            "--runtime-root",
            str(runtime_root),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    proof = json.loads((output_dir / "child_isolation_proof.json").read_text(encoding="utf-8"))
    assert proof["isolated"] is True
    assert sorted(path.name for path in output_dir.glob("P*.json")) == [
        "P1-mainstream.json",
        "P2-dark_anime.json",
        "P3-diversity_explorer.json",
    ]


def test_safe_runner_exits_with_a_clear_invalid_profile_error(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "invalid.json").write_text(
        json.dumps({"profile_id": "bad", "unexpected": True}), encoding="utf-8"
    )
    env = os.environ.copy()
    env.pop("WATCHBANE_DATA_DIR", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qa.run_synthetic_taste_profile_evaluation",
            "--runtime-root",
            str(tmp_path / "runtime"),
            "--profiles-dir",
            str(profiles_dir),
            "--output-dir",
            str(tmp_path / "evidence"),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "SYNTHETIC_PROFILE_FAIL: Unknown field(s) at profile: unexpected" in completed.stderr
