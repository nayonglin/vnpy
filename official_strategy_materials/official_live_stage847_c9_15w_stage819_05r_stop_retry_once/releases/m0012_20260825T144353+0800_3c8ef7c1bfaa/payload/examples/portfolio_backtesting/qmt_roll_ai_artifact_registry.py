from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from typing import Iterable, Mapping

from qmt_roll_strategy_material_manifest import canonical_json_bytes, sha256_file


PUBLICATION_REQUEST_SCHEMA_VERSION = 1


class AiArtifactRegistryError(RuntimeError):
    """Raised when an AI artifact publication request is unsafe or invalid."""


@dataclass(frozen=True)
class AiArtifact:
    path: Path
    logical_name: str
    role: str
    reproducibility_required: bool
    feature_schema_version: str = "not_applicable"


@dataclass(frozen=True)
class ExperimentRegistration:
    destination: Path
    manifest_path: Path
    copied_logical_names: tuple[str, ...]
    staged_paths: tuple[str, ...]


def _request_digest(payload: Mapping[str, object]) -> str:
    core = {key: value for key, value in payload.items() if key != "request_sha256"}
    return hashlib.sha256(canonical_json_bytes(core)).hexdigest()


def _artifact_row(artifact: AiArtifact) -> dict[str, object]:
    if not artifact.logical_name or PurePosixPath(artifact.logical_name).is_absolute() or ".." in PurePosixPath(artifact.logical_name).parts:
        raise AiArtifactRegistryError("ai_artifact_logical_name_invalid")
    if artifact.path.is_symlink() or not artifact.path.is_file():
        raise AiArtifactRegistryError(f"ai_artifact_not_regular:{artifact.logical_name}")
    allowed_roles = {"decision_asset", "model_artifact", "feature_contract", "qualification_evidence", "cache_or_visualization"}
    if artifact.role not in allowed_roles:
        raise AiArtifactRegistryError(f"ai_artifact_role_invalid:{artifact.logical_name}")
    return {
        "path": str(artifact.path.resolve(strict=True)),
        "logical_name": artifact.logical_name,
        "role": artifact.role,
        "reproducibility_required": bool(artifact.reproducibility_required),
        "feature_schema_version": artifact.feature_schema_version,
        "size_bytes": artifact.path.stat().st_size,
        "sha256": sha256_file(artifact.path),
    }


def canonical_publication_request(
    *,
    official_version: str,
    generator: str,
    data_cutoff: str,
    eval_date: str,
    training_label_cutoff: str,
    artifacts: Iterable[AiArtifact],
    source_commit: str,
) -> dict[str, object]:
    rows = sorted((_artifact_row(artifact) for artifact in artifacts), key=lambda row: str(row["logical_name"]))
    logical_names = [str(row["logical_name"]) for row in rows]
    if len(logical_names) != len(set(logical_names)):
        raise AiArtifactRegistryError("duplicate_ai_artifact_logical_name")
    if not rows or not any(bool(row["reproducibility_required"]) for row in rows):
        raise AiArtifactRegistryError("publication_request_has_no_reproducibility_assets")
    payload: dict[str, object] = {
        "schema_version": PUBLICATION_REQUEST_SCHEMA_VERSION,
        "promotion_scope": "official_candidate",
        "official_version": official_version,
        "generator": generator,
        "data_cutoff": data_cutoff,
        "eval_date": eval_date,
        "training_label_cutoff": training_label_cutoff,
        "source_commit": source_commit,
        "ai_artifacts": rows,
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }
    payload["request_sha256"] = _request_digest(payload)
    return payload


def write_json_atomically(destination: Path, payload: Mapping[str, object]) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=str(destination.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(payload) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def write_publication_request(
    *,
    destination: Path,
    official_version: str,
    generator: str,
    data_cutoff: str,
    eval_date: str,
    training_label_cutoff: str,
    artifacts: Iterable[AiArtifact],
    source_commit: str,
) -> Path:
    payload = canonical_publication_request(
        official_version=official_version,
        generator=generator,
        data_cutoff=data_cutoff,
        eval_date=eval_date,
        training_label_cutoff=training_label_cutoff,
        artifacts=artifacts,
        source_commit=source_commit,
    )
    return write_json_atomically(destination, payload)


def load_publication_request(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise AiArtifactRegistryError("publication_request_not_regular")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AiArtifactRegistryError("publication_request_json_invalid") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != PUBLICATION_REQUEST_SCHEMA_VERSION:
        raise AiArtifactRegistryError("publication_request_schema_invalid")
    if payload.get("request_sha256") != _request_digest(payload):
        raise AiArtifactRegistryError("publication_request_sha256_mismatch")
    if payload.get("order_api_called_count") != 0 or payload.get("cancel_order_api_called_count") != 0:
        raise AiArtifactRegistryError("publication_request_order_api_count_nonzero")
    rows = payload.get("ai_artifacts")
    if not isinstance(rows, list) or not rows:
        raise AiArtifactRegistryError("publication_request_artifacts_invalid")
    for row in rows:
        if not isinstance(row, dict):
            raise AiArtifactRegistryError("publication_request_artifact_invalid")
        source = Path(str(row.get("path", "")))
        if source.is_symlink() or not source.is_file():
            raise AiArtifactRegistryError(f"publication_source_missing:{row.get('logical_name', '')}")
        if source.stat().st_size != int(row.get("size_bytes", -1)):
            raise AiArtifactRegistryError(f"publication_source_size_mismatch:{row.get('logical_name', '')}")
        if sha256_file(source) != row.get("sha256"):
            raise AiArtifactRegistryError(f"publication_source_sha256_mismatch:{row.get('logical_name', '')}")
    return payload


def _git(repo_root: Path, *args: str) -> str:
    if args and args[0] in {"commit", "push", "reset", "stash"}:
        raise AiArtifactRegistryError(f"experiment_registry_git_operation_forbidden:{args[0]}")
    process = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise AiArtifactRegistryError(process.stderr.strip() or "experiment_registry_git_failed")
    return process.stdout


def register_experiment_artifacts(
    *,
    repo_root: Path,
    line_id: str,
    stage: str,
    run_id: str,
    artifacts: Iterable[AiArtifact],
) -> ExperimentRegistration:
    repo = repo_root.resolve(strict=True)
    if "production_live" in repo.name or "production-live" in repo.as_posix():
        raise AiArtifactRegistryError("experiment_registry_forbidden_in_production_worktree")
    for label, value in (("line_id", line_id), ("stage", stage), ("run_id", run_id)):
        path = PurePosixPath(value)
        if not value or path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
            raise AiArtifactRegistryError(f"experiment_{label}_invalid")
    selected = sorted(
        (artifact for artifact in artifacts if artifact.reproducibility_required),
        key=lambda item: item.logical_name,
    )
    if not selected:
        raise AiArtifactRegistryError("experiment_has_no_reproducibility_assets")
    destination = repo / "research/ai_assets" / line_id / stage / run_id
    if destination.exists():
        raise AiArtifactRegistryError("experiment_artifact_run_exists")
    destination.mkdir(parents=True)
    rows: list[dict[str, object]] = []
    copied: list[str] = []
    for artifact in selected:
        row = _artifact_row(artifact)
        suffix = artifact.path.suffix
        relative = Path("payload") / f"{artifact.logical_name}{suffix}"
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(artifact.path, target)
        if sha256_file(target) != row["sha256"]:
            raise AiArtifactRegistryError(f"experiment_artifact_copy_drift:{artifact.logical_name}")
        row["source_path"] = str(row.pop("path"))
        row["path"] = relative.as_posix()
        rows.append(row)
        copied.append(artifact.logical_name)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "line_id": line_id,
        "stage": stage,
        "run_id": run_id,
        "artifacts": rows,
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }
    manifest["manifest_sha256"] = hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()
    manifest_path = write_json_atomically(destination / "manifest.json", manifest)
    relative_destination = destination.relative_to(repo).as_posix()
    _git(repo, "add", "--", relative_destination)
    staged = tuple(
        sorted(
            line.strip()
            for line in _git(repo, "diff", "--cached", "--name-only", "--", relative_destination).splitlines()
            if line.strip()
        )
    )
    return ExperimentRegistration(
        destination=destination,
        manifest_path=manifest_path,
        copied_logical_names=tuple(copied),
        staged_paths=staged,
    )
