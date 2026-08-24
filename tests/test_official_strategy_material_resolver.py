from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_strategy_material_resolver import (
    ActiveMaterialError,
    active_release_critical_files,
    assert_active_release_deployable,
    load_active_material_release,
    material_release_critical_files,
    resolve_active_material,
)
from qmt_roll_strategy_material_manifest import (
    MaterialFile,
    MaterialRole,
    StorageKind,
    build_material_manifest,
    serialize_material_manifest,
    sha256_file,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _active_repo(tmp_path: Path, *, mode: str = "bootstrap_non_deployable") -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Tests")
    _git(repo, "config", "user.email", "tests@example.com")
    version = "official_test"
    release_id = "m0001_20260819T153000+0800_000000000000"
    release = repo / "official_strategy_materials" / version / "releases" / release_id
    pool = release / "payload/ai/stage182/combined_eligibility.csv"
    pool.parent.mkdir(parents=True)
    pool.write_text("rank,symbol\n1,fu.SHFE\n", encoding="utf-8")
    manifest = build_material_manifest(
        release_id=release_id,
        strategy_version=version,
        material_version="m0001",
        source_commit="0" * 40,
        created_at_utc="2026-08-19T07:30:00Z",
        created_at_cst="2026-08-19T15:30:00+08:00",
        research_line="futures_official_strategy_material_governance",
        capital=150000.0,
        capital_label="15w",
        files=(
            MaterialFile(
                logical_path="ai/stage182/combined_eligibility.csv",
                payload_path="payload/ai/stage182/combined_eligibility.csv",
                role=MaterialRole.DECISION_ASSET,
                storage=StorageKind.GIT,
                size_bytes=pool.stat().st_size,
                sha256=sha256_file(pool),
                source_path="promotion_source:pool.csv",
            ),
        ),
        provenance={"eval_date": "2026-07-31"},
        qualification={"status": "candidate", "evidence_ids": []},
        parent_material_version="",
    )
    (release / "manifest.json").write_bytes(serialize_material_manifest(manifest))
    (release / "inventory.csv").write_text(
        "logical_path,payload_path,role,storage,size_bytes,sha256,source_path\n"
        f"ai/stage182/combined_eligibility.csv,payload/ai/stage182/combined_eligibility.csv,decision_asset,git,{pool.stat().st_size},{sha256_file(pool)},promotion_source:pool.csv\n",
        encoding="utf-8",
    )
    (release / "checksums.sha256").write_text(
        f"{sha256_file(pool)}  payload/ai/stage182/combined_eligibility.csv\n",
        encoding="utf-8",
    )
    (release / "RELEASE.md").write_text("# fixture\n", encoding="utf-8")
    _git(repo, "add", "official_strategy_materials")
    _git(repo, "commit", "-m", "release")
    release_commit = _git(repo, "rev-parse", "HEAD")
    qualification = {
        "status": "bootstrap_passed" if mode != "active" else "passed",
        "release_commit": release_commit,
        "evidence_ids": ["clone-smoke"],
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }
    current = {
        "schema_version": 1,
        "activation_mode": mode,
        "strategy_version": version,
        "release_id": release_id,
        "release_commit": release_commit,
        "material_version": "m0001",
        "manifest_sha256": manifest["manifest_sha256"],
        "tree_fingerprint": manifest["tree_fingerprint"],
        "activated_at_utc": "2026-08-19T07:35:00Z",
        "qualification": qualification,
    }
    current_path = repo / "official_strategy_materials/CURRENT.json"
    current_path.write_text(json.dumps(current, sort_keys=True), encoding="utf-8")
    return repo, current_path


def test_active_resolver_returns_verified_ai_pool_and_rejects_drift(tmp_path: Path) -> None:
    repo, current_path = _active_repo(tmp_path)
    active = load_active_material_release(current_path, repo_root=repo)
    pool = resolve_active_material(active, logical_path="ai/stage182/combined_eligibility.csv")
    assert pool.is_file()
    pool.write_bytes(pool.read_bytes() + b"drift")
    with pytest.raises(ActiveMaterialError, match="active_material_size_mismatch"):
        resolve_active_material(active, logical_path="ai/stage182/combined_eligibility.csv")


def test_bootstrap_release_resolves_offline_but_is_not_deployable(tmp_path: Path) -> None:
    repo, current_path = _active_repo(tmp_path)
    active = load_active_material_release(current_path, repo_root=repo)
    with pytest.raises(ActiveMaterialError, match="bootstrap_material_release_not_deployable"):
        assert_active_release_deployable(active)
    with pytest.raises(ActiveMaterialError, match="bootstrap_material_release_not_deployable"):
        active_release_critical_files(repo_root=repo)
    files = material_release_critical_files(repo / "official_strategy_materials", active.release_id)
    assert any(path.endswith("manifest.json") for path in files)
    assert any(path.endswith("combined_eligibility.csv") for path in files)
