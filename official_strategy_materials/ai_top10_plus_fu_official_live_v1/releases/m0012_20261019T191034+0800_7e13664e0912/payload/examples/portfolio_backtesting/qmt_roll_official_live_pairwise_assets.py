"""Bind live pairwise scoring to verified bytes in the active immutable release.

Kept out of lightweight config import: historical materials can still be read,
but a real Stage901 replay cannot use mutable backtest_outputs model files.
"""
from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import Any

from qmt_roll_official_strategy_material_resolver import (
    ActiveMaterialError,
    ActiveMaterialRelease,
    resolve_active_material,
)
from qmt_roll_strategy_material_manifest import sha256_file


PAIRWISE_MODEL_LOGICAL_PATH = "ai/stage182/pairwise/model.joblib"
PAIRWISE_SUMMARY_LOGICAL_PATH = "ai/stage182/pairwise/summary.json"
PAIRWISE_MODEL_SHA256 = "ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66"
PAIRWISE_SUMMARY_SHA256 = "c399a5787577c1cb55276766ed28b0cad8385c063de5b492076dfa8e0619ee86"
PAIRWISE_RUNTIME_VERSIONS = {
    "numpy": "2.4.4",
    "pandas": "2.3.3",
    "scikit-learn": "1.8.0",
    "scipy": "1.17.1",
    "joblib": "1.6.0",
}


class PairwiseAssetsError(RuntimeError):
    """The live model, feature contract or inference runtime is unqualified."""


def assert_pairwise_runtime_versions() -> dict[str, str]:
    actual = {}
    for package, expected in PAIRWISE_RUNTIME_VERSIONS.items():
        try:
            actual[package] = metadata.version(package)
        except metadata.PackageNotFoundError as exc:
            raise PairwiseAssetsError(f"pairwise_runtime_package_missing:{package}") from exc
        if actual[package] != expected:
            raise PairwiseAssetsError(f"pairwise_runtime_version_mismatch:{package}")
    return actual


def resolve_official_pairwise_assets(
    active: ActiveMaterialRelease,
    *,
    expected_release_id: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Return only immutable paths; no environment or mutable-file fallback."""
    manifest = active.manifest
    if (
        active.release_id != expected_release_id
        or manifest.get("release_id") != active.release_id
        or manifest.get("strategy_version") != active.strategy_version
        or manifest.get("material_version") != active.material_version
        or active.strategy_version != "ai_top10_plus_fu_official_live_v1"
        or active.activation_mode != "active"
        or active.manifest_path.parent.name != active.release_id
    ):
        raise PairwiseAssetsError("pairwise_release_identity_mismatch")
    runtime = assert_pairwise_runtime_versions()
    definitions = (
        ("model", "selection_pairwise_model_path", PAIRWISE_MODEL_LOGICAL_PATH,
         PAIRWISE_MODEL_SHA256, "model_artifact"),
        ("summary", "selection_pairwise_summary_path", PAIRWISE_SUMMARY_LOGICAL_PATH,
         PAIRWISE_SUMMARY_SHA256, "feature_contract"),
    )
    overrides: dict[str, str] = {}
    audit: dict[str, Any] = {
        "status": "valid",
        "material_release_id": active.release_id,
        "material_release_commit": active.release_commit,
        "material_manifest_sha256": str(manifest.get("manifest_sha256", "")),
        "runtime_versions": runtime,
    }
    release_root = active.manifest_path.parent.resolve(strict=True)
    for name, parameter, logical_path, expected_sha, role in definitions:
        rows = [row for row in manifest.get("files", []) if row.get("logical_path") == logical_path]
        if not rows:
            raise PairwiseAssetsError(f"pairwise_asset_missing:{logical_path}")
        if len(rows) != 1 or rows[0].get("role") != role:
            raise PairwiseAssetsError(f"pairwise_asset_inventory_invalid:{logical_path}")
        try:
            material_path = resolve_active_material(active, logical_path=logical_path)
            path = material_path.resolve(strict=True)
        except (ActiveMaterialError, OSError, ValueError) as exc:
            raise PairwiseAssetsError(f"pairwise_asset_invalid:{logical_path}") from exc
        canonical = release_root / "payload" / logical_path
        if path != canonical:
            raise PairwiseAssetsError(f"pairwise_asset_release_path_mismatch:{logical_path}")
        if any(parent.is_symlink() for parent in [material_path, *material_path.parents]
               if parent == release_root or release_root in parent.parents):
            raise PairwiseAssetsError(f"pairwise_asset_symlink:{logical_path}")
        if sha256_file(path) != expected_sha:
            raise PairwiseAssetsError(f"pairwise_known_sha256_mismatch:{logical_path}")
        overrides[parameter] = str(path)
        audit[f"{name}_logical_path"] = logical_path
        audit[f"{name}_path"] = str(path)
        audit[f"{name}_sha256"] = expected_sha
    return overrides, audit
