from __future__ import annotations

import json
import hashlib
from pathlib import Path
import plistlib
import subprocess
import sys


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from audit_qmt_roll_official_promotion_closure import (
    PRODUCTION_PLIST_NAMES,
    audit_official_promotion_closure,
)
from build_qmt_roll_official_strategy_material_release import write_current_atomically
from qmt_roll_strategy_material_manifest import (
    MaterialFile,
    MaterialRole,
    StorageKind,
    build_material_manifest,
    serialize_material_manifest,
    sha256_file,
)


RULESET = "stage021_q_rollover_volume_atr_v1"
CONFIG_PATH = "examples/portfolio_backtesting/qmt_roll_official_live_config.py"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _active_repo(root: Path, *, ruleset: str, release_id: str) -> Path:
    root.mkdir()
    _git(root, "init", "-b", "master")
    _git(root, "config", "user.name", "Tests")
    _git(root, "config", "user.email", "tests@example.com")
    config = root / CONFIG_PATH
    config.parent.mkdir(parents=True)
    config.write_text(
        f'OFFICIAL_LIVE_RULESET_VERSION: str = "{ruleset}"\n',
        encoding="utf-8",
    )
    _git(root, "add", CONFIG_PATH)
    _git(root, "commit", "-m", "source")
    source_commit = _git(root, "rev-parse", "HEAD")

    strategy = "official_test"
    release = root / "official_strategy_materials" / strategy / "releases" / release_id
    payload = release / "payload" / CONFIG_PATH
    payload.parent.mkdir(parents=True)
    payload.write_bytes(config.read_bytes())
    manifest = build_material_manifest(
        release_id=release_id,
        strategy_version=strategy,
        material_version="m0001",
        source_commit=source_commit,
        created_at_utc="2026-08-24T17:01:54Z",
        created_at_cst="2026-08-25T01:01:54+08:00",
        research_line="futures_trend_rollover_shape_same_volume",
        capital=150000.0,
        capital_label="15w",
        files=(
            MaterialFile(
                logical_path=CONFIG_PATH,
                payload_path=f"payload/{CONFIG_PATH}",
                role=MaterialRole.STRATEGY_CONFIG,
                storage=StorageKind.GIT,
                size_bytes=payload.stat().st_size,
                sha256=sha256_file(payload),
                source_path=CONFIG_PATH,
            ),
        ),
        provenance={"eval_date": "2026-07-31"},
        qualification={"status": "candidate", "evidence_ids": []},
        parent_material_version="",
    )
    (release / "manifest.json").write_bytes(serialize_material_manifest(manifest))
    (release / "inventory.csv").write_text(
        "logical_path,payload_path,role,storage,size_bytes,sha256,source_path\n"
        f"{CONFIG_PATH},payload/{CONFIG_PATH},strategy_config,git,{payload.stat().st_size},"
        f"{sha256_file(payload)},{CONFIG_PATH}\n",
        encoding="utf-8",
    )
    (release / "checksums.sha256").write_text(
        f"{sha256_file(payload)}  payload/{CONFIG_PATH}\n",
        encoding="utf-8",
    )
    (release / "RELEASE.md").write_text("# fixture\n", encoding="utf-8")
    index = {
        "schema_version": 1,
        "official_version": strategy,
        "releases": [
            {
                "material_version": "m0001",
                "release_id": release_id,
                "created_at_cst": manifest["created_at_cst"],
                "source_commit": source_commit,
                "manifest_sha256": manifest["manifest_sha256"],
                "tree_fingerprint": manifest["tree_fingerprint"],
                "file_count": 1,
            }
        ],
    }
    index_path = release.parents[1] / "index.json"
    index_path.write_text(json.dumps(index, sort_keys=True) + "\n", encoding="utf-8")
    _git(root, "add", "official_strategy_materials")
    _git(root, "commit", "-m", f"release(materials): {release_id}")
    release_commit = _git(root, "rev-parse", "HEAD")
    qualification = {
        "status": "passed",
        "release_commit": release_commit,
        "evidence_ids": ["fixture"],
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }
    write_current_atomically(
        root,
        release_id=release_id,
        release_commit=release_commit,
        qualification=qualification,
    )
    _git(root, "add", "official_strategy_materials/CURRENT.json")
    _git(root, "commit", "-m", f"activate(materials): {release_id}")
    return root


def _write_state(
    state: Path,
    *,
    production_root: Path,
    source_commit: str,
    manifest_sha256: str,
) -> Path:
    state.mkdir(parents=True)
    qualification_root = state / "qualification-bundle"
    qualification = qualification_root / "qualification.json"
    qualification.parent.mkdir(parents=True)
    selected_suite = {
        "artifact_kind": "pytest_selected_suite_aggregate",
        "source_commit": source_commit,
        "status": "passed",
        "passed_count": 1,
        "failed_count": 0,
        "skipped_count": 0,
    }
    formal_ctp = {
        "artifact_kind": "formal_ctp_readonly_qualification",
        "source_commit": source_commit,
        "status": "qualified",
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }
    review = {
        "artifact_kind": "production_qualification_independent_review",
        "source_commit": source_commit,
        "status": "passed",
        "p0_count": 0,
        "p1_count": 0,
        "p2_count": 0,
    }
    artifact_refs: dict[str, dict[str, str]] = {}
    for field, filename, payload in (
        ("selected_suite_aggregate", "selected-suite-aggregate.json", selected_suite),
        ("formal_ctp_readonly", "formal-ctp-readonly.json", formal_ctp),
        ("review", "independent-review.json", review),
    ):
        raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
        (qualification_root / filename).write_bytes(raw)
        artifact_refs[field] = {
            "artifact_path": filename,
            "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        }
    qualification.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "evidence_kind": "stage179_c9_15w_production_qualification",
                "evidence_sha256": "b" * 64,
                "source_commit": source_commit,
                **artifact_refs,
            }
        ),
        encoding="utf-8",
    )
    (state / "release-manifest.json").write_text(
        json.dumps(
            {
                "source_commit": source_commit,
                "manifest_sha256": manifest_sha256,
            }
        ),
        encoding="utf-8",
    )
    activation = state / "activation/latest.json"
    activation.parent.mkdir(parents=True)
    activation.write_text(
        json.dumps(
            {
                "source_commit": source_commit,
                "manifest_sha256": manifest_sha256,
                "order_api_called_count": 0,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "launchd_surface_conflict_loaded_count": 0,
                "launchd_surface_production_labels": [
                    name.removesuffix(".plist") for name in PRODUCTION_PLIST_NAMES
                ],
            }
        ),
        encoding="utf-8",
    )
    receipt = state / "runtime/state/activation_receipt.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(
        json.dumps({"manifest_sha256": manifest_sha256, "policy_decision": "approved"}),
        encoding="utf-8",
    )
    launchd = state / "launchd"
    launchd.mkdir()
    for name in PRODUCTION_PLIST_NAMES:
        with (launchd / name).open("wb") as handle:
            plistlib.dump(
                {
                    "Label": name.removesuffix(".plist"),
                    "WorkingDirectory": str(production_root),
                },
                handle,
            )
    return launchd


def _closure_fixture(
    tmp_path: Path,
    *,
    master_ruleset: str = RULESET,
    production_ruleset: str = RULESET,
    all_match: bool = False,
) -> dict[str, object]:
    release_id = "m0001_20260825T010154+0800_111111111111"
    master = _active_repo(tmp_path / "master", ruleset=master_ruleset, release_id=release_id)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", str(master), str(remote)], check=True)
    if all_match or production_ruleset == master_ruleset:
        production = tmp_path / "production"
        subprocess.run(["git", "clone", str(remote), str(production)], check=True)
    else:
        production = _active_repo(
            tmp_path / "production",
            ruleset=production_ruleset,
            release_id="m0001_20260825T010154+0800_222222222222",
        )
    production_source = _git(production, "rev-parse", "HEAD")
    current = json.loads(
        (production / "official_strategy_materials/CURRENT.json").read_text(encoding="utf-8")
    )
    manifest_sha = "a" * 64
    state = tmp_path / "state"
    launchd = _write_state(
        state,
        production_root=production,
        source_commit=production_source,
        manifest_sha256=manifest_sha,
    )
    return {
        "repo_root": master,
        "production_root": production,
        "production_state_root": state,
        "launchd_install_dir": launchd,
        "remote": str(remote),
        "branch": "master",
        "expected_release_id": release_id,
    }


def test_audit_rejects_master_q_with_old_production(tmp_path: Path) -> None:
    fixture = _closure_fixture(
        tmp_path,
        master_ruleset=RULESET,
        production_ruleset="old_c9_v1",
    )
    result = audit_official_promotion_closure(**fixture)
    assert result["status"] == "fail_closed"
    assert "production_ruleset_mismatch" in result["blockers"]


def test_audit_passes_only_six_identity_and_zero_api_match(tmp_path: Path) -> None:
    result = audit_official_promotion_closure(**_closure_fixture(tmp_path, all_match=True))
    assert result["status"] == "passed"
    assert result["ahead_behind"] == [0, 0]
    assert result["order_api_called_count"] == 0
    assert result["send_order_api_called_count"] == 0
    assert result["cancel_order_api_called_count"] == 0
    assert result["launchd_label_count"] == 7


def test_audit_rejects_tampered_qualification_artifact(tmp_path: Path) -> None:
    fixture = _closure_fixture(tmp_path, all_match=True)
    artifact = (
        Path(fixture["production_state_root"])
        / "qualification-bundle/formal-ctp-readonly.json"
    )
    artifact.write_text("{}\n", encoding="utf-8")

    result = audit_official_promotion_closure(**fixture)

    assert result["status"] == "fail_closed"
    assert "production_formal_ctp_readonly_artifact_sha256_mismatch" in result["blockers"]
