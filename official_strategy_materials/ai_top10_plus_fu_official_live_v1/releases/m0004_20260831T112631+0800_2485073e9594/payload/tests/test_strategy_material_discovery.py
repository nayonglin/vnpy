from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from qmt_roll_strategy_material_discovery import (
    MaterialDeclaration,
    MaterialDiscoveryError,
    assert_discovery_publishable,
    discover_materials,
)
from qmt_roll_strategy_material_manifest import MaterialRole


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.name", "Tests")
    _git(path, "config", "user.email", "tests@example.com")
    return path


def test_discovery_closes_local_imports_and_rejects_ignored_decision_asset(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "entry.py").write_text("import helper\n", encoding="utf-8")
    (repo / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    ignored = repo / "backtest_outputs/pool.csv"
    ignored.parent.mkdir()
    ignored.write_text("rank,symbol\n1,fu.SHFE\n", encoding="utf-8")
    (repo / ".gitignore").write_text("backtest_outputs/\n", encoding="utf-8")
    _git(repo, "add", "entry.py", "helper.py", ".gitignore")
    _git(repo, "commit", "-m", "fixture")
    result = discover_materials(
        repo_root=repo,
        entrypoints=(Path("entry.py"),),
        declared_paths=(),
        config_assets=(
            MaterialDeclaration(
                source_path=ignored,
                logical_path="ai/official-pool.csv",
                role=MaterialRole.DECISION_ASSET,
            ),
        ),
        ai_artifacts=(),
    )
    assert "helper.py" in result.repo_paths
    with pytest.raises(MaterialDiscoveryError, match="ignored_decision_asset"):
        assert_discovery_publishable(result)


def test_external_promotion_source_is_allowed_but_external_runtime_is_blocked(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    (repo / "entry.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "entry.py")
    _git(repo, "commit", "-m", "fixture")
    external = tmp_path / "pool.csv"
    external.write_text("rank,symbol\n1,fu.SHFE\n", encoding="utf-8")
    result = discover_materials(
        repo_root=repo,
        entrypoints=(),
        declared_paths=(Path("entry.py"),),
        config_assets=(),
        ai_artifacts=(
            MaterialDeclaration(
                source_path=external,
                logical_path="ai/pool.csv",
                role=MaterialRole.DECISION_ASSET,
                source_kind="promotion_source",
            ),
        ),
    )
    assert not result.blockers

    blocked = discover_materials(
        repo_root=repo,
        entrypoints=(),
        declared_paths=(),
        config_assets=(),
        ai_artifacts=(
            MaterialDeclaration(
                source_path=external,
                logical_path="runtime/external.py",
                role=MaterialRole.RUNTIME_CODE,
                source_kind="promotion_source",
            ),
        ),
    )
    with pytest.raises(MaterialDiscoveryError, match="external_runtime_dependency"):
        assert_discovery_publishable(blocked)


def test_non_literal_dynamic_import_is_a_blocker(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "entry.py").write_text(
        "import importlib\nname = 'helper'\nimportlib.import_module(name)\n",
        encoding="utf-8",
    )
    _git(repo, "add", "entry.py")
    _git(repo, "commit", "-m", "fixture")
    result = discover_materials(
        repo_root=repo,
        entrypoints=(Path("entry.py"),),
        declared_paths=(),
        config_assets=(),
        ai_artifacts=(),
    )
    with pytest.raises(MaterialDiscoveryError, match="unresolved_dynamic_import"):
        assert_discovery_publishable(result)
