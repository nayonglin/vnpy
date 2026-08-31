from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from build_qmt_roll_official_strategy_material_release import write_current_atomically
from qmt_roll_official_baseline_identity import (
    OfficialBaselineIdentityError,
    assert_official_checkout_matches_active_material,
)
from qmt_roll_strategy_material_manifest import (
    MaterialFile,
    MaterialRole,
    StorageKind,
    build_material_manifest,
    serialize_material_manifest,
    sha256_file,
)


RULESET = "stage021_q_rollover_volume_atr_v1"
CONFIG_LOGICAL_PATH = "examples/portfolio_backtesting/qmt_roll_official_live_config.py"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _config_bytes(ruleset: str) -> bytes:
    return (
        "from __future__ import annotations\n\n"
        f'OFFICIAL_LIVE_RULESET_VERSION: str = "{ruleset}"\n'
    ).encode()


def _write_active_fixture(
    tmp_path: Path,
    *,
    top_ruleset: str,
    payload_ruleset: str,
) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Tests")
    _git(repo, "config", "user.email", "tests@example.com")

    top_config = repo / CONFIG_LOGICAL_PATH
    top_config.parent.mkdir(parents=True)
    top_config.write_bytes(_config_bytes(top_ruleset))
    _git(repo, "add", CONFIG_LOGICAL_PATH)
    _git(repo, "commit", "-m", "source")
    source_commit = _git(repo, "rev-parse", "HEAD")

    strategy_version = "official_test"
    release_id = f"m0001_20260825T010154+0800_{source_commit[:12]}"
    release = repo / "official_strategy_materials" / strategy_version / "releases" / release_id
    payload_config = release / "payload" / CONFIG_LOGICAL_PATH
    payload_config.parent.mkdir(parents=True)
    payload_config.write_bytes(_config_bytes(payload_ruleset))
    manifest = build_material_manifest(
        release_id=release_id,
        strategy_version=strategy_version,
        material_version="m0001",
        source_commit=source_commit,
        created_at_utc="2026-08-24T17:01:54Z",
        created_at_cst="2026-08-25T01:01:54+08:00",
        research_line="futures_trend_rollover_shape_same_volume",
        capital=150000.0,
        capital_label="15w",
        files=(
            MaterialFile(
                logical_path=CONFIG_LOGICAL_PATH,
                payload_path=f"payload/{CONFIG_LOGICAL_PATH}",
                role=MaterialRole.STRATEGY_CONFIG,
                storage=StorageKind.GIT,
                size_bytes=payload_config.stat().st_size,
                sha256=sha256_file(payload_config),
                source_path=CONFIG_LOGICAL_PATH,
            ),
        ),
        provenance={"eval_date": "2026-07-31"},
        qualification={"status": "candidate", "evidence_ids": []},
        parent_material_version="",
    )
    (release / "manifest.json").write_bytes(serialize_material_manifest(manifest))
    (release / "inventory.csv").write_text(
        "logical_path,payload_path,role,storage,size_bytes,sha256,source_path\n"
        f"{CONFIG_LOGICAL_PATH},payload/{CONFIG_LOGICAL_PATH},strategy_config,git,"
        f"{payload_config.stat().st_size},{sha256_file(payload_config)},{CONFIG_LOGICAL_PATH}\n",
        encoding="utf-8",
    )
    (release / "checksums.sha256").write_text(
        f"{sha256_file(payload_config)}  payload/{CONFIG_LOGICAL_PATH}\n",
        encoding="utf-8",
    )
    (release / "RELEASE.md").write_text("# fixture\n", encoding="utf-8")
    _git(repo, "add", "official_strategy_materials")
    _git(repo, "commit", "-m", "release")
    release_commit = _git(repo, "rev-parse", "HEAD")
    qualification = {
        "status": "passed",
        "release_commit": release_commit,
        "evidence_ids": ["clone-smoke"],
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }
    write_current_atomically(
        repo,
        release_id=release_id,
        release_commit=release_commit,
        qualification=qualification,
    )
    return repo


def test_identity_rejects_same_strategy_name_with_different_ruleset(tmp_path: Path) -> None:
    repo = _write_active_fixture(
        tmp_path,
        top_ruleset="old_c9_v1",
        payload_ruleset=RULESET,
    )
    with pytest.raises(OfficialBaselineIdentityError, match="top_level_ruleset_mismatch"):
        assert_official_checkout_matches_active_material(repo)


def test_current_records_ruleset_and_source_commit(tmp_path: Path) -> None:
    repo = _write_active_fixture(
        tmp_path,
        top_ruleset=RULESET,
        payload_ruleset=RULESET,
    )
    current = json.loads(
        (repo / "official_strategy_materials/CURRENT.json").read_text(encoding="utf-8")
    )
    assert current["ruleset_version"] == RULESET
    assert re.fullmatch(r"[0-9a-f]{40}", current["source_commit"])

    identity = assert_official_checkout_matches_active_material(repo)
    assert identity.strategy_version == "official_test"
    assert identity.ruleset_version == RULESET
    assert identity.source_commit == current["source_commit"]
