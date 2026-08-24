from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from qmt_roll_ai_artifact_registry import (
    AiArtifact,
    AiArtifactRegistryError,
    load_publication_request,
    register_experiment_artifacts,
    write_publication_request,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_publication_request_records_hashes_and_rejects_source_drift(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    pool.write_text("rank,symbol\n1,fu.SHFE\n", encoding="utf-8")
    request = write_publication_request(
        destination=tmp_path / "control/request.json",
        official_version="official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        generator="stage935",
        data_cutoff="2026-08-03",
        eval_date="2026-07-31",
        training_label_cutoff="2026-05-07",
        artifacts=(AiArtifact(pool, "combined_eligibility.csv", "decision_asset", True),),
        source_commit="d6080c914ae9884eaa984618f37f18022ef5e058",
    )
    payload = load_publication_request(request)
    assert payload["promotion_scope"] == "official_candidate"
    assert payload["order_api_called_count"] == 0
    pool.write_text("rank,symbol\n1,rb.SHFE\n", encoding="utf-8")
    with pytest.raises(AiArtifactRegistryError, match="publication_source_sha256_mismatch"):
        load_publication_request(request)


def test_experiment_registry_copies_only_reproducibility_assets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Tests")
    _git(repo, "config", "user.email", "tests@example.com")
    (repo / ".gitignore").write_text("source/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "fixture")
    source = repo / "source"
    source.mkdir()
    model = source / "pool.csv"
    chart = source / "curve.png"
    model.write_text("rank,symbol\n1,fu.SHFE\n", encoding="utf-8")
    chart.write_bytes(b"chart")
    result = register_experiment_artifacts(
        repo_root=repo,
        line_id="futures_trend_example",
        stage="stage001",
        run_id="20260819_153000",
        artifacts=(
            AiArtifact(model, "official-pool", "decision_asset", True),
            AiArtifact(chart, "curve", "cache_or_visualization", False),
        ),
    )
    assert result.copied_logical_names == ("official-pool",)
    assert (result.destination / "payload/official-pool.csv").is_file()
    assert not (result.destination / "payload/curve.png").exists()
    assert result.staged_paths
