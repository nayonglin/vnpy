from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Iterable, Mapping


SCHEMA_VERSION = 1
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"


class MaterialManifestError(RuntimeError):
    """Raised when a strategy-material manifest is invalid or has drifted."""


class MaterialRole(str, Enum):
    RUNTIME_CODE = "runtime_code"
    STRATEGY_CONFIG = "strategy_config"
    DECISION_ASSET = "decision_asset"
    MODEL_ARTIFACT = "model_artifact"
    FEATURE_CONTRACT = "feature_contract"
    QUALIFICATION_EVIDENCE = "qualification_evidence"
    OPERATIONAL_CONFIG = "operational_config"


class StorageKind(str, Enum):
    GIT = "git"
    GIT_LFS = "git_lfs"


@dataclass(frozen=True)
class MaterialFile:
    logical_path: str
    payload_path: str
    role: MaterialRole
    storage: StorageKind
    size_bytes: int
    sha256: str
    source_path: str


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_row(file: MaterialFile | Mapping[str, object]) -> dict[str, object]:
    row = asdict(file) if isinstance(file, MaterialFile) else dict(file)
    if isinstance(row.get("role"), Enum):
        row["role"] = row["role"].value
    if isinstance(row.get("storage"), Enum):
        row["storage"] = row["storage"].value
    return row


def _validate_iso8601(value: str, *, field: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MaterialManifestError(f"invalid_{field}") from exc


def _validate_relative_path(value: str, *, field: str) -> None:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise MaterialManifestError(f"invalid_{field}")


def _validate_file_rows(rows: Iterable[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    normalized: list[dict[str, object]] = []
    logical_paths: set[str] = set()
    payload_paths: set[str] = set()
    for raw in rows:
        row = dict(raw)
        required = {
            "logical_path",
            "payload_path",
            "role",
            "storage",
            "size_bytes",
            "sha256",
            "source_path",
        }
        if set(row) != required:
            raise MaterialManifestError("material_file_fields_invalid")
        logical_path = str(row["logical_path"])
        payload_path = str(row["payload_path"])
        _validate_relative_path(logical_path, field="logical_path")
        _validate_relative_path(payload_path, field="payload_path")
        if not payload_path.startswith("payload/"):
            raise MaterialManifestError("payload_path_outside_payload")
        if logical_path in logical_paths:
            raise MaterialManifestError("duplicate_material_logical_path")
        if payload_path in payload_paths:
            raise MaterialManifestError("duplicate_material_payload_path")
        logical_paths.add(logical_path)
        payload_paths.add(payload_path)
        try:
            row["role"] = MaterialRole(str(row["role"])).value
        except ValueError as exc:
            raise MaterialManifestError("unknown_material_role") from exc
        try:
            row["storage"] = StorageKind(str(row["storage"])).value
        except ValueError as exc:
            raise MaterialManifestError("unknown_storage_kind") from exc
        try:
            size_bytes = int(row["size_bytes"])
        except (TypeError, ValueError) as exc:
            raise MaterialManifestError("material_file_size_invalid") from exc
        if size_bytes < 0:
            raise MaterialManifestError("material_file_size_invalid")
        row["size_bytes"] = size_bytes
        sha256 = str(row["sha256"])
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise MaterialManifestError("material_file_sha256_invalid")
        row["sha256"] = sha256
        row["source_path"] = str(row["source_path"])
        normalized.append(row)
    return tuple(sorted(normalized, key=lambda item: (str(item["logical_path"]), str(item["payload_path"]))))


def material_tree_fingerprint(files: Iterable[Mapping[str, object]]) -> str:
    rows = _validate_file_rows(files)
    identity_rows = [
        {
            "logical_path": row["logical_path"],
            "payload_path": row["payload_path"],
            "role": row["role"],
            "storage": row["storage"],
            "size_bytes": row["size_bytes"],
            "sha256": row["sha256"],
        }
        for row in rows
    ]
    return hashlib.sha256(canonical_json_bytes(identity_rows)).hexdigest()


def material_manifest_digest(payload: Mapping[str, object]) -> str:
    core = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    return hashlib.sha256(canonical_json_bytes(core)).hexdigest()


def build_material_manifest(
    *,
    release_id: str,
    strategy_version: str,
    material_version: str,
    source_commit: str,
    created_at_utc: str,
    created_at_cst: str,
    research_line: str,
    capital: float,
    capital_label: str,
    files: Iterable[MaterialFile | Mapping[str, object]],
    provenance: Mapping[str, object],
    qualification: Mapping[str, object],
    parent_material_version: str,
    changes: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if not release_id or not strategy_version or not re.fullmatch(r"m\d{4}", material_version):
        raise MaterialManifestError("material_identity_invalid")
    if not _COMMIT_RE.fullmatch(source_commit):
        raise MaterialManifestError("source_commit_invalid")
    _validate_iso8601(created_at_utc, field="created_at_utc")
    _validate_iso8601(created_at_cst, field="created_at_cst")
    rows = _validate_file_rows(_file_row(file) for file in files)
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "release_id": release_id,
        "strategy_version": strategy_version,
        "material_version": material_version,
        "parent_material_version": parent_material_version,
        "source_commit": source_commit,
        "created_at_utc": created_at_utc,
        "created_at_cst": created_at_cst,
        "research_line": research_line,
        "capital": float(capital),
        "capital_label": capital_label,
        "provenance": dict(provenance),
        "qualification": dict(qualification),
        "changes": dict(changes or {"added": [], "changed": [], "deleted": []}),
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "files": list(rows),
        "tree_fingerprint": material_tree_fingerprint(rows),
    }
    payload["manifest_sha256"] = material_manifest_digest(payload)
    return payload


def serialize_material_manifest(payload: Mapping[str, object]) -> bytes:
    if payload.get("manifest_sha256") != material_manifest_digest(payload):
        raise MaterialManifestError("manifest_sha256_mismatch")
    return canonical_json_bytes(payload) + b"\n"


def load_and_validate_material_manifest(
    manifest_path: Path,
    *,
    release_root: Path | None = None,
) -> dict[str, object]:
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise MaterialManifestError("manifest_not_regular_file")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MaterialManifestError("manifest_json_invalid") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise MaterialManifestError("manifest_schema_version_unsupported")
    required = {
        "schema_version",
        "release_id",
        "strategy_version",
        "material_version",
        "parent_material_version",
        "source_commit",
        "created_at_utc",
        "created_at_cst",
        "research_line",
        "capital",
        "capital_label",
        "provenance",
        "qualification",
        "changes",
        "order_api_called_count",
        "cancel_order_api_called_count",
        "files",
        "tree_fingerprint",
        "manifest_sha256",
    }
    if set(payload) != required:
        raise MaterialManifestError("manifest_top_level_fields_invalid")
    if not _COMMIT_RE.fullmatch(str(payload["source_commit"])):
        raise MaterialManifestError("source_commit_invalid")
    _validate_iso8601(str(payload["created_at_utc"]), field="created_at_utc")
    _validate_iso8601(str(payload["created_at_cst"]), field="created_at_cst")
    if payload["order_api_called_count"] != 0 or payload["cancel_order_api_called_count"] != 0:
        raise MaterialManifestError("order_api_count_must_be_zero")
    files_value = payload.get("files")
    if not isinstance(files_value, list):
        raise MaterialManifestError("manifest_files_invalid")
    rows = _validate_file_rows(files_value)
    if list(rows) != files_value:
        raise MaterialManifestError("manifest_files_not_canonical")
    if payload.get("tree_fingerprint") != material_tree_fingerprint(rows):
        raise MaterialManifestError("material_tree_fingerprint_mismatch")
    if payload.get("manifest_sha256") != material_manifest_digest(payload):
        raise MaterialManifestError("manifest_sha256_mismatch")

    root = (release_root or manifest_path.parent).resolve(strict=True)
    for row in rows:
        target = root / str(row["payload_path"])
        if target.is_symlink() or not target.is_file():
            raise MaterialManifestError("material_file_not_regular")
        try:
            target.resolve(strict=True).relative_to(root)
        except ValueError as exc:
            raise MaterialManifestError("material_payload_path_escape") from exc
        if target.stat().st_size != int(row["size_bytes"]):
            raise MaterialManifestError("material_file_size_mismatch")
        with target.open("rb") as handle:
            if handle.read(len(_LFS_POINTER_PREFIX)) == _LFS_POINTER_PREFIX:
                raise MaterialManifestError("git_lfs_pointer_not_expanded")
        if sha256_file(target) != row["sha256"]:
            raise MaterialManifestError("material_file_sha256_mismatch")
    return payload
