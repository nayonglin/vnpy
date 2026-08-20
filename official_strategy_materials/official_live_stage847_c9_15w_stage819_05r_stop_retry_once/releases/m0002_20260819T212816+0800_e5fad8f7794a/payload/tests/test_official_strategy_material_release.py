from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from build_qmt_roll_official_strategy_material_release import (
    GitLfsStatus,
    MaterialReleaseError,
    ReleaseRequest,
    activate_release,
    classify_storage,
    commit_prepared_release,
    prepare_release,
    verify_release,
)
from qmt_roll_strategy_material_discovery import MaterialDeclaration, discover_materials
from qmt_roll_strategy_material_manifest import MaterialRole


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _request(tmp_path: Path) -> tuple[Path, ReleaseRequest]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Tests")
    _git(repo, "config", "user.email", "tests@example.com")
    source = repo / "pool.csv"
    source.write_text("rank,symbol\n1,fu.SHFE\n", encoding="utf-8")
    _git(repo, "add", "pool.csv")
    _git(repo, "commit", "-m", "source")
    discovery = discover_materials(
        repo_root=repo,
        entrypoints=(),
        declared_paths=(),
        config_assets=(
            MaterialDeclaration(
                source_path=source,
                logical_path="ai/pool.csv",
                role=MaterialRole.DECISION_ASSET,
            ),
        ),
        ai_artifacts=(),
    )
    request = ReleaseRequest(
        repo_root=repo,
        official_version="official_test",
        capital=150000.0,
        capital_label="15w",
        research_line="futures_official_strategy_material_governance",
        source_commit=_git(repo, "rev-parse", "HEAD"),
        created_at_utc="2026-08-19T07:30:00Z",
        created_at_cst="2026-08-19T15:30:00+08:00",
        discovery=discovery,
        provenance={"eval_date": "2026-07-31"},
        qualification={"status": "candidate", "evidence_ids": []},
    )
    return repo, request


def test_prepare_is_immutable_and_verifiable(tmp_path: Path) -> None:
    repo, request = _request(tmp_path)
    prepared = prepare_release(request)
    assert prepared.material_version == "m0001"
    assert (prepared.release_dir / "payload/ai/pool.csv").is_file()
    manifest = verify_release(repo_root=repo, release_id=prepared.release_id)
    assert manifest["order_api_called_count"] == 0
    assert manifest["files"][0]["logical_path"] == "ai/pool.csv"


def test_commit_refuses_unrelated_staged_path_and_never_pushes(tmp_path: Path) -> None:
    repo, request = _request(tmp_path)
    prepared = prepare_release(request)
    (repo / "unrelated.txt").write_text("do not commit", encoding="utf-8")
    _git(repo, "add", "unrelated.txt")
    with pytest.raises(MaterialReleaseError, match="staged_path_outside_release_allowlist"):
        commit_prepared_release(
            repo_root=repo,
            prepared=prepared,
            confirmation=f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
        )


def test_commit_clone_verify_and_blocked_activation(tmp_path: Path) -> None:
    repo, request = _request(tmp_path)
    prepared = prepare_release(request)
    release_commit = commit_prepared_release(
        repo_root=repo,
        prepared=prepared,
        confirmation=f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
    )
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "--no-local", str(repo), str(clone)], check=True, capture_output=True, text=True)
    manifest = verify_release(repo_root=clone, release_id=prepared.release_id)
    assert manifest["manifest_sha256"]
    with pytest.raises(MaterialReleaseError, match="qualification_not_passed"):
        activate_release(
            repo_root=repo,
            release_id=prepared.release_id,
            release_commit=release_commit,
            qualification={"status": "blocked", "evidence_ids": []},
            confirmation=f"I_UNDERSTAND_THIS_ACTIVATES_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
        )


def test_lfs_classification_requires_proven_filters_for_large_file(tmp_path: Path) -> None:
    large = tmp_path / "weights.bin"
    large.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
    with pytest.raises(MaterialReleaseError, match="git_lfs_not_ready"):
        classify_storage(large, lfs_status=GitLfsStatus(filters_ready=False, remote_ready=False))
