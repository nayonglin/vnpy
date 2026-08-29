from __future__ import annotations

import argparse
from pathlib import Path
import json
import subprocess
import sys

import pytest

PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import build_qmt_roll_official_strategy_material_release as material_release
from build_qmt_roll_official_strategy_material_release import (
    GitLfsStatus,
    MaterialReleaseError,
    ReleaseRequest,
    activate_release,
    classify_storage,
    commit_prepared_release,
    prepare_release,
    promote_official_version_to_master,
    publish_materials_to_master,
    verify_release,
)
from qmt_roll_official_baseline_identity import (
    assert_official_checkout_matches_active_material,
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
    config = repo / "examples/portfolio_backtesting/qmt_roll_official_live_config.py"
    config.parent.mkdir(parents=True)
    config.write_text(
        'OFFICIAL_LIVE_RULESET_VERSION: str = "stage021_q_rollover_volume_atr_v1"\n',
        encoding="utf-8",
    )
    executable = repo / "examples/portfolio_backtesting/run_official_test.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    skill = repo / "skills/freeze-official-strategy-materials/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Freeze official strategy materials\n", encoding="utf-8")
    registry = repo / "research/registry.md"
    registry.parent.mkdir(parents=True)
    registry.write_text("# Research registry\n", encoding="utf-8")
    _git(
        repo,
        "add",
        "pool.csv",
        "examples/portfolio_backtesting/qmt_roll_official_live_config.py",
        "examples/portfolio_backtesting/run_official_test.sh",
        "skills/freeze-official-strategy-materials/SKILL.md",
        "research/registry.md",
    )
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
            MaterialDeclaration(
                source_path=config,
                logical_path="examples/portfolio_backtesting/qmt_roll_official_live_config.py",
                role=MaterialRole.STRATEGY_CONFIG,
            ),
            MaterialDeclaration(
                source_path=executable,
                logical_path="examples/portfolio_backtesting/run_official_test.sh",
                role=MaterialRole.RUNTIME_CODE,
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


def _bare_master_remote(tmp_path: Path, repo: Path) -> Path:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-b", "master")
    _git(seed, "config", "user.name", "Tests")
    _git(seed, "config", "user.email", "tests@example.com")
    (seed / "README.md").write_text("remote master\n", encoding="utf-8")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "remote base")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "origin", "master")
    _git(repo, "remote", "add", "publish-origin", str(remote))
    return remote


def _qualified_activation_fixture(
    tmp_path: Path,
) -> tuple[Path, object, str, dict[str, object], Path]:
    repo, request = _request(tmp_path)
    remote = _bare_master_remote(tmp_path, repo)
    prepared = prepare_release(request)
    release_commit = commit_prepared_release(
        repo_root=repo,
        prepared=prepared,
        confirmation=(
            "I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:"
            f"{prepared.release_id}"
        ),
    )
    qualification = {
        "status": "passed",
        "release_commit": release_commit,
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "evidence_ids": ["test-evidence"],
    }
    activation_commit = activate_release(
        repo_root=repo,
        release_id=prepared.release_id,
        release_commit=release_commit,
        qualification=qualification,
        confirmation=(
            "I_UNDERSTAND_THIS_ACTIVATES_OFFICIAL_STRATEGY_MATERIALS:"
            f"{prepared.release_id}"
        ),
    )
    return repo, prepared, activation_commit, qualification, remote


def _clone_master(remote: Path, target: Path) -> Path:
    subprocess.run(
        ["git", "clone", "--no-local", "--branch", "master", str(remote), str(target)],
        check=True,
        capture_output=True,
        text=True,
    )
    return target


def test_cli_prepare_discovers_core_strategy_local_import_closure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The release inventory must contain the runtime strategy and its local imports."""
    captured: dict[str, ReleaseRequest] = {}
    monkeypatch.setattr(
        "qmt_roll_ai_artifact_registry.load_publication_request",
        lambda _path: {
            "ai_artifacts": [],
            "generator": "test-generator",
            "data_cutoff": "2026-08-25",
            "eval_date": "2026-08-25",
            "training_label_cutoff": "2026-08-24",
            "request_sha256": "test-request",
            "official_version": "official-test",
            "source_commit": _git(PORTFOLIO_DIR.parents[1], "rev-parse", "HEAD"),
        },
    )
    monkeypatch.setattr(
        material_release,
        "assert_publication_source_commit",
        lambda _repo, source_commit: source_commit,
    )
    monkeypatch.setattr(
        material_release,
        "prepare_release",
        lambda request: captured.setdefault("request", request),
    )

    material_release._cli_prepare(
        argparse.Namespace(
            repo_root=str(PORTFOLIO_DIR.parents[1]),
            publication_request="unused-by-this-discovery-test.json",
            capital=150000.0,
            capital_label="15w",
            research_line="futures_official_strategy_material_governance",
            stage179_manifest=None,
        )
    )

    discovered_paths = set(captured["request"].discovery.repo_paths)
    assert {
        "examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py",
        "examples/portfolio_backtesting/main_contract_mapping.py",
        "examples/portfolio_backtesting/qmt_roll_ai_selection_pairwise_runtime.py",
        "examples/portfolio_backtesting/qmt_roll_ai_path_damage_runtime.py",
    }.issubset(discovered_paths)
    assert "tests/test_strategy_material_discovery.py" in discovered_paths
    assert "skills/freeze-official-strategy-materials/SKILL.md" in discovered_paths
    assert not any(
        blocker.startswith("unresolved_dynamic_import:tests/")
        for blocker in captured["request"].discovery.blockers
    )


def test_publication_request_source_commit_must_match_clean_head(
    tmp_path: Path,
) -> None:
    repo, _request_value = _request(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    validator = getattr(
        material_release,
        "assert_publication_source_commit",
        None,
    )
    assert callable(validator), "material publisher must bind request to clean HEAD"

    assert validator(repo, head) == head
    with pytest.raises(MaterialReleaseError, match="publication_source_commit_invalid"):
        validator(repo, "not-a-commit")
    with pytest.raises(MaterialReleaseError, match="publication_source_commit_not_head"):
        validator(repo, "0" * 40)

    (repo / "pool.csv").write_text("rank,symbol\n1,cu.SHFE\n", encoding="utf-8")
    with pytest.raises(MaterialReleaseError, match="source_tree_not_clean"):
        validator(repo, head)


def test_prepare_is_immutable_and_verifiable(tmp_path: Path) -> None:
    repo, request = _request(tmp_path)
    prepared = prepare_release(request)
    assert prepared.material_version == "m0001"
    assert (prepared.release_dir / "payload/ai/pool.csv").is_file()
    manifest = verify_release(repo_root=repo, release_id=prepared.release_id)
    assert manifest["order_api_called_count"] == 0
    assert manifest["files"][0]["logical_path"] == "ai/pool.csv"
    assert (
        prepared.release_dir
        / "payload/examples/portfolio_backtesting/run_official_test.sh"
    ).stat().st_mode & 0o111


def test_promote_master_publishes_source_current_and_governance(tmp_path: Path) -> None:
    repo, release, activation, qualification, remote = _qualified_activation_fixture(tmp_path)
    result = promote_official_version_to_master(
        repo_root=repo,
        release_id=release.release_id,
        release_commit=qualification["release_commit"],
        activation_commit=activation,
        qualification=qualification,
        governance_paths=(
            "skills/freeze-official-strategy-materials/SKILL.md",
            "research/registry.md",
        ),
        confirmation=f"I_APPROVE_COMPLETE_OFFICIAL_PROMOTION_TO_MASTER:{release.release_id}",
        remote="publish-origin",
    )

    clone = _clone_master(remote, tmp_path / "promoted-clone")
    identity = assert_official_checkout_matches_active_material(clone)
    assert identity.ruleset_version == "stage021_q_rollover_volume_atr_v1"
    current = json.loads(
        (clone / "official_strategy_materials/CURRENT.json").read_text(encoding="utf-8")
    )
    assert current["release_id"] == release.release_id
    assert (clone / "skills/freeze-official-strategy-materials/SKILL.md").is_file()
    assert (clone / "research/registry.md").is_file()
    assert (
        clone / "examples/portfolio_backtesting/run_official_test.sh"
    ).stat().st_mode & 0o111
    assert result.promoted_commit == _git(clone, "rev-parse", "HEAD")


def test_promote_master_requires_exact_confirmation(tmp_path: Path) -> None:
    repo, release, activation, qualification, _remote = _qualified_activation_fixture(tmp_path)
    with pytest.raises(
        MaterialReleaseError,
        match="complete_official_promotion_confirmation_missing",
    ):
        promote_official_version_to_master(
            repo_root=repo,
            release_id=release.release_id,
            release_commit=qualification["release_commit"],
            activation_commit=activation,
            qualification=qualification,
            governance_paths=(),
            confirmation="",
            remote="publish-origin",
        )


def test_promote_master_rejects_activation_for_another_release(tmp_path: Path) -> None:
    repo, release, _activation, qualification, _remote = _qualified_activation_fixture(tmp_path)
    current_path = repo / "official_strategy_materials/CURRENT.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    current["release_id"] = "m9999_wrong_release"
    current_path.write_text(json.dumps(current, sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, "add", "official_strategy_materials/CURRENT.json")
    _git(repo, "commit", "-m", "fixture: wrong activation")
    wrong_activation = _git(repo, "rev-parse", "HEAD")

    with pytest.raises(MaterialReleaseError, match="promotion_activation_release_mismatch"):
        promote_official_version_to_master(
            repo_root=repo,
            release_id=release.release_id,
            release_commit=qualification["release_commit"],
            activation_commit=wrong_activation,
            qualification=qualification,
            governance_paths=(),
            confirmation=f"I_APPROVE_COMPLETE_OFFICIAL_PROMOTION_TO_MASTER:{release.release_id}",
            remote="publish-origin",
        )


def test_promote_master_rejects_ruleset_drift(tmp_path: Path) -> None:
    repo, release, _activation, qualification, _remote = _qualified_activation_fixture(tmp_path)
    config = repo / "examples/portfolio_backtesting/qmt_roll_official_live_config.py"
    config.write_text(
        'OFFICIAL_LIVE_RULESET_VERSION: str = "drifted_ruleset"\n',
        encoding="utf-8",
    )
    _git(repo, "add", "examples/portfolio_backtesting/qmt_roll_official_live_config.py")
    _git(repo, "commit", "-m", "fixture: ruleset drift")
    drifted_activation = _git(repo, "rev-parse", "HEAD")

    with pytest.raises(MaterialReleaseError, match="top_level_ruleset_mismatch"):
        promote_official_version_to_master(
            repo_root=repo,
            release_id=release.release_id,
            release_commit=qualification["release_commit"],
            activation_commit=drifted_activation,
            qualification=qualification,
            governance_paths=(),
            confirmation=f"I_APPROVE_COMPLETE_OFFICIAL_PROMOTION_TO_MASTER:{release.release_id}",
            remote="publish-origin",
        )


def test_promote_master_rejects_governance_path_traversal(tmp_path: Path) -> None:
    repo, release, activation, qualification, _remote = _qualified_activation_fixture(tmp_path)
    with pytest.raises(MaterialReleaseError, match="promotion_governance_path_invalid"):
        promote_official_version_to_master(
            repo_root=repo,
            release_id=release.release_id,
            release_commit=qualification["release_commit"],
            activation_commit=activation,
            qualification=qualification,
            governance_paths=("../outside.md",),
            confirmation=f"I_APPROVE_COMPLETE_OFFICIAL_PROMOTION_TO_MASTER:{release.release_id}",
            remote="publish-origin",
        )


def test_promote_master_rechecks_remote_before_push(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, release, activation, qualification, _remote = _qualified_activation_fixture(tmp_path)
    real_head = material_release._remote_branch_head(repo, "publish-origin", "master")
    observed = iter((real_head, "f" * 40))
    monkeypatch.setattr(material_release, "_remote_branch_head", lambda *_args: next(observed))

    with pytest.raises(MaterialReleaseError, match="remote_master_changed_before_promotion_push"):
        promote_official_version_to_master(
            repo_root=repo,
            release_id=release.release_id,
            release_commit=qualification["release_commit"],
            activation_commit=activation,
            qualification=qualification,
            governance_paths=(),
            confirmation=f"I_APPROVE_COMPLETE_OFFICIAL_PROMOTION_TO_MASTER:{release.release_id}",
            remote="publish-origin",
        )


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


def test_publish_master_directly_pushes_only_material_directory_without_pr(tmp_path: Path) -> None:
    repo, request = _request(tmp_path)
    remote = _bare_master_remote(tmp_path, repo)
    prepared = prepare_release(request)
    release_commit = commit_prepared_release(
        repo_root=repo,
        prepared=prepared,
        confirmation=f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
    )
    worktrees_before = _git(repo, "worktree", "list", "--porcelain")

    publication = publish_materials_to_master(
        repo_root=repo,
        release_id=prepared.release_id,
        release_commit=release_commit,
        confirmation=f"I_APPROVE_DIRECT_OFFICIAL_MATERIAL_PUSH_TO_MASTER:{prepared.release_id}",
        remote="publish-origin",
    )

    assert publication.status == "published"
    assert publication.changed_paths
    assert all(path.startswith("official_strategy_materials/") for path in publication.changed_paths)
    clone = tmp_path / "master-clone"
    subprocess.run(
        ["git", "clone", "--no-local", "--branch", "master", str(remote), str(clone)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert not (clone / "pool.csv").exists()
    assert not (clone / "official_strategy_materials/CURRENT.json").exists()
    assert (clone / "README.md").read_text(encoding="utf-8") == "remote master\n"
    assert verify_release(repo_root=clone, release_id=prepared.release_id)["manifest_sha256"]
    assert _git(clone, "rev-parse", "HEAD") == publication.published_commit
    repeated = publish_materials_to_master(
        repo_root=repo,
        release_id=prepared.release_id,
        release_commit=release_commit,
        confirmation=f"I_APPROVE_DIRECT_OFFICIAL_MATERIAL_PUSH_TO_MASTER:{prepared.release_id}",
        remote="publish-origin",
    )
    assert repeated.status == "already_published"
    assert repeated.published_commit == publication.published_commit
    assert _git(repo, "worktree", "list", "--porcelain") == worktrees_before


def test_publish_master_requires_exact_authority_and_master_target(tmp_path: Path) -> None:
    repo, request = _request(tmp_path)
    _bare_master_remote(tmp_path, repo)
    prepared = prepare_release(request)
    release_commit = commit_prepared_release(
        repo_root=repo,
        prepared=prepared,
        confirmation=f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
    )

    with pytest.raises(MaterialReleaseError, match="direct_master_push_confirmation_missing"):
        publish_materials_to_master(
            repo_root=repo,
            release_id=prepared.release_id,
            release_commit=release_commit,
            confirmation="",
            remote="publish-origin",
        )
    with pytest.raises(MaterialReleaseError, match="publish_branch_must_be_master"):
        publish_materials_to_master(
            repo_root=repo,
            release_id=prepared.release_id,
            release_commit=release_commit,
            confirmation=f"I_APPROVE_DIRECT_OFFICIAL_MATERIAL_PUSH_TO_MASTER:{prepared.release_id}",
            remote="publish-origin",
            branch="main",
        )


def test_publish_master_rejects_activation_commit(tmp_path: Path) -> None:
    repo, request = _request(tmp_path)
    _bare_master_remote(tmp_path, repo)
    prepared = prepare_release(request)
    release_commit = commit_prepared_release(
        repo_root=repo,
        prepared=prepared,
        confirmation=f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
    )
    qualification = {
        "status": "passed",
        "release_commit": release_commit,
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "evidence_ids": ["test-evidence"],
    }
    activation_commit = activate_release(
        repo_root=repo,
        release_id=prepared.release_id,
        release_commit=release_commit,
        qualification=qualification,
        confirmation=f"I_UNDERSTAND_THIS_ACTIVATES_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
    )

    with pytest.raises(MaterialReleaseError, match="release_commit_subject_invalid"):
        publish_materials_to_master(
            repo_root=repo,
            release_id=prepared.release_id,
            release_commit=activation_commit,
            confirmation=f"I_APPROVE_DIRECT_OFFICIAL_MATERIAL_PUSH_TO_MASTER:{prepared.release_id}",
            remote="publish-origin",
        )


def test_publish_master_noop_rechecks_remote_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, request = _request(tmp_path)
    _bare_master_remote(tmp_path, repo)
    prepared = prepare_release(request)
    release_commit = commit_prepared_release(
        repo_root=repo,
        prepared=prepared,
        confirmation=f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
    )
    publication = publish_materials_to_master(
        repo_root=repo,
        release_id=prepared.release_id,
        release_commit=release_commit,
        confirmation=f"I_APPROVE_DIRECT_OFFICIAL_MATERIAL_PUSH_TO_MASTER:{prepared.release_id}",
        remote="publish-origin",
    )
    observed = iter((publication.published_commit, "f" * 40))
    monkeypatch.setattr(material_release, "_remote_branch_head", lambda *_args: next(observed))

    with pytest.raises(MaterialReleaseError, match="remote_master_changed_before_noop_readback"):
        publish_materials_to_master(
            repo_root=repo,
            release_id=prepared.release_id,
            release_commit=release_commit,
            confirmation=f"I_APPROVE_DIRECT_OFFICIAL_MATERIAL_PUSH_TO_MASTER:{prepared.release_id}",
            remote="publish-origin",
        )


def test_release_index_rejects_duplicate_material_version(tmp_path: Path) -> None:
    source = tmp_path / "source/official_test/index.json"
    target = tmp_path / "target/official_test/index.json"
    source.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    source.write_text(
        '{"schema_version":1,"official_version":"official_test","releases":[{"material_version":"m0001","release_id":"m0001_source"}]}\n',
        encoding="utf-8",
    )
    target.write_text(
        '{"schema_version":1,"official_version":"official_test","releases":[{"material_version":"m0001","release_id":"m0001_target"}]}\n',
        encoding="utf-8",
    )
    with pytest.raises(MaterialReleaseError, match="remote_material_version_conflict"):
        material_release._merge_release_index(source, target)


def test_publish_master_blocks_lfs_until_target_remote_is_proven(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, request = _request(tmp_path)
    _bare_master_remote(tmp_path, repo)
    prepared = prepare_release(request)
    release_commit = commit_prepared_release(
        repo_root=repo,
        prepared=prepared,
        confirmation=f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
    )
    monkeypatch.setattr(material_release, "_material_root_uses_lfs", lambda _root: True)

    with pytest.raises(MaterialReleaseError, match="direct_master_lfs_remote_not_proven"):
        publish_materials_to_master(
            repo_root=repo,
            release_id=prepared.release_id,
            release_commit=release_commit,
            confirmation=f"I_APPROVE_DIRECT_OFFICIAL_MATERIAL_PUSH_TO_MASTER:{prepared.release_id}",
            remote="publish-origin",
        )


def test_release_commit_rejects_index_manifest_mismatch(tmp_path: Path) -> None:
    repo, request = _request(tmp_path)
    prepared = prepare_release(request)
    index_path = repo / "official_strategy_materials/official_test/index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["releases"][0]["manifest_sha256"] = "0" * 64
    index_path.write_text(json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    _git(repo, "add", "--", str(index_path.relative_to(repo)))

    with pytest.raises(MaterialReleaseError, match="release_index_manifest_mismatch"):
        commit_prepared_release(
            repo_root=repo,
            prepared=prepared,
            confirmation=f"I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{prepared.release_id}",
        )
