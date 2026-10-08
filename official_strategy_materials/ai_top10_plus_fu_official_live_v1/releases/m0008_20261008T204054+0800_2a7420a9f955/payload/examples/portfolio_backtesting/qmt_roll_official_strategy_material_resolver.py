from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Mapping

from qmt_roll_strategy_material_manifest import (
    MaterialManifestError,
    load_and_validate_material_manifest,
    sha256_file,
)


CURRENT_SCHEMA_VERSION = 1
ACTIVE_MODE = "active"
BOOTSTRAP_MODE = "bootstrap_non_deployable"


class ActiveMaterialError(RuntimeError):
    """Raised when an active official material pointer or payload is invalid."""


@dataclass(frozen=True)
class ActiveMaterialRelease:
    repo_root: Path
    current_path: Path
    activation_mode: str
    release_id: str
    release_commit: str
    strategy_version: str
    material_version: str
    manifest_path: Path
    manifest: Mapping[str, object]

    @property
    def deployable(self) -> bool:
        return self.activation_mode == ACTIVE_MODE


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _load_current(current_path: Path) -> dict[str, object]:
    if current_path.is_symlink() or not current_path.is_file():
        raise ActiveMaterialError("active_material_current_missing")
    try:
        payload = json.loads(current_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ActiveMaterialError("active_material_current_json_invalid") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != CURRENT_SCHEMA_VERSION:
        raise ActiveMaterialError("active_material_current_schema_invalid")
    required = {
        "schema_version",
        "activation_mode",
        "strategy_version",
        "release_id",
        "release_commit",
        "material_version",
        "manifest_sha256",
        "tree_fingerprint",
        "activated_at_utc",
        "qualification",
    }
    optional = {"ruleset_version", "source_commit"}
    if not required.issubset(payload) or not set(payload).issubset(required | optional):
        raise ActiveMaterialError("active_material_current_fields_invalid")
    if payload["activation_mode"] not in {ACTIVE_MODE, BOOTSTRAP_MODE}:
        raise ActiveMaterialError("active_material_activation_mode_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", str(payload["release_commit"])):
        raise ActiveMaterialError("active_material_release_commit_invalid")
    if "ruleset_version" in payload and not isinstance(payload["ruleset_version"], str):
        raise ActiveMaterialError("active_material_ruleset_version_invalid")
    if "source_commit" in payload and not re.fullmatch(
        r"[0-9a-f]{40}", str(payload["source_commit"])
    ):
        raise ActiveMaterialError("active_material_source_commit_invalid")
    return payload


def _assert_release_commit(repo_root: Path, manifest_path: Path, release_commit: str) -> None:
    relative = manifest_path.resolve(strict=True).relative_to(repo_root).as_posix()
    process = _git(repo_root, "cat-file", "-e", f"{release_commit}:{relative}")
    if process.returncode != 0:
        raise ActiveMaterialError("active_material_release_commit_missing_manifest")


def load_active_material_release(
    current_path: Path,
    *,
    repo_root: Path,
) -> ActiveMaterialRelease:
    repo = repo_root.resolve(strict=True)
    current = _load_current(current_path)
    strategy_version = str(current["strategy_version"])
    release_id = str(current["release_id"])
    manifest_path = (
        repo
        / "official_strategy_materials"
        / strategy_version
        / "releases"
        / release_id
        / "manifest.json"
    )
    try:
        manifest = load_and_validate_material_manifest(
            manifest_path,
            release_root=manifest_path.parent,
        )
    except MaterialManifestError as exc:
        raise ActiveMaterialError(str(exc)) from exc
    identity_pairs = (
        ("release_id", release_id),
        ("strategy_version", strategy_version),
        ("material_version", str(current["material_version"])),
        ("manifest_sha256", str(current["manifest_sha256"])),
        ("tree_fingerprint", str(current["tree_fingerprint"])),
    )
    for field, expected in identity_pairs:
        if str(manifest[field]) != expected:
            raise ActiveMaterialError(f"active_material_{field}_mismatch")
    release_commit = str(current["release_commit"])
    _assert_release_commit(repo, manifest_path, release_commit)
    return ActiveMaterialRelease(
        repo_root=repo,
        current_path=current_path.resolve(strict=True),
        activation_mode=str(current["activation_mode"]),
        release_id=release_id,
        release_commit=release_commit,
        strategy_version=strategy_version,
        material_version=str(current["material_version"]),
        manifest_path=manifest_path,
        manifest=manifest,
    )


def unique_inventory_row(
    manifest: Mapping[str, object],
    logical_path: str,
) -> Mapping[str, object]:
    rows = [
        row
        for row in manifest.get("files", [])
        if isinstance(row, dict) and row.get("logical_path") == logical_path
    ]
    if not rows:
        raise ActiveMaterialError(f"active_material_logical_path_missing:{logical_path}")
    if len(rows) != 1:
        raise ActiveMaterialError(f"active_material_logical_path_not_unique:{logical_path}")
    return rows[0]


def verify_material_file(path: Path, row: Mapping[str, object]) -> None:
    if path.is_symlink() or not path.is_file():
        raise ActiveMaterialError("active_material_not_regular")
    if path.stat().st_size != int(row["size_bytes"]):
        raise ActiveMaterialError("active_material_size_mismatch")
    if sha256_file(path) != row["sha256"]:
        raise ActiveMaterialError("active_material_sha256_mismatch")


def resolve_active_material(
    active: ActiveMaterialRelease,
    *,
    logical_path: str,
) -> Path:
    row = unique_inventory_row(active.manifest, logical_path)
    path = active.manifest_path.parent / str(row["payload_path"])
    try:
        path.resolve(strict=True).relative_to(active.manifest_path.parent.resolve(strict=True))
    except ValueError as exc:
        raise ActiveMaterialError("active_material_payload_path_escape") from exc
    verify_material_file(path, row)
    return path


def assert_runtime_materials_match_checkout(active: ActiveMaterialRelease) -> None:
    drifted: list[str] = []
    for row in active.manifest.get("files", []):
        if not isinstance(row, dict) or row.get("role") not in {
            "runtime_code",
            "strategy_config",
            "operational_config",
        }:
            continue
        source_path = str(row.get("source_path", ""))
        if source_path.startswith("promotion_source:"):
            continue
        target = active.repo_root / source_path
        try:
            verify_material_file(target, row)
        except ActiveMaterialError:
            drifted.append(source_path)
    if drifted:
        raise ActiveMaterialError(
            "active_runtime_material_drift:" + ",".join(sorted(drifted))
        )


def assert_active_release_deployable(active: ActiveMaterialRelease) -> None:
    if active.activation_mode == BOOTSTRAP_MODE:
        raise ActiveMaterialError("bootstrap_material_release_not_deployable")
    qualification = json.loads(active.current_path.read_text(encoding="utf-8"))["qualification"]
    if not isinstance(qualification, dict) or qualification.get("status") not in {"passed", "qualified"}:
        raise ActiveMaterialError("active_material_qualification_not_passed")
    if qualification.get("release_commit") != active.release_commit:
        raise ActiveMaterialError("active_material_qualification_commit_mismatch")
    if int(qualification.get("order_api_called_count", -1)) != 0:
        raise ActiveMaterialError("active_material_order_api_count_nonzero")
    if int(qualification.get("cancel_order_api_called_count", -1)) != 0:
        raise ActiveMaterialError("active_material_order_api_count_nonzero")
    evidence_ids = qualification.get("evidence_ids")
    if not isinstance(evidence_ids, list) or not evidence_ids:
        raise ActiveMaterialError("active_material_qualification_evidence_missing")
    assert_runtime_materials_match_checkout(active)


def material_release_critical_files(
    material_root: Path,
    release_id: str,
) -> tuple[str, ...]:
    root = material_root.resolve(strict=True)
    repo_root = root.parent
    matches = list(root.glob(f"*/releases/{release_id}"))
    if len(matches) != 1:
        raise ActiveMaterialError("material_release_not_unique")
    release_dir = matches[0]
    verify_release_metadata = ("manifest.json", "inventory.csv", "checksums.sha256", "RELEASE.md")
    files = [release_dir / name for name in verify_release_metadata]
    manifest = load_and_validate_material_manifest(release_dir / "manifest.json", release_root=release_dir)
    files.extend(release_dir / str(row["payload_path"]) for row in manifest["files"])
    return tuple(sorted(path.relative_to(repo_root).as_posix() for path in files))


def active_release_critical_files(
    *,
    repo_root: Path,
    require_deployable: bool = True,
) -> tuple[str, ...]:
    repo = repo_root.resolve(strict=True)
    current_path = repo / "official_strategy_materials/CURRENT.json"
    active = load_active_material_release(current_path, repo_root=repo)
    if require_deployable:
        assert_active_release_deployable(active)
    files = list(material_release_critical_files(repo / "official_strategy_materials", active.release_id))
    files.append(current_path.relative_to(repo).as_posix())
    return tuple(sorted(files))
